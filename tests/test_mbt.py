"""Model-Based Testing for HTTP API using Hypothesis state machine."""

import json
import os
import socket
import threading
import time
from typing import Any
from wsgiref.simple_server import make_server

from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    rule,
)

from src.app import create_app
from src.client import ApiClient
from src.config import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_USERNAME,
    STATUS_BAD_REQUEST,
    STATUS_UNAUTHORIZED,
    ZERO,
)
from src.storage_file import FileStorage
from src.storage_pony import PonyStorage


def find_free_port() -> int:
    """Find available TCP port on localhost."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((DEFAULT_HOST, ZERO))
    port = sock.getsockname()[1]
    sock.close()
    return port


class ServerRunner:
    """Helper to run Bottle WSGI server in background thread."""

    def __init__(self, storage, test_mode: bool = False):
        """Initialize WSGI server thread runner."""
        self.port = find_free_port()
        self.storage = storage
        self.app = create_app(
            storage=storage,
            username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD,
            test_mode=test_mode,
        )
        self.server = make_server(DEFAULT_HOST, self.port, self.app)
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
        self, mid: int, cid: int, user: int, desc: str, st_val: str
    ) -> None:
        """Track message and completion creation."""
        self.messages[mid] = {"identifier": mid, "user": user, "desc": desc}
        self.completions[cid] = {
            "identifier": cid,
            "message": mid,
            "state": st_val,
        }

    def delete_message(self, mid: int) -> None:
        """Track message deletion."""
        if mid in self.messages:
            del self.messages[mid]


class BaseApiStateMachine(RuleBasedStateMachine):
    """Abstract Hypothesis RuleBasedStateMachine for HTTP API."""

    users = Bundle("users")
    messages = Bundle("messages")

    def __init__(self) -> None:
        """Initialize state machine, storage and HTTP client."""
        super().__init__()
        self.storage.clear()
        self.client = ApiClient(
            base_url=f"http://{DEFAULT_HOST}:{self.runner.port}",
            username=DEFAULT_USERNAME,
            password=DEFAULT_PASSWORD,
        )
        self.model = ReferenceModel()

    @rule(
        target=users,
        ip=st.ip_addresses().map(str),
        locale=st.sampled_from(["ru-RU", "en-US", "de-DE"]),
    )
    def rule_user_insert(self, ip: str, locale: str) -> int:
        """Test POST /private/api/stable/user/insert."""
        u_data = self.client.private_api_stable_user_insert(ip, locale)
        uid = u_data["identifier"]
        assert uid > ZERO
        assert u_data["ip"] == ip
        assert u_data["locale"] == locale
        self.model.add_user(uid, ip, locale)
        return uid

    @rule(uid=users)
    def rule_user_del(self, uid: int) -> None:
        """Test GET /private/api/stable/user/del."""
        res = self.client.private_api_stable_user_del(uid)
        assert res["status"] in ("ok", "not_found")
        self.model.delete_user(uid)

    @rule(uid=users)
    def rule_user_query_by_id(self, uid: int) -> None:
        """Test GET /private/api/stable/user/query with identifier."""
        res = self.client.private_api_stable_user_query(identifier=uid)
        assert isinstance(res, list)

    @rule(ip=st.ip_addresses().map(str))
    def rule_user_query_by_ip(self, ip: str) -> None:
        """Test GET /private/api/stable/user/query with IP."""
        res = self.client.private_api_stable_user_query(ip=ip)
        assert isinstance(res, list)

    @rule()
    def rule_user_query_all(self) -> None:
        """Test GET /private/api/stable/user/query without arguments."""
        res = self.client.private_api_stable_user_query()
        assert isinstance(res, list)

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
                "user_1": {
                    "id": 1,
                    "age": 25,
                    "interests": ["tech"],
                    "lat": 55.0,
                    "lon": 37.0,
                },
                "user_2": {
                    "id": 2,
                    "age": 26,
                    "interests": ["tech"],
                    "lat": 55.0,
                    "lon": 37.0,
                },
            }
        )
        res = self.client.private_api_stable_message_insert(
            user, sample_input, desc, triggered
        )
        mid = res["message_id"]
        cid = res["completion_id"]
        assert mid > ZERO
        assert cid > ZERO
        self.model.add_message(mid, cid, user, desc, res["state"])
        return mid

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
                "user_1": {
                    "id": 10,
                    "age": 30,
                    "interests": ["art"],
                    "lat": 55.0,
                    "lon": 37.0,
                },
                "user_2": {
                    "id": 11,
                    "age": 30,
                    "interests": ["art"],
                    "lat": 55.0,
                    "lon": 37.0,
                },
            }
        )
        res = self.client.private_api_stable_message_insert(
            fake_user, sample_input, desc, ZERO
        )
        mid = res["message_id"]
        cid = res["completion_id"]
        assert mid > ZERO
        self.model.add_message(mid, cid, fake_user, desc, res["state"])
        return mid

    @rule(mid=messages)
    def rule_message_del(self, mid: int) -> None:
        """Test GET /private/api/stable/message/del."""
        res = self.client.private_api_stable_message_del(mid)
        assert res["status"] in ("ok", "not_found")
        self.model.delete_message(mid)

    @rule(user=users)
    def rule_message_query_by_user(self, user: int) -> None:
        """Test GET /private/api/stable/message/query/:user."""
        res = self.client.private_api_stable_message_query_user(user)
        assert isinstance(res, list)

    @rule(mid=messages)
    def rule_completion_query_by_msg(self, mid: int) -> None:
        """Test GET /private/api/stable/completion/query/:message."""
        res = self.client.private_api_stable_completion_query_message(mid)
        assert isinstance(res, list)

    @rule()
    def rule_report_query(self) -> None:
        """Test GET /private/api/stable/report/query."""
        res = self.client.private_api_stable_report_query()
        assert isinstance(res, list)

    @rule()
    def rule_exercise_error_branches(self) -> None:
        """Exercise error handling branches to maximize branch coverage."""
        unauth_client = ApiClient(
            base_url=f"http://{DEFAULT_HOST}:{self.runner.port}",
            username="bad_user",
            password="bad_password",
        )
        st_code, _ = unauth_client._send(
            "GET", "/private/api/stable/report/query"
        )
        assert st_code == STATUS_UNAUTHORIZED

        st_bad_del, _ = self.client._send(
            "GET", "/private/api/stable/user/del"
        )
        assert st_bad_del == STATUS_BAD_REQUEST

        st_bad_msg_del, _ = self.client._send(
            "GET", "/private/api/stable/message/del"
        )
        assert st_bad_msg_del == STATUS_BAD_REQUEST

        st_bad_user_xml, _ = self.client._send(
            "POST", "/private/api/stable/user/insert", body="<bad>xml"
        )
        assert st_bad_user_xml == STATUS_BAD_REQUEST

        st_bad_msg_xml, _ = self.client._send(
            "POST", "/private/api/stable/message/insert", body="<bad>xml"
        )
        assert st_bad_msg_xml == STATUS_BAD_REQUEST


file_storage_instance = FileStorage("test_mbt_file.json")
file_server_runner = ServerRunner(file_storage_instance, test_mode=False)


class FileStorageStateMachine(BaseApiStateMachine):
    """MBT state machine testing HTTP API with FileStorage backend."""

    storage = file_storage_instance
    runner = file_server_runner


pony_storage_instance = PonyStorage("test_mbt_pony.sqlite3")
pony_server_runner = ServerRunner(pony_storage_instance, test_mode=True)


class PonyStorageStateMachine(BaseApiStateMachine):
    """MBT state machine testing HTTP API with PonyStorage backend."""

    storage = pony_storage_instance
    runner = pony_server_runner


TestFileStorageMBT = FileStorageStateMachine.TestCase
TestFileStorageMBT.settings = hyp_settings(
    max_examples=25, stateful_step_count=15
)

TestPonyStorageMBT = PonyStorageStateMachine.TestCase
TestPonyStorageMBT.settings = hyp_settings(
    max_examples=25, stateful_step_count=15
)


def teardown_module() -> None:
    """Tear down WSGI servers and clean persistent data."""
    file_server_runner.stop()
    pony_server_runner.stop()
    file_storage_instance.clear()
    pony_storage_instance.clear()
    for fname in ("test_mbt_file.json", "test_mbt_pony.sqlite3"):
        if os.path.exists(fname):
            try:
                os.remove(fname)
            except OSError:
                pass
