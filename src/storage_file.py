"""File-based persistent storage implementation."""

import json
import os
import time
from typing import Optional

from src.config import (
    DEFAULT_IP,
    DEFAULT_LOCALE,
    ONE,
    TIME_WINDOW_SECONDS,
)
from src.models import Completion, Message, ReportItem, User


class FileStorage:
    """File-backed database storage engine."""

    def __init__(self, filepath: Optional[str] = None):
        """Initialize file storage with specified path."""
        self.filepath = filepath or "storage_data.json"
        self.users: dict[int, User] = {}
        self.messages: dict[int, Message] = {}
        self.completions: dict[int, Completion] = {}
        self._user_seq = ONE
        self._msg_seq = ONE
        self._comp_seq = ONE
        self.load()

    def clear(self) -> None:
        """Clear all records from storage."""
        self.users.clear()
        self.messages.clear()
        self.completions.clear()
        self._user_seq = ONE
        self._msg_seq = ONE
        self._comp_seq = ONE
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    def save(self) -> None:
        """Persist data state to disk."""
        data = {
            "users": [u.__dict__ for u in self.users.values()],
            "messages": [m.__dict__ for m in self.messages.values()],
            "completions": [c.__dict__ for c in self.completions.values()],
            "user_seq": self._user_seq,
            "msg_seq": self._msg_seq,
            "comp_seq": self._comp_seq,
        }
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    def load(self) -> None:
        """Load data state from disk if exists."""
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.users = {
            int(u["identifier"]): User(**u) for u in data.get("users", [])
        }
        self.messages = {
            int(m["identifier"]): Message(**m)
            for m in data.get("messages", [])
        }
        self.completions = {
            int(c["identifier"]): Completion(**c)
            for c in data.get("completions", [])
        }
        self._user_seq = data.get("user_seq", ONE)
        self._msg_seq = data.get("msg_seq", ONE)
        self._comp_seq = data.get("comp_seq", ONE)

    def add_user(
        self, ip: Optional[str] = None, locale: Optional[str] = None
    ) -> User:
        """Create and store new user."""
        uid = self._user_seq
        self._user_seq += ONE
        user = User(
            identifier=uid,
            time=int(time.time()),
            ip=ip or DEFAULT_IP,
            locale=locale or DEFAULT_LOCALE,
        )
        self.users[uid] = user
        self.save()
        return user

    def delete_user(self, identifier: int) -> bool:
        """Remove user by identifier."""
        if identifier in self.users:
            del self.users[identifier]
            self.save()
            return True
        return False

    def get_users(
        self,
        identifier: Optional[int] = None,
        ip: Optional[str] = None,
    ) -> list[User]:
        """Query users by optional filters."""
        result = list(self.users.values())
        if identifier is not None:
            result = [u for u in result if u.identifier == identifier]
        if ip is not None:
            result = [u for u in result if u.ip == ip]
        return result

    def add_message(
        self,
        user_id: int,
        input_data: str,
        description: str,
        triggered: int,
    ) -> Message:
        """Create and store new message."""
        mid = self._msg_seq
        self._msg_seq += ONE
        msg = Message(
            identifier=mid,
            time=int(time.time()),
            input=input_data,
            user=user_id,
            description=description,
            triggered=triggered,
        )
        self.messages[mid] = msg
        self.save()
        return msg

    def delete_message(self, identifier: int) -> bool:
        """Remove message by identifier."""
        if identifier in self.messages:
            del self.messages[identifier]
            self.completions = {
                cid: comp
                for cid, comp in self.completions.items()
                if comp.message != identifier
            }
            self.save()
            return True
        return False

    def get_messages(
        self,
        user_id: Optional[int] = None,
        identifier: Optional[int] = None,
    ) -> list[Message]:
        """Query messages by optional filters."""
        result = list(self.messages.values())
        if user_id is not None:
            result = [m for m in result if m.user == user_id]
        if identifier is not None:
            result = [m for m in result if m.identifier == identifier]
        return result

    def add_completion(
        self,
        message_id: int,
        result: str,
        state: str,
        failure: str,
        cache_hit: int,
        duration: int,
    ) -> Completion:
        """Create and store task completion result."""
        cid = self._comp_seq
        self._comp_seq += ONE
        comp = Completion(
            identifier=cid,
            time=int(time.time()),
            result=result,
            state=state,
            failure=failure,
            message=message_id,
            cache_hit=cache_hit,
            duration=duration,
        )
        self.completions[cid] = comp
        self.save()
        return comp

    def get_completions(
        self,
        message_id: Optional[int] = None,
        identifier: Optional[int] = None,
    ) -> list[Completion]:
        """Query completions by optional filters."""
        result = list(self.completions.values())
        if message_id is not None:
            result = [c for c in result if c.message == message_id]
        if identifier is not None:
            result = [c for c in result if c.identifier == identifier]
        return result

    def get_report(self) -> list[ReportItem]:
        """Calculate report according to variant formula."""
        now = int(time.time())
        cutoff = now - TIME_WINDOW_SECONDS
        recent_messages = [
            m for m in self.messages.values() if m.time >= cutoff
        ]
        joined_right = []
        for msg in recent_messages:
            for comp in self.completions.values():
                if msg.identifier == comp.message:
                    joined_right.append((msg, comp))

        report_items = []
        for msg, comp in joined_right:
            user = self.users.get(msg.user)
            user_ip = user.ip if user is not None else ""
            report_items.append(
                ReportItem(
                    state=comp.state,
                    description=msg.description,
                    ip=user_ip,
                )
            )
        return report_items
