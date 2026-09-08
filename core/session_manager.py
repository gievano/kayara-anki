import json
import os

_STORE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "user_files"
)
_STORE = os.path.join(_STORE_DIR, "session.json")
_MAX_MESSAGES = 200


class ChatSession:
    def __init__(self):
        self.messages = []
        self.current_model = None
        self._load()

    def _load(self):
        try:
            with open(_STORE, encoding="utf-8") as f:
                data = json.load(f)
            self.messages = data.get("messages", [])[-_MAX_MESSAGES:]
            self.current_model = data.get("current_model")
        except Exception:
            pass

    def _save(self):
        try:
            os.makedirs(_STORE_DIR, exist_ok=True)
            with open(_STORE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "messages": self.messages[-_MAX_MESSAGES:],
                        "current_model": self.current_model,
                    },
                    f,
                    ensure_ascii=False,
                )
        except Exception:
            pass

    def add(self, role, content):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > _MAX_MESSAGES:
            self.messages = self.messages[-_MAX_MESSAGES:]
        self._save()

    def history(self):
        return list(self.messages)

    def last_assistant(self):
        for msg in reversed(self.messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""

    def clear(self):
        self.messages.clear()
        self._save()

    def export_markdown(self):
        lines = ["# Kayara Chat\n"]
        for msg in self.messages:
            who = "💬 **You**" if msg["role"] == "user" else "🌸 **Kayara**"
            lines.append(f"{who}\n\n{msg['content']}\n\n---\n")
        return "\n".join(lines)


_session = ChatSession()


def get_session():
    return _session
