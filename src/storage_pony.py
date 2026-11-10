"""PonyORM SQLite database storage layer implementation."""

import time
from typing import Optional

from pony import orm
from pony.orm import (
    Database,
    PrimaryKey,
    Required,
    Set,
    db_session,
    select,
)

from src.config import (
    DEFAULT_IP,
    DEFAULT_LOCALE,
    TIME_WINDOW_SECONDS,
)
from src.models import Completion, Message, ReportItem, User


def define_entities(db: Database) -> None:
    """Define PonyORM database entity classes."""

    class UserEntity(db.Entity):
        """User table entity."""

        _table_ = "users"
        identifier = PrimaryKey(int, auto=True)
        time = Required(int)
        ip = orm.Optional(str, default="", autostrip=False)
        locale = orm.Optional(str, default="", autostrip=False)
        messages = Set("MessageEntity")

    class MessageEntity(db.Entity):
        """Message task table entity."""

        _table_ = "messages"
        identifier = PrimaryKey(int, auto=True)
        time = Required(int)
        input_data = orm.Optional(str, default="", autostrip=False)
        user_id = Required(int)
        user = orm.Optional(UserEntity)
        description = orm.Optional(str, default="", autostrip=False)
        triggered = Required(int)
        completions = Set("CompletionEntity")

    class CompletionEntity(db.Entity):
        """Task completion table entity."""

        _table_ = "completions"
        identifier = PrimaryKey(int, auto=True)
        time = Required(int)
        result = orm.Optional(str, default="", autostrip=False)
        state = Required(str, autostrip=False)
        failure = orm.Optional(str, default="", autostrip=False)
        message = Required(MessageEntity)
        cache_hit = Required(int)
        duration = Required(int)


def create_pony_db(db_path: str = "pony_storage.sqlite3") -> Database:
    """Instantiate and bind Pony Database."""
    db = Database()
    define_entities(db)
    db.bind(provider="sqlite", filename=db_path, create_db=True)
    db.generate_mapping(create_tables=True)
    return db


