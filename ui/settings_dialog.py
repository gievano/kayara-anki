"""Dialog pengaturan Kayara: endpoint, API key, model, system prompt.

Data disimpan via mw.addonManager.writeConfig supaya tetap kompatibel
dengan config bawaan Anki (Tools → Add-ons → Config).
"""

import copy

from aqt import mw
from aqt.qt import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    Qt,
    QVBoxLayout,
)

from ..core.api_client import KayaraClient


def parse_models(text):
    """Satu model per baris: id | Nama Tampil | temperature (opsional)."""
    models = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if not parts[0]:
            continue
        temp = 0.3
        if len(parts) > 2 and parts[2]:
            try:
                temp = float(parts[2])
            except ValueError:
                return None, f"Temperature tidak valid di baris: {line}"
        models.append(
            {
                "id": parts[0],
                "name": parts[1] if len(parts) > 1 and parts[1] else parts[0],
                "temperature": temp,
            }
        )
    if not models:
        return None, "Minimal satu model harus diisi."
    return models, None


def models_to_text(models):
    return "\n".join(
        f"{m['id']} | {m.get('name', m['id'])} | {m.get('temperature', 0.3)}"
        for m in models
    )


class SettingsDialog(QDialog):
    def __init__(self, config, addon_name, on_saved=None, parent=None):
        super().__init__(parent or mw)
        self._addon_name = addon_name
        self._on_saved = on_saved
        self._config = copy.deepcopy(config)

        self.setWindowTitle("Kayara — Settings")
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.endpoint = QLineEdit(self._config.get("api_endpoint", ""))
        self.endpoint.setPlaceholderText("http://localhost:20128/v1")
        form.addRow("API endpoint", self.endpoint)

        self.api_key = QLineEdit(self._config.get("api_key", ""))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API key", self.api_key)

        self.models_edit = QPlainTextEdit(models_to_text(self._config.get("models", [])))
        self.models_edit.setPlaceholderText("id-model | Nama Tampil | 0.3")
        self.models_edit.setFixedHeight(110)
        form.addRow("Models\n(id | nama | temp)", self.models_edit)

        self.default_model = QComboBox()
        self._rebuild_default_combo()
        form.addRow("Model default", self.default_model)

        self.prompt_edit = QPlainTextEdit(self._config.get("system_prompt", ""))
        self.prompt_edit.setFixedHeight(140)
        form.addRow("System prompt", self.prompt_edit)

        root.addLayout(form)

        # Test koneksi pakai client sungguhan, model default yang dipilih
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("Test koneksi")
        self.test_btn.clicked.connect(self._test_connection)
        self.test_result = QLabel("")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_result, 1)
        root.addLayout(test_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _rebuild_default_combo(self):
        models, _ = parse_models(self.models_edit.toPlainText())
        models = models or []
        self.default_model.clear()
        for m in models:
            self.default_model.addItem(m["name"], m["id"])
        cur_idx = self._config.get("default_model_index", 0)
        if 0 <= cur_idx < len(models):
            self.default_model.setCurrentIndex(cur_idx)

    def _build_config(self):
        models, err = parse_models(self.models_edit.toPlainText())
        if err:
            return None, err
        cfg = self._config
        cfg["api_endpoint"] = self.endpoint.text().strip()
        cfg["api_key"] = self.api_key.text().strip()
        cfg["models"] = models
        cfg["default_model_index"] = self.default_model.currentIndex()
        cfg["system_prompt"] = self.prompt_edit.toPlainText().strip()
        return cfg, None

    def _test_connection(self):
        cfg, err = self._build_config()
        if err:
            self.test_result.setText(f"❌ {err}")
            return
        self.test_btn.setEnabled(False)
        self.test_result.setText("⏳ Testing…")
        from aqt.qt import QApplication

        QApplication.processEvents()
        # ponytail: test sinkron — request kecil, UI freeze sebentar tak masalah
        client = KayaraClient(cfg, self._addon_name)
        idx = self.default_model.currentIndex()
        model_id = cfg["models"][idx]["id"] if 0 <= idx < len(cfg["models"]) else cfg["models"][0]["id"]
        ok = client.test_connection(model_id)
        self.test_result.setText("✅ Koneksi OK" if ok else "❌ Gagal — cek endpoint/key/model")
        self.test_btn.setEnabled(True)

    def _save(self):
        cfg, err = self._build_config()
        if err:
            from aqt.qt import QMessageBox

            QMessageBox.warning(self, "Kayara", err)
            return
        mw.addonManager.writeConfig(self._addon_name, cfg)
        if self._on_saved:
            self._on_saved(cfg)
        self.accept()
