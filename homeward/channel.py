"""Messaging channel. Same interface for Photon 2.0 and for the local stub.

PhotonChannel uses the official Photon 2.0 Python client (photonhq-api) the way
the Photon "Build an iMessage agent" guide does: poll list_messages for new
received messages, answer with send_message using the incoming message's
space id and receiving-agent user id.

StubChannel is for development without a Photon key: the /phone page in the
dashboard plays the patient's phone.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import queue

from . import config


@dataclass
class Incoming:
    id: str
    handle: str          # who sent it (patient phone or email)
    text: str
    space_id: str        # conversation id, needed to reply
    agent_user_id: str   # our line's user id in that conversation, needed to reply


class StubChannel:
    name = "stub"

    def __init__(self) -> None:
        self.inbox: "queue.Queue[Incoming]" = queue.Queue()
        self._n = 0

    def push(self, handle: str, text: str) -> None:
        self._n += 1
        self.inbox.put(Incoming(f"stub-{self._n}-{datetime.now().timestamp()}", handle, text, f"stub-space:{handle}", "stub-agent"))

    def poll(self) -> list[Incoming]:
        items = []
        while not self.inbox.empty():
            items.append(self.inbox.get_nowait())
        return items

    def send(self, space_id: str, agent_user_id: str, text: str, idempotency_key: str, parent_id: str | None = None) -> None:
        pass  # the phone page reads outbound messages from the database

    def typing(self, space_id: str, agent_user_id: str, on: bool) -> None:
        pass


class PhotonChannel:
    name = "photon"

    def __init__(self) -> None:
        from photon_api import Photon  # imported here so the stub runs without the package

        self.photon = Photon(headers={"Authorization": f"Bearer {config.PHOTON_API_KEY}"})
        self.project = config.PHOTON_PROJECT_ID
        # Only look at messages that arrive after start (minus a small overlap).
        self.since = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def poll(self) -> list[Incoming]:
        from photon_api.rpc_generated import ListMessagesInput

        out: list[Incoming] = []
        query = {"createdSince": self.since, "direction": "received", "order": "asc", "pageSize": 100, "platform": "imessage"}
        while True:
            page = self.photon.projects.list_messages(
                ListMessagesInput.model_validate({"path": {"id": self.project}, "query": query})
            )
            for item in page.items:
                m = item.root.root
                if m.status != "received":
                    continue
                sender, agent, space = m.sentBy.root, m.receivedBy.root, m.space.root
                if getattr(sender, "kind", None) != "human" or getattr(agent, "kind", None) != "agent":
                    continue  # never answer our own outbound messages
                if config.PHOTON_AGENT_HANDLE and agent.handle != config.PHOTON_AGENT_HANDLE:
                    continue
                text = _plain_text(m.content)
                if text is None:
                    continue
                out.append(Incoming(m.id, sender.handle, text, space.id, agent.id))
            token = page.nextPageToken
            if not isinstance(token, str):
                break
            query["pageToken"] = token
        return out

    def send(self, space_id: str, agent_user_id: str, text: str, idempotency_key: str, parent_id: str | None = None) -> None:
        from photon_api.rpc_generated import SendMessageInput

        body = {"spaceId": space_id, "senderId": agent_user_id, "content": {"type": "text", "format": "plain", "text": text}}
        if parent_id:
            body["parentMessageId"] = parent_id
        self.photon.projects.send_message(
            SendMessageInput.model_validate(
                {"path": {"id": self.project}, "headers": {"idempotency-key": idempotency_key}, "body": body}
            )
        )

    def typing(self, space_id: str, agent_user_id: str, on: bool) -> None:
        from photon_api.rpc_generated import SetSpaceTypingInput

        try:
            self.photon.projects.set_space_typing(
                SetSpaceTypingInput.model_validate(
                    {"path": {"id": self.project, "spaceId": space_id}, "body": {"senderId": agent_user_id, "typing": on}}
                )
            )
        except Exception:
            pass  # typing indicator is cosmetic


def _plain_text(content) -> str | None:
    c = getattr(content, "root", content)
    if getattr(c, "type", None) == "text":
        return c.text
    return None


def make_channel():
    return PhotonChannel() if config.USE_PHOTON else StubChannel()
