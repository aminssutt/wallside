import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR / "src"))

os.environ.setdefault("GOOGLE_API_KEY", "test-key")

import api  # noqa: E402


def _parse_sse_events(raw_text: str):
    events = []
    for block in raw_text.split("\n\n"):
        if not block.strip():
            continue

        event_name = "message"
        data_lines = []
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            if line.startswith("event:"):
                event_name = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data_lines.append(line.split(":", 1)[1].lstrip())

        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((event_name, payload))
    return events


@pytest.fixture
def client(monkeypatch):
    guide = SimpleNamespace(name="Guide Test", is_indexed=True)
    monkeypatch.setattr(api.guide_manager, "get_guide", lambda slug: guide)
    return api.app.test_client()


def _post_stream(client):
    response = client.post(
        "/api/guides/test-guide/chat/stream",
        json={"message": "Question test", "session_id": "sess-1"},
    )
    assert response.status_code == 200
    return _parse_sse_events(response.get_data(as_text=True))


def test_stream_uses_sync_fallback_without_emitting_error(monkeypatch, client):
    chatbot_calls = []

    class DummyChatbot:
        def chat_stream(self, question, lang=None, session_id="default"):
            yield {"type": "status", "step": "manual_search", "message_id": "mid-1"}
            yield {"type": "status", "step": "generating", "message_id": "mid-1"}
            yield {"type": "chunk", "text": "Bonjour", "message_id": "mid-1"}
            raise TimeoutError("stream timeout")

        def chat(self, question, lang=None, session_id="default"):
            chatbot_calls.append((question, lang, session_id))
            return "Bonjour depuis le fallback.\n\nSources web:\n- https://example.com/help"

    monkeypatch.setattr(api, "get_guide_chatbot", lambda slug: DummyChatbot())

    events = _post_stream(client)
    names = [event_name for event_name, _ in events]
    chunk_payloads = [payload for event_name, payload in events if event_name == "chunk"]
    end_payloads = [payload for event_name, payload in events if event_name == "end"]

    assert chatbot_calls == [("Question test", None, "sess-1")]
    assert "error" not in names
    assert names[0] == "start"
    assert names[-1] == "end"
    assert [payload["text"] for payload in chunk_payloads] == [
        "Bonjour",
        " depuis le fallback.\n\nSources web:\n- https://example.com/help",
    ]
    assert end_payloads == [{
        "success": True,
        "vehicle_name": "Guide Test",
        "message_id": "mid-1",
        "response": "Bonjour depuis le fallback.\n\nSources web:\n- https://example.com/help",
    }]


def test_stream_ignores_post_end_failure_instead_of_emitting_error(monkeypatch, client):
    chatbot = SimpleNamespace(chat_called=False)

    def chat_stream(question, lang=None, session_id="default"):
        yield {"type": "status", "step": "manual_search", "message_id": "mid-2"}
        yield {"type": "chunk", "text": "Texte complet", "message_id": "mid-2"}
        yield {
            "type": "end",
            "response": "Texte complet",
            "message_id": "mid-2",
            "confidence": "medium",
            "fix_mode": False,
        }
        raise RuntimeError("sources failed")

    def chat(question, lang=None, session_id="default"):
        chatbot.chat_called = True
        return "Ne doit pas etre appele"

    chatbot.chat_stream = chat_stream
    chatbot.chat = chat
    monkeypatch.setattr(api, "get_guide_chatbot", lambda slug: chatbot)

    events = _post_stream(client)
    names = [event_name for event_name, _ in events]

    assert names.count("end") == 1
    assert "error" not in names
    assert chatbot.chat_called is False


def test_stream_still_ends_when_stream_and_sync_fallback_both_fail(monkeypatch, client):
    class DummyChatbot:
        def chat_stream(self, question, lang=None, session_id="default"):
            raise RuntimeError("primary stream failed")
            yield  # pragma: no cover

        def chat(self, question, lang=None, session_id="default"):
            raise RuntimeError("sync fallback failed")

    monkeypatch.setattr(api, "get_guide_chatbot", lambda slug: DummyChatbot())

    events = _post_stream(client)
    names = [event_name for event_name, _ in events]
    end_payloads = [payload for event_name, payload in events if event_name == "end"]

    assert names == ["start", "end"]
    assert end_payloads == [{
        "success": True,
        "vehicle_name": "Guide Test",
        "message_id": "",
        "response": "Une erreur interne est survenue. Veuillez reessayer.",
    }]