class PonyStorage:
    """Database storage engine based on SQLite and PonyORM."""

    def __init__(self, db_path: str = "pony_storage.sqlite3"):
        """Initialize Pony database engine with file or memory path."""
        self.db_path = db_path
        self.db = create_pony_db(db_path)
        self.UserEntity = self.db.UserEntity
        self.MessageEntity = self.db.MessageEntity
        self.CompletionEntity = self.db.CompletionEntity

    def clear(self) -> None:
        """Remove all entity records from database."""
        with db_session:
            self.CompletionEntity.select().delete(bulk=True)
            self.MessageEntity.select().delete(bulk=True)
            self.UserEntity.select().delete(bulk=True)

    def add_user(
        self, ip: Optional[str] = None, locale: Optional[str] = None
    ) -> User:
        """Create and persist new User entity."""
        with db_session:
            ent = self.UserEntity(
                time=int(time.time()),
                ip=ip or DEFAULT_IP,
                locale=locale or DEFAULT_LOCALE,
            )
            self.db.commit()
            return User(
                identifier=ent.identifier,
                time=ent.time,
                ip=ent.ip,
                locale=ent.locale,
            )

    def delete_user(self, identifier: int) -> bool:
        """Delete user entity by primary key."""
        with db_session:
            ent = self.UserEntity.get(identifier=identifier)
            if ent is not None:
                ent.delete()
                return True
            return False

    def get_users(
        self,
        identifier: Optional[int] = None,
        ip: Optional[str] = None,
    ) -> list[User]:
        """Query user entities by criteria."""
        with db_session:
            query = select(u for u in self.UserEntity)
            if identifier is not None:
                query = query.filter(lambda u: u.identifier == identifier)
            if ip is not None:
                query = query.filter(lambda u: u.ip == ip)
            return [
                User(
                    identifier=u.identifier,
                    time=u.time,
                    ip=u.ip,
                    locale=u.locale,
                )
                for u in query[:]
            ]

    def add_message(
        self,
        user_id: int,
        input_data: str,
        description: str,
        triggered: int,
    ) -> Message:
        """Create and persist new Message entity."""
        with db_session:
            user_ent = self.UserEntity.get(identifier=user_id)
            msg_ent = self.MessageEntity(
                time=int(time.time()),
                input_data=input_data,
                user_id=user_id,
                user=user_ent,
                description=description,
                triggered=triggered,
            )
            self.db.commit()
            return Message(
                identifier=msg_ent.identifier,
                time=msg_ent.time,
                input=msg_ent.input_data,
                user=msg_ent.user_id,
                description=msg_ent.description,
                triggered=msg_ent.triggered,
            )

    def delete_message(self, identifier: int) -> bool:
        """Delete message entity by primary key."""
        with db_session:
            msg_ent = self.MessageEntity.get(identifier=identifier)
            if msg_ent is not None:
                msg_ent.delete()
                return True
            return False

    def get_messages(
        self,
        user_id: Optional[int] = None,
        identifier: Optional[int] = None,
    ) -> list[Message]:
        """Query message entities by criteria."""
        with db_session:
            query = select(m for m in self.MessageEntity)
            if user_id is not None:
                query = query.filter(lambda m: m.user_id == user_id)
            if identifier is not None:
                query = query.filter(lambda m: m.identifier == identifier)
            return [
                Message(
                    identifier=m.identifier,
                    time=m.time,
                    input=m.input_data,
                    user=m.user_id,
                    description=m.description,
                    triggered=m.triggered,
                )
                for m in query[:]
            ]

    def add_completion(
        self,
        message_id: int,
        result: str,
        state: str,
        failure: str,
        cache_hit: int,
        duration: int,
    ) -> Completion:
        """Create and persist task completion entity."""
        with db_session:
            msg_ent = self.MessageEntity.get(identifier=message_id)
            if msg_ent is None:
                raise ValueError("Message not found")
            c_ent = self.CompletionEntity(
                time=int(time.time()),
                result=result,
                state=state,
                failure=failure,
                message=msg_ent,
                cache_hit=cache_hit,
                duration=duration,
            )
            self.db.commit()
            return Completion(
                identifier=c_ent.identifier,
                time=c_ent.time,
                result=c_ent.result,
                state=c_ent.state,
                failure=c_ent.failure,
                message=message_id,
                cache_hit=c_ent.cache_hit,
                duration=c_ent.duration,
            )

    def get_completions(
        self,
        message_id: Optional[int] = None,
        identifier: Optional[int] = None,
    ) -> list[Completion]:
        """Query completion entities by criteria."""
        with db_session:
            query = select(c for c in self.CompletionEntity)
            if message_id is not None:
                query = query.filter(
                    lambda c: c.message.identifier == message_id
                )
            if identifier is not None:
                query = query.filter(lambda c: c.identifier == identifier)
            return [
                Completion(
                    identifier=c.identifier,
                    time=c.time,
                    result=c.result,
                    state=c.state,
                    failure=c.failure,
                    message=c.message.identifier,
                    cache_hit=c.cache_hit,
                    duration=c.duration,
                )
                for c in query[:]
            ]

    def get_report(self) -> list[ReportItem]:
        """Generate relational algebra report according to formula (15)."""
        now = int(time.time())
        cutoff = now - TIME_WINDOW_SECONDS
        with db_session:
            recent_msgs = select(
                m for m in self.MessageEntity if m.time >= cutoff
            )
            report_items = []
            for msg in recent_msgs:
                for comp in msg.completions:
                    user_ip = msg.user.ip if msg.user is not None else ""
                    report_items.append(
                        ReportItem(
                            state=comp.state,
                            description=msg.description,
                            ip=user_ip,
                        )
                    )
            return report_items


def main() -> None:
    """Demonstrate PonyORM database operations."""
    print("Testing PonyStorage with SQLite...")
    st = PonyStorage(":memory:")
    u = st.add_user("127.0.0.1", "ru-RU")
    print(f"Created user: id={u.identifier}, ip={u.ip}")
    msg = st.add_message(u.identifier, "460123456789", "Milk", 1)
    print(f"Created message: id={msg.identifier}, desc={msg.description}")
    comp = st.add_completion(msg.identifier, "SUCCESS", "SUCCESS", "", 0, 15)
    print(f"Created completion: id={comp.identifier}, state={comp.state}")
    rep = st.get_report()
    print(f"Report query items count: {len(rep)}")
    for item in rep:
        print(
            f"  state={item.state}, desc={item.description}, ip={item.ip}"
        )
    print("PonyStorage test successfully passed!")


if __name__ == "__main__":
    main()
