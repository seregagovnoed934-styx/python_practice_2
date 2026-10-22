"""Data models and XML serialization utilities."""

from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import Optional

from src.config import ZERO


@dataclass
class User:
    """User entity model."""

    identifier: int
    time: int
    ip: str
    locale: str


@dataclass
class Message:
    """Message task entity model."""

    identifier: int
    time: int
    input: str
    user: int
    description: str
    triggered: int


@dataclass
class Completion:
    """Task completion result entity model."""

    identifier: int
    time: int
    result: str
    state: str
    failure: str
    message: int
    cache_hit: int
    duration: int


@dataclass
class ReportItem:
    """Report projection item model."""

    state: str
    description: str
    ip: str


def user_to_xml_element(user: User) -> ET.Element:
    """Convert User instance to XML element."""
    elem = ET.Element("user")
    ET.SubElement(elem, "identifier").text = str(user.identifier)
    ET.SubElement(elem, "time").text = str(user.time)
    ET.SubElement(elem, "ip").text = user.ip
    ET.SubElement(elem, "locale").text = user.locale
    return elem


def message_to_xml_element(msg: Message) -> ET.Element:
    """Convert Message instance to XML element."""
    elem = ET.Element("message")
    ET.SubElement(elem, "identifier").text = str(msg.identifier)
    ET.SubElement(elem, "time").text = str(msg.time)
    ET.SubElement(elem, "input").text = msg.input
    ET.SubElement(elem, "user").text = str(msg.user)
    ET.SubElement(elem, "description").text = msg.description
    ET.SubElement(elem, "triggered").text = str(msg.triggered)
    return elem


def completion_to_xml_element(comp: Completion) -> ET.Element:
    """Convert Completion instance to XML element."""
    elem = ET.Element("completion")
    ET.SubElement(elem, "identifier").text = str(comp.identifier)
    ET.SubElement(elem, "time").text = str(comp.time)
    ET.SubElement(elem, "result").text = comp.result
    ET.SubElement(elem, "state").text = comp.state
    ET.SubElement(elem, "failure").text = comp.failure
    ET.SubElement(elem, "message").text = str(comp.message)
    ET.SubElement(elem, "cache_hit").text = str(comp.cache_hit)
    ET.SubElement(elem, "duration").text = str(comp.duration)
    return elem


def serialize_user(user: User) -> str:
    """Serialize User instance to XML string."""
    elem = user_to_xml_element(user)
    return ET.tostring(elem, encoding="utf-8").decode("utf-8")


def serialize_users(users: list[User]) -> str:
    """Serialize list of users to XML string."""
    root = ET.Element("users")
    for u in users:
        root.append(user_to_xml_element(u))
    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def serialize_messages(messages: list[Message]) -> str:
    """Serialize list of messages to XML string."""
    root = ET.Element("messages")
    for m in messages:
        root.append(message_to_xml_element(m))
    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def serialize_completions(completions: list[Completion]) -> str:
    """Serialize list of completions to XML string."""
    root = ET.Element("completions")
    for c in completions:
        root.append(completion_to_xml_element(c))
    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def serialize_report(items: list[ReportItem]) -> str:
    """Serialize report items to XML string."""
    root = ET.Element("report")
    for it in items:
        sub = ET.SubElement(root, "item")
        ET.SubElement(sub, "state").text = it.state
        ET.SubElement(sub, "description").text = it.description
        ET.SubElement(sub, "ip").text = it.ip
    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def serialize_action_status(status: str, detail: Optional[str] = None) -> str:
    """Serialize action status message to XML."""
    root = ET.Element("response")
    ET.SubElement(root, "status").text = status
    if detail is not None:
        ET.SubElement(root, "detail").text = detail
    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def parse_xml_user(xml_text: str) -> dict:
    """Parse user payload dictionary from XML text."""
    root = ET.fromstring(xml_text)
    ip_node = root.find("ip")
    loc_node = root.find("locale")
    ip_val = ip_node.text if ip_node is not None and ip_node.text else ""
    loc_val = loc_node.text if loc_node is not None and loc_node.text else ""
    return {"ip": ip_val, "locale": loc_val}


def parse_xml_message(xml_text: str) -> dict:
    """Parse message payload dictionary from XML text."""
    root = ET.fromstring(xml_text)
    u_node = root.find("user")
    inp_node = root.find("input")
    d_node = root.find("description")
    tr_node = root.find("triggered")
    user_id = int(u_node.text) if u_node is not None and u_node.text else ZERO
    inp_val = inp_node.text if inp_node is not None and inp_node.text else ""
    d_val = d_node.text if d_node is not None and d_node.text else ""
    tr_val = (
        int(tr_node.text) if tr_node is not None and tr_node.text else ZERO
    )
    return {
        "user": user_id,
        "input": inp_val,
        "description": d_val,
        "triggered": tr_val,
    }
