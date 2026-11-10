"""HTTP API client with route-mapped method names."""

import base64
from typing import Any, Optional
import urllib.error
import urllib.parse
import urllib.request
from xml.etree.ElementTree import Element, SubElement, fromstring, tostring

from src.config import (
    DEFAULT_HOST,
    DEFAULT_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DEFAULT_USERNAME,
    STATUS_OK,
)


class ApiClient:
    """Client for Variant 15 HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: str = DEFAULT_USERNAME,
        password: str = DEFAULT_PASSWORD,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize HTTP client with target endpoint and credentials."""
        self.base_url = (
            base_url or "http://{}:{}".format(DEFAULT_HOST, DEFAULT_PORT)
        ).rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout

    def _get_auth_header(self) -> str:
        """Construct RFC 7617 Basic Authentication header value."""
        raw = "{}:{}".format(self.username, self.password).encode("utf-8")
        token = base64.b64encode(raw).decode("utf-8")
        return f"Basic {token}"

    def _send(
        self,
        method: str,
        path: str,
        body: Optional[str] = None,
        query: Optional[dict[str, Any]] = None,
    ) -> tuple[int, str]:
        """Perform HTTP request and return status code and response body."""
        url = f"{self.base_url}{path}"
        if query:
            clean_q = {k: v for k, v in query.items() if v is not None}
            if clean_q:
                url = f"{url}?{urllib.parse.urlencode(clean_q)}"

        data = body.encode("utf-8") if body else None
        req = urllib.request.Request(url=url, data=data, method=method)
        req.add_header("Authorization", self._get_auth_header())
        req.add_header("Accept", "text/xml")
        if body:
            req.add_header("Content-Type", "text/xml; charset=utf-8")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                resp_text = resp.read().decode("utf-8")
                return status, resp_text
        except urllib.error.HTTPError as err:
            err_text = err.read().decode("utf-8")
            return err.code, err_text

    def private_api_stable_user_insert(
        self, ip: str, locale: str
    ) -> dict[str, Any]:
        """Insert new user record via POST /private/api/stable/user/insert."""
        elem = Element("user")
        SubElement(elem, "ip").text = ip
        SubElement(elem, "locale").text = locale
        xml_body = tostring(elem, encoding="utf-8").decode("utf-8")
        st, text = self._send(
            "POST", "/private/api/stable/user/insert", xml_body
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        return {
            "identifier": int(root.findtext("identifier", "0")),
            "time": int(root.findtext("time", "0")),
            "ip": root.findtext("ip", ""),
            "locale": root.findtext("locale", ""),
        }

    def private_api_stable_user_del(self, identifier: int) -> dict[str, Any]:
        """Delete user by identifier via GET /private/api/stable/user/del."""
        st, text = self._send(
            "GET",
            "/private/api/stable/user/del",
            query={"identifier": identifier},
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        return {"status": root.findtext("status", "")}

    def private_api_stable_user_query(
        self,
        identifier: Optional[int] = None,
        ip: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Query users via GET /private/api/stable/user/query."""
        st, text = self._send(
            "GET",
            "/private/api/stable/user/query",
            query={"identifier": identifier, "ip": ip},
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        res = []
        for u in root.findall("user"):
            res.append(
                {
                    "identifier": int(u.findtext("identifier", "0")),
                    "time": int(u.findtext("time", "0")),
                    "ip": u.findtext("ip", ""),
                    "locale": u.findtext("locale", ""),
                }
            )
        return res

    def private_api_stable_message_insert(
        self,
        user: int,
        input_data: str,
        description: str,
        triggered: int,
    ) -> dict[str, Any]:
        """Insert message via POST /private/api/stable/message/insert."""
        elem = Element("message")
        SubElement(elem, "user").text = str(user)
        SubElement(elem, "input").text = input_data
        SubElement(elem, "description").text = description
        SubElement(elem, "triggered").text = str(triggered)
        xml_body = tostring(elem, encoding="utf-8").decode("utf-8")
        st, text = self._send(
            "POST", "/private/api/stable/message/insert", xml_body
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        m_elem = root.find("message")
        c_elem = root.find("completion")
        return {
            "message_id": int(m_elem.findtext("identifier", "0")),
            "completion_id": int(c_elem.findtext("identifier", "0")),
            "state": c_elem.findtext("state", ""),
            "result": c_elem.findtext("result", ""),
        }

    def private_api_stable_message_del(
        self, identifier: int
    ) -> dict[str, Any]:
        """Delete message via GET /private/api/stable/message/del."""
        st, text = self._send(
            "GET",
            "/private/api/stable/message/del",
            query={"identifier": identifier},
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        return {"status": root.findtext("status", "")}

    def private_api_stable_message_query_user(
        self, user: int
    ) -> list[dict[str, Any]]:
        """Query messages by user via GET .../message/query/:user."""
        st, text = self._send(
            "GET", f"/private/api/stable/message/query/{user}"
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        res = []
        for m in root.findall("message"):
            res.append(
                {
                    "identifier": int(m.findtext("identifier", "0")),
                    "time": int(m.findtext("time", "0")),
                    "input": m.findtext("input", ""),
                    "user": int(m.findtext("user", "0")),
                    "description": m.findtext("description", ""),
                    "triggered": int(m.findtext("triggered", "0")),
                }
            )
        return res

    def private_api_stable_completion_query_message(
        self, message: int
    ) -> list[dict[str, Any]]:
        """Query completions by message via GET .../completion/query."""
        st, text = self._send(
            "GET", f"/private/api/stable/completion/query/{message}"
        )
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        res = []
        for c in root.findall("completion"):
            res.append(
                {
                    "identifier": int(c.findtext("identifier", "0")),
                    "time": int(c.findtext("time", "0")),
                    "result": c.findtext("result", ""),
                    "state": c.findtext("state", ""),
                    "failure": c.findtext("failure", ""),
                    "message": int(c.findtext("message", "0")),
                    "cache_hit": int(c.findtext("cache_hit", "0")),
                    "duration": int(c.findtext("duration", "0")),
                }
            )
        return res

    def private_api_stable_report_query(self) -> list[dict[str, Any]]:
        """Query report via GET /private/api/stable/report/query."""
        st, text = self._send("GET", "/private/api/stable/report/query")
        if st != STATUS_OK:
            raise RuntimeError(f"HTTP {st}: {text}")
        root = fromstring(text)
        res = []
        for it in root.findall("item"):
            res.append(
                {
                    "state": it.findtext("state", ""),
                    "description": it.findtext("description", ""),
                    "ip": it.findtext("ip", ""),
                }
            )
        return res

    private_api_stable_message_query = private_api_stable_message_query_user
    private_api_stable_completion_query = (
        private_api_stable_completion_query_message
    )

    _private_api_stable_user_insert = private_api_stable_user_insert
    _private_api_stable_user_del = private_api_stable_user_del
    _private_api_stable_user_query = private_api_stable_user_query
    _private_api_stable_message_insert = private_api_stable_message_insert
    _private_api_stable_message_del = private_api_stable_message_del
    _private_api_stable_message_query = private_api_stable_message_query_user
    _private_api_stable_message_query_user = (
        private_api_stable_message_query_user
    )
    _private_api_stable_completion_query = (
        private_api_stable_completion_query_message
    )
    _private_api_stable_completion_query_message = (
        private_api_stable_completion_query_message
    )
    _private_api_stable_report_query = private_api_stable_report_query


def main() -> None:
    """Run standalone demonstration of ApiClient against running server."""
    client = ApiClient()
    task_json = (
        '{"code": "460123456789", "output_pdf": "data/client_barcode.pdf"}'
    )
    try:
        user = client._private_api_stable_user_insert("127.0.0.1", "ru-RU")
        print("User saved:", user)
        msg = client._private_api_stable_message_insert(
            user=user["identifier"],
            input_data=task_json,
            description="Client barcode check",
            triggered=1,
        )
        print("Message saved:", msg)
        print("Users on server:", client._private_api_stable_user_query())
        print("Report:", client._private_api_stable_report_query())
    except urllib.error.URLError as exc:
        print("Server connection error:", exc.reason)


if __name__ == "__main__":
    main()
