"""Model-Based Testing for HTTP API using Hypothesis state machine."""

import json
import os
import socket
import sys
import tempfile
import threading
import time
from typing import Any
from wsgiref.simple_server import WSGIRequestHandler, make_server

from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    rule,
    run_state_machine_as_test,
)


def _add_project_root() -> None:
    """Ensure repository root is on sys.path for direct script execution."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)


def find_free_port() -> int:
    """Find available TCP port on localhost."""
    _add_project_root()
    from src import config as cfg

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((cfg.DEFAULT_HOST, cfg.ZERO))
    port = sock.getsockname()[1]
    sock.close()
    return port


class QuietHandler(WSGIRequestHandler):
    """WSGI request handler suppressing stderr access logs."""

    def log_message(self, fmt: str, *args: Any) -> None:
        """Silence default HTTP request logging during MBT execution."""
        return


class ServerRunner:
    """Helper to run Bottle WSGI server in background thread."""

    def __init__(self, storage: Any, test_mode: bool = False):
        """Initialize WSGI server thread runner."""
        _add_project_root()
        from src import config as cfg
        from src.app import create_app

        self.port = find_free_port()
        self.storage = storage
        self.app = create_app(
            storage=storage,
            username=cfg.DEFAULT_USERNAME,
            password=cfg.DEFAULT_PASSWORD,
            test_mode=test_mode,
        )
        self.server = make_server(
            cfg.DEFAULT_HOST,
            self.port,
            self.app,
            handler_class=QuietHandler,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        time.sleep(0.1)

    def stop(self) -> None:
        """Stop background WSGI server."""
        self.server.shutdown()
        self.server.server_close()


class ReferenceModel:
    """Independent reference model for state tracking."""

    def __init__(self) -> None:
        """Initialize reference data tables."""
        self.users: dict[int, dict[str, Any]] = {}
        self.messages: dict[int, dict[str, Any]] = {}
        self.completions: dict[int, dict[str, Any]] = {}

    def add_user(self, uid: int, ip: str, locale: str) -> None:
        """Track user creation."""
        self.users[uid] = {"identifier": uid, "ip": ip, "locale": locale}

    def delete_user(self, uid: int) -> None:
        """Track user deletion."""
        if uid in self.users:
            del self.users[uid]

    def add_message(
        self, mid: int, cid: int, msg_data: dict[str, Any]
    ) -> None:
        """Track message and completion creation."""
        self.messages[mid] = {
            "identifier": mid,
            "user": msg_data["user"],
            "input": msg_data["input"],
            "description": msg_data["description"],
            "triggered": msg_data["triggered"],
        }
        self.completions[cid] = {
            "identifier": cid,
            "message": mid,
            "state": msg_data["state"],
        }

    def delete_message(self, mid: int) -> None:
        """Track message and cascade completion deletion."""
        if mid in self.messages:
            del self.messages[mid]
        self.completions = {
            cid: comp
            for cid, comp in self.completions.items()
            if comp["message"] != mid
        }

    def expected_report(self) -> list[tuple[str, str, str]]:
        """Compute expected report tuples per Formula (15)."""
        items: list[tuple[str, str, str]] = []
        for mid, msg in self.messages.items():
            user = self.users.get(msg["user"])
            u_ip = user["ip"] if user is not None else ""
            for comp in self.completions.values():
                if comp["message"] == mid:
                    items.append((comp["state"], msg["description"], u_ip))
        return items


class BaseApiStateMachine(RuleBasedStateMachine):
    """Abstract Hypothesis RuleBasedStateMachine for HTTP API."""

    users = Bundle("users")
    messages = Bundle("messages")
    storage: Any = None
    runner: Any = None
    tmp_dir: str = "."

    def __init__(self) -> None:
        """Initialize state machine, storage and HTTP client."""
        _add_project_root()
        from src import config as cfg
        from src.client import ApiClient

        super().__init__()
        self.cfg = cfg
        self.storage.clear()
        self.client = ApiClient(
            base_url="http://{}:{}".format(
                cfg.DEFAULT_HOST, self.runner.port
            ),
            username=cfg.DEFAULT_USERNAME,
            password=cfg.DEFAULT_PASSWORD,
        )
        self.model = ReferenceModel()

    def _assert_message_insert(
        self, user_id: int, sample_input: str, desc: str, triggered: int
    ) -> int:
        """Execute message insert and verify response against model."""
        res = self.client.private_api_stable_message_insert(
            user_id, sample_input, desc, triggered
        )
        mid = res["message_id"]
        cid = res["completion_id"]
        assert mid > self.cfg.ZERO
        assert cid > self.cfg.ZERO
        assert mid not in self.model.messages
        assert cid not in self.model.completions
        assert res["state"] == self.cfg.STATE_SUCCESS
        self.model.add_message(
            mid,
            cid,
            {
                "user": user_id,
                "input": sample_input,
                "description": desc,
                "triggered": triggered,
                "state": res["state"],
            },
        )
        return mid

    @rule(
        target=users,
        ip=st.ip_addresses().map(str),
        locale=st.sampled_from(["ru-RU", "en-US", "de-DE"]),
    )
    def rule_user_insert(self, ip: str, locale: str) -> int:
        """Test POST /private/api/stable/user/insert."""
        u_data = self.client.private_api_stable_user_insert(ip, locale)
        uid = u_data["identifier"]
        assert uid > self.cfg.ZERO
        assert uid not in self.model.users
        assert u_data["time"] >= self.cfg.MIN_TIMESTAMP
        assert u_data["ip"] == ip
        assert u_data["locale"] == locale
        self.model.add_user(uid, ip, locale)
        return uid

    @rule(uid=users)
    def rule_user_del(self, uid: int) -> None:
        """Test GET /private/api/stable/user/del."""
        res = self.client.private_api_stable_user_del(uid)
        expected = "ok" if uid in self.model.users else "not_found"
        assert res["status"] == expected
        self.model.delete_user(uid)

    @rule(uid=users)
    def rule_user_query_by_id(self, uid: int) -> None:
        """Test GET /private/api/stable/user/query with identifier."""
        res = self.client.private_api_stable_user_query(identifier=uid)
        if uid in self.model.users:
            exp = self.model.users[uid]
            assert len(res) == self.cfg.ONE
            assert res[self.cfg.ZERO]["identifier"] == uid
            assert res[self.cfg.ZERO]["ip"] == exp["ip"]
            assert res[self.cfg.ZERO]["locale"] == exp["locale"]
            assert res[self.cfg.ZERO]["time"] >= self.cfg.MIN_TIMESTAMP
        else:
            assert res == []

    @rule(ip=st.ip_addresses().map(str))
    def rule_user_query_by_ip(self, ip: str) -> None:
        """Test GET /private/api/stable/user/query with IP."""
        res = self.client.private_api_stable_user_query(ip=ip)
        exp_ids = {
            k for k, u in self.model.users.items() if u["ip"] == ip
        }
        got_ids = {u["identifier"] for u in res}
        assert got_ids == exp_ids

    @rule()
    def rule_user_query_all(self) -> None:
        """Test GET /private/api/stable/user/query without arguments."""
        res = self.client.private_api_stable_user_query()
        got_ids = {u["identifier"] for u in res}
        assert got_ids == set(self.model.users.keys())

    @rule(
        target=messages,
        user=users,
        desc=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-",
            min_size=1,
            max_size=15,
        ),
        triggered=st.integers(min_value=0, max_value=1),
    )
    def rule_message_insert(
        self, user: int, desc: str, triggered: int
    ) -> int:
        """Test POST /private/api/stable/message/insert with valid user."""
        sample_input = json.dumps(
            {
                "code": "460123456789",
                "title": "Item Barcode",
                "output_pdf": os.path.join(self.tmp_dir, "test_mbt_bar.pdf"),
            }
        )
        return self._assert_message_insert(user, sample_input, desc, triggered)

    @rule(
        target=messages,
        fake_user=st.integers(min_value=9000, max_value=9999),
        desc=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-",
            min_size=1,
            max_size=15,
        ),
    )
    def rule_message_insert_orphan(self, fake_user: int, desc: str) -> int:
        """Test POST /private/api/stable/message/insert with orphan message."""
        sample_input = json.dumps(
            {
                "code": "460987654321",
                "title": "Orphan Barcode",
                "output_pdf": os.path.join(
                    self.tmp_dir, "test_mbt_orphan.pdf"
                ),
            }
        )
        return self._assert_message_insert(
            fake_user, sample_input, desc, self.cfg.ZERO
        )

    @rule(mid=messages)
    def rule_message_del(self, mid: int) -> None:
        """Test GET /private/api/stable/message/del."""
        res = self.client.private_api_stable_message_del(mid)
        expected = "ok" if mid in self.model.messages else "not_found"
        assert res["status"] == expected
        self.model.delete_message(mid)

    @rule(user=users)
    def rule_message_query_by_user(self, user: int) -> None:
        """Test GET /private/api/stable/message/query/:user."""
        res = self.client.private_api_stable_message_query_user(user)
        exp_msgs = {
            k: m
            for k, m in self.model.messages.items()
            if m["user"] == user
        }
        got_ids = {m["identifier"] for m in res}
        assert got_ids == set(exp_msgs.keys())
        for msg in res:
            exp = exp_msgs[msg["identifier"]]
            assert msg["user"] == exp["user"]
            assert msg["input"] == exp["input"]
            assert msg["description"] == exp["description"]
            assert msg["triggered"] == exp["triggered"]
            assert msg["time"] >= self.cfg.MIN_TIMESTAMP

    @rule(mid=messages)
    def rule_completion_query_by_msg(self, mid: int) -> None:
        """Test GET /private/api/stable/completion/query/:message."""
        res = self.client.private_api_stable_completion_query_message(mid)
        exp_comps = {
            k: c
            for k, c in self.model.completions.items()
            if c["message"] == mid
        }
        got_ids = {c["identifier"] for c in res}
        assert got_ids == set(exp_comps.keys())
        for comp in res:
            exp = exp_comps[comp["identifier"]]
            assert comp["message"] == mid
            assert comp["state"] == exp["state"]
            assert comp["time"] >= self.cfg.MIN_TIMESTAMP

    @rule()
    def rule_report_query(self) -> None:
        """Test GET /private/api/stable/report/query."""
        res = self.client.private_api_stable_report_query()
        got = sorted((it["state"], it["description"], it["ip"]) for it in res)
        exp = sorted(self.model.expected_report())
        assert got == exp

    @rule()
    def rule_exercise_error_branches(self) -> None:
        """Exercise error handling branches to maximize branch coverage."""
        from src.client import ApiClient

        unauth_client = ApiClient(
            base_url="http://{}:{}".format(
                self.cfg.DEFAULT_HOST, self.runner.port
            ),
            username="bad_user",
            password="bad_password",
        )
        st_code, _ = unauth_client._send(
            "GET", "/private/api/stable/report/query"
        )
        assert st_code == self.cfg.STATUS_UNAUTHORIZED

        st_bad_del, _ = self.client._send(
            "GET", "/private/api/stable/user/del"
        )
        assert st_bad_del == self.cfg.STATUS_BAD_REQUEST

        st_bad_msg_del, _ = self.client._send(
            "GET", "/private/api/stable/message/del"
        )
        assert st_bad_msg_del == self.cfg.STATUS_BAD_REQUEST

        st_bad_user_xml, _ = self.client._send(
            "POST", "/private/api/stable/user/insert", body="<bad>xml"
        )
        assert st_bad_user_xml == self.cfg.STATUS_BAD_REQUEST

        st_bad_msg_xml, _ = self.client._send(
            "POST", "/private/api/stable/message/insert", body="<bad>xml"
        )
        assert st_bad_msg_xml == self.cfg.STATUS_BAD_REQUEST


class FileStorageStateMachine(BaseApiStateMachine):
    """MBT state machine testing HTTP API with FileStorage backend."""


class PonyStorageStateMachine(BaseApiStateMachine):
    """MBT state machine testing HTTP API with PonyStorage backend."""


def _run_storage_mbt(
    machine_cls: type[BaseApiStateMachine],
    storage_cls: type,
    db_name: str,
    test_mode: bool,
) -> None:
    """Start test server for storage backend and execute Hypothesis MBT."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        db_path = os.path.join(tmp_dir, db_name)
        storage = storage_cls(db_path)
        runner = ServerRunner(storage, test_mode=test_mode)
        machine_cls.storage = storage
        machine_cls.runner = runner
        machine_cls.tmp_dir = tmp_dir
        try:
            run_state_machine_as_test(
                machine_cls,
                settings=hyp_settings(max_examples=25, stateful_step_count=15),
            )
        finally:
            runner.stop()
            storage.clear()
            if hasattr(storage, "db"):
                storage.db.disconnect()


def test_file_storage_mbt() -> None:
    """Execute Hypothesis MBT against FileStorage HTTP API."""
    _add_project_root()
    from src.storage_file import FileStorage

    _run_storage_mbt(
        FileStorageStateMachine, FileStorage, "test_mbt_file.json", False
    )


def test_pony_storage_mbt() -> None:
    """Execute Hypothesis MBT against PonyStorage SQLite HTTP API."""
    _add_project_root()
    from src.storage_pony import PonyStorage

    _run_storage_mbt(
        PonyStorageStateMachine, PonyStorage, "test_mbt_pony.sqlite3", True
    )


if __name__ == "__main__":
    test_pony_storage_mbt()
    test_file_storage_mbt()
    print("All MBT tests passed!")
