class ChatSession:
    def __init__(self):
        self.messages = []
        self.current_model = None

    def add(self, role, content):
        self.messages.append({"role": role, "content": content})

    def history(self):
        return list(self.messages)

    def last_assistant(self):
        for msg in reversed(self.messages):
            if msg["role"] == "assistant":
                return msg["content"]
        return ""

    def clear(self):
        self.messages.clear()

    def export_markdown(self):
        lines = ["# Kayara Chat\n"]
        for msg in self.messages:
            who = "💬 **You**" if msg["role"] == "user" else "🌸 **Kayara**"
            lines.append(f"{who}\n\n{msg['content']}\n\n---\n")
        return "\n".join(lines)


_session = ChatSession()


def get_session():
    return _session
