from aqt.qt import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ..core.session_manager import get_session


class ModelPicker(QWidget):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.models = config["models"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Model:")
        label.setObjectName("ModelLabel")
        layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.setObjectName("ModelPicker")
        for m in self.models:
            self.combo.addItem(m["name"], m["id"])
        layout.addWidget(self.combo, 1)

        idx = config.get("default_model_index", 0)
        session = get_session()
        if config.get("features", {}).get("remember_last_model") and session.current_model:
            for i, m in enumerate(self.models):
                if m["id"] == session.current_model:
                    idx = i
                    break
        self.combo.setCurrentIndex(idx)

    def current_model_id(self):
        return self.combo.currentData()

    def current_temperature(self):
        model_id = self.current_model_id()
        for m in self.models:
            if m["id"] == model_id:
                return m.get("temperature", 0.3)
        return 0.3
