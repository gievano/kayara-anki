import re

import aqt
from aqt.qt import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)


class SaveDialog(QDialog):
    """Modal untuk pilih field target + mode append/replace."""

    def __init__(self, note, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save to Card")
        self.setMinimumWidth(400)
        self.note = note
        self.content = content
        self.field_name = None
        self.mode = "append"

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Target Field:"))
        self.field_combo = QComboBox()
        for field in note.keys():
            self.field_combo.addItem(field)
        layout.addWidget(self.field_combo)

        layout.addWidget(QLabel("Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Append (tambah di bawah)", "append")
        self.mode_combo.addItem("Replace (ganti isi)", "replace")
        layout.addWidget(self.mode_combo)

        preview_label = QLabel("Preview:")
        layout.addWidget(preview_label)
        self.preview = QLineEdit()
        self.preview.setReadOnly(True)
        self.preview.setText(content[:80] + ("..." if len(content) > 80 else ""))
        layout.addWidget(self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_save(self):
        self.field_name = self.field_combo.currentText()
        self.mode = self.mode_combo.currentData()
        self.accept()


class NewNoteDialog(QDialog):
    """Bikin kartu BARU dari jawaban AI — deck asli ga disentuh."""

    def __init__(self, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Save as New Card")
        self.setMinimumWidth(420)
        self.created = False
        col = aqt.mw.col

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Deck:"))
        self.deck_combo = QComboBox()
        self.deck_combo.setEditable(True)
        self.deck_combo.addItems(sorted(col.decks.all_names()))
        layout.addWidget(self.deck_combo)

        layout.addWidget(QLabel("Note Type:"))
        self.model_combo = QComboBox()
        names = sorted(m["name"] for m in col.models.all())
        self.model_combo.addItems(names)
        basic = next((i for i, n in enumerate(names) if n.lower().startswith("basic")), 0)
        self.model_combo.setCurrentIndex(basic)
        layout.addWidget(self.model_combo)

        front, back = self._split(content)
        layout.addWidget(QLabel("Depan:"))
        self.front_edit = QPlainTextEdit(front)
        self.front_edit.setMaximumHeight(90)
        layout.addWidget(self.front_edit)
        layout.addWidget(QLabel("Belakang:"))
        self.back_edit = QPlainTextEdit(back)
        self.back_edit.setMaximumHeight(140)
        layout.addWidget(self.back_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _split(content):
        m = re.search(r"Depan:\s*\n?(.+?)\n\s*Belakang:\s*\n?(.+)", content, re.S | re.I)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        parts = content.strip().split("\n", 1)
        return parts[0], parts[1].strip() if len(parts) > 1 else ""

    def _save(self):
        col = aqt.mw.col
        model = col.models.by_name(self.model_combo.currentText())
        if model is None:
            return
        note = col.new_note(model)
        fields = [f["name"] for f in model["flds"]]
        note[fields[0]] = self.front_edit.toPlainText().strip().replace("\n", "<br>")
        if len(fields) > 1:
            note[fields[1]] = self.back_edit.toPlainText().strip().replace("\n", "<br>")
        deck = col.decks.by_name(self.deck_combo.currentText())
        did = deck["id"] if deck else col.decks.id(self.deck_combo.currentText())
        add_note = getattr(col, "add_note", None) or getattr(col, "addNote")
        try:
            add_note(note, did)
        except TypeError:
            add_note(note)
        col.save()
        aqt.mw.reset()
        self.created = True
        self.accept()
