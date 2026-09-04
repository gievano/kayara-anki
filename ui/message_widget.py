import html

from aqt.qt import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
    Qt,
)


def _render(text):
    """Mini markdown: **bold**, `code`, line breaks -> HTML."""
    escaped = html.escape(text)
    out = []
    for line in escaped.split("\n"):
        parts = line.split("`")
        if len(parts) >= 3:
            rebuilt = parts[0]
            for i, part in enumerate(parts[1:]):
                if i % 2 == 0:
                    rebuilt += f"<code>{part}</code>"
                else:
                    rebuilt += part
            line = rebuilt
        if "**" in line:
            chunks = line.split("**")
            rebuilt = chunks[0]
            for i, chunk in enumerate(chunks[1:]):
                if i % 2 == 0:
                    rebuilt += f"<b>{chunk}</b>"
                else:
                    rebuilt += chunk
            line = rebuilt
        out.append(line)
    return "<br>".join(out)


class MessageWidget(QWidget):
    def __init__(self, role, content, on_copy=None, on_save=None,
                 save_enabled=False, parent=None):
        super().__init__(parent)
        self.role = role

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        if role == "user":
            bubble = QFrame()
            bubble.setObjectName("UserBubble")
            inner = QVBoxLayout(bubble)
            inner.setContentsMargins(14, 9, 14, 9)
            label = QLabel(_render(content))
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setOpenExternalLinks(True)
            inner.addWidget(label)
            bubble.setMaximumWidth(560)
            layout.addWidget(bubble)
            return

        # assistant
        header = QLabel("🌸 Kayara")
        header.setObjectName("AiName")
        layout.addWidget(header)

        label = QLabel(_render(content))
        label.setObjectName("AiBody")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setOpenExternalLinks(True)
        layout.addWidget(label)

        if on_copy or (save_enabled and on_save):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            if on_copy:
                copy_btn = QLabel('<a href="copy">📋 Copy</a>')
                copy_btn.setObjectName("MsgAction")
                copy_btn.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                copy_btn.linkActivated.connect(lambda _: on_copy(content))
                row.addWidget(copy_btn)
            if save_enabled and on_save:
                save_btn = QLabel('<a href="save">💾 Simpan ke Kartu</a>')
                save_btn.setObjectName("MsgAction")
                save_btn.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
                save_btn.linkActivated.connect(lambda _: on_save(content))
                row.addWidget(save_btn)
            row.addStretch()
            layout.addLayout(row)


def message_bubble(role, content, on_copy=None, on_save=None, save_enabled=False):
    """Return widget siap ditambahin ke layout chat (sudah dibungkus row align)."""
    w = MessageWidget(role, content, on_copy, on_save, save_enabled)
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    if role == "user":
        h.addStretch()
        h.addWidget(w)
    else:
        h.addWidget(w, 1)
    return row
