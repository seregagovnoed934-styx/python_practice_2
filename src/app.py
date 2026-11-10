"""Bottle web server implementing HTTP API for Variant 15."""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Optional
from xml.etree.ElementTree import Element, tostring

from bottle import Bottle, HTTPResponse, request, response

from src.config import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_USERNAME,
    EXIT_SUCCESS,
    STATE_FAILURE,
    STATE_SUCCESS,
    STATUS_BAD_REQUEST,
    STATUS_UNAUTHORIZED,
    ZERO,
)
from src.models import (
    completion_to_xml_element,
    message_to_xml_element,
    parse_xml_message,
    parse_xml_user,
    serialize_action_status,
    serialize_completions,
    serialize_messages,
    serialize_report,
    serialize_user,
    serialize_users,
)
from src.storage_file import FileStorage


def check_basic_auth(
    auth_header: Optional[str], u_exp: str, p_exp: str
) -> bool:
    """Validate HTTP Basic Authentication credentials per RFC 7617."""
    if not auth_header or not auth_header.startswith("Basic "):
        return False
    try:
        encoded = auth_header[6:].strip()
        decoded = base64.b64decode(encoded).decode("utf-8")
        if ":" not in decoded:
            return False
        username, password = decoded.split(":", 1)
        return username == u_exp and password == p_exp
    except Exception:
        return False


def run_cli_task(input_content: str) -> tuple[str, str, int, str]:
    """Execute computation task via CLI subprocess."""
    start_t = time.time()
    in_fd, in_path = tempfile.mkstemp(suffix=".json")
    out_fd, out_path = tempfile.mkstemp(suffix=".json")
    os.close(in_fd)
    os.close(out_fd)

    try:
        with open(in_path, "w", encoding="utf-8") as f_in:
            f_in.write(input_content)

        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [sys.executable, "-m", "src.cli", "-i", in_path, "-o", out_path]
        proc = subprocess.run(
            cmd, cwd=root_dir, capture_output=True, text=True, check=False
        )
        duration_ms = int((time.time() - start_t) * 1000)

        if proc.returncode == EXIT_SUCCESS and os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as f_out:
                res_text = f_out.read()
            return res_text, STATE_SUCCESS, duration_ms, ""
        return "", STATE_FAILURE, duration_ms, proc.stderr or "CLI error"
    finally:
        for p in (in_path, out_path):
            if os.path.exists(p):
                os.remove(p)


def make_auth_checker(username: str, password: str):
    """Build authentication check callback."""

    def auth_required() -> Optional[HTTPResponse]:
        hdr = request.headers.get("Authorization")
        if not check_basic_auth(hdr, username, password):
            resp = HTTPResponse(
                body=serialize_action_status("error", "Unauthorized"),
                status=STATUS_UNAUTHORIZED,
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )
            resp.set_header("WWW-Authenticate", 'Basic realm="API"')
            return resp
        return None

    return auth_required


def register_user_insert(app: Bottle, storage, check_auth) -> None:
    """Register user insert route handler on Bottle app."""

    @app.route("/private/api/stable/user/insert", method="POST")
    def user_insert():
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        try:
            body = request.body.read().decode("utf-8")
            data = parse_xml_user(body)
            u = storage.add_user(ip=data["ip"], locale=data["locale"])
            return serialize_user(u)
        except Exception as exc:
            response.status = STATUS_BAD_REQUEST
            return serialize_action_status("error", str(exc))


def register_user_del_and_query(app: Bottle, storage, check_auth) -> None:
    """Register user delete and query route handlers."""

    @app.route("/private/api/stable/user/del", method="GET")
    def user_del():
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        raw_id = request.query.get("identifier")
        if not raw_id:
            response.status = STATUS_BAD_REQUEST
            return serialize_action_status("error", "Missing identifier")
        success = storage.delete_user(int(raw_id))
        st = "ok" if success else "not_found"
        return serialize_action_status(st)

    @app.route("/private/api/stable/user/query", method="GET")
    def user_query():
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        raw_id = request.query.get("identifier")
        uid = int(raw_id) if raw_id else None
        ip_val = request.query.get("ip")
        users = storage.get_users(identifier=uid, ip=ip_val)
        return serialize_users(users)


def _exec_message_task(
    input_str: str, test_mode: bool
) -> tuple[str, str, int, str]:
    """Execute computation task or return mock for testing."""
    if test_mode:
        res_str = json.dumps({"status": "MATCH", "test": True})
        return res_str, STATE_SUCCESS, ZERO, ""
    return run_cli_task(input_str)


def register_message_insert(
    app: Bottle, storage, check_auth, test_mode: bool
) -> None:
    """Register message insert route handler on Bottle app."""

    @app.route("/private/api/stable/message/insert", method="POST")
    def message_insert():
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        try:
            body = request.body.read().decode("utf-8")
            data = parse_xml_message(body)
            msg = storage.add_message(
                user_id=data["user"],
                input_data=data["input"],
                description=data["description"],
                triggered=data["triggered"],
            )
            res_str, st_val, dur, fail_str = _exec_message_task(
                msg.input, test_mode
            )
            comp = storage.add_completion(
                message_id=msg.identifier,
                result=res_str,
                state=st_val,
                failure=fail_str,
                cache_hit=ZERO,
                duration=dur,
            )
            root = Element("response")
            root.append(message_to_xml_element(msg))
            root.append(completion_to_xml_element(comp))
            return tostring(root, encoding="utf-8").decode("utf-8")
        except Exception as exc:
            response.status = STATUS_BAD_REQUEST
            return serialize_action_status("error", str(exc))


def register_message_del_and_query(app: Bottle, storage, check_auth) -> None:
    """Register message delete and query route handlers."""

    @app.route("/private/api/stable/message/del", method="GET")
    def message_del():
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        raw_id = request.query.get("identifier")
        if not raw_id:
            response.status = STATUS_BAD_REQUEST
            return serialize_action_status("error", "Missing identifier")
        success = storage.delete_message(int(raw_id))
        st = "ok" if success else "not_found"
        return serialize_action_status(st)

    @app.route("/private/api/stable/message/query/<user:int>", method="GET")
    def message_query(user: int):
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        raw_id = request.query.get("identifier")
        mid = int(raw_id) if raw_id else None
        messages = storage.get_messages(user_id=user, identifier=mid)
        return serialize_messages(messages)


def register_query_routes(app: Bottle, storage, check_auth) -> None:
    """Register completion and report query route handlers."""

    @app.route(
        "/private/api/stable/completion/query/<message:int>", method="GET"
    )
    def completion_query(message: int):
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        raw_id = request.query.get("identifier")
        cid = int(raw_id) if raw_id else None
        comps = storage.get_completions(message_id=message, identifier=cid)
        return serialize_completions(comps)

    @app.route("/private/api/stable/report/query", method="GET")
    def report_query():
        err = check_auth()
        if err:
            return err
        response.content_type = "text/xml; charset=utf-8"
        report_data = storage.get_report()
        return serialize_report(report_data)


def create_app(
    storage,
    username: str = DEFAULT_USERNAME,
    password: str = DEFAULT_PASSWORD,
    test_mode: bool = False,
) -> Bottle:
    """Create and configure Bottle application instance."""
    app = Bottle()
    check_auth = make_auth_checker(username, password)
    register_user_insert(app, storage, check_auth)
    register_user_del_and_query(app, storage, check_auth)
    register_message_insert(app, storage, check_auth, test_mode)
    register_message_del_and_query(app, storage, check_auth)
    register_query_routes(app, storage, check_auth)
    return app


def main() -> None:
    """CLI entry point to launch web application server."""
    parser = argparse.ArgumentParser(description="Bottle HTTP API Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to bind"
    )
    parser.add_argument(
        "-u",
        "--username",
        default=DEFAULT_USERNAME,
        help="Basic auth username",
    )
    parser.add_argument(
        "-p",
        "--password",
        default=DEFAULT_PASSWORD,
        help="Basic auth password",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Run without executing CLI tasks",
    )
    args = parser.parse_args()

    storage = FileStorage()
    app = create_app(
        storage=storage,
        username=args.username,
        password=args.password,
        test_mode=args.test_mode,
    )
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
