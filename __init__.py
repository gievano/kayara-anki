from aqt import gui_hooks, mw
from aqt.qt import QAction, QKeySequence

from .core.session_manager import get_session
from .core.text_handler import get_selected_text
from .ui.chat_dialog import ChatDialog

ADDON_NAME = "kayara"

_dialog_instance = None


def get_config():
    return mw.addonManager.getConfig(ADDON_NAME)


def open_chat(initial_text=None):
    global _dialog_instance
    if _dialog_instance is None:
        config = get_config()
        _dialog_instance = ChatDialog(config, ADDON_NAME, initial_text=initial_text, parent=mw)
    else:
        if initial_text:
            _dialog_instance.set_input(initial_text)
    _dialog_instance.show()
    _dialog_instance.raise_()
    _dialog_instance.activateWindow()


def on_shortcut_open():
    open_chat(initial_text=None)


def on_shortcut_with_selection():
    selected = None
    try:
        selected = get_selected_text()
    except Exception:
        pass
    open_chat(initial_text=selected)


def open_settings():
    from .ui.settings_dialog import SettingsDialog

    def _apply(cfg):
        if _dialog_instance is not None:
            _dialog_instance.apply_config(cfg)

    dlg = SettingsDialog(get_config(), ADDON_NAME, on_saved=_apply, parent=mw)
    dlg.exec()


def setup_menu():
    config = get_config()
    shortcut_open = config.get("keybinds", {}).get("open_empty", "Ctrl+K")
    shortcut_selection = config.get("keybinds", {}).get("open_with_selection", "Ctrl+L")

    menu = mw.form.menubar.addMenu("🌸 Kayara")
    
    action_open = QAction("Open Chat", mw)
    action_open.setShortcut(QKeySequence(shortcut_open))
    action_open.setStatusTip(f"Buka Kayara ({shortcut_open})")
    action_open.triggered.connect(on_shortcut_open)
    menu.addAction(action_open)
    
    action_selection = QAction("Open with Selection", mw)
    action_selection.setShortcut(QKeySequence(shortcut_selection))
    action_selection.setStatusTip(f"Buka Kayara dengan teks terpilih ({shortcut_selection})")
    action_selection.triggered.connect(on_shortcut_with_selection)
    menu.addAction(action_selection)

    action_settings = QAction("Settings…", mw)
    action_settings.setStatusTip("Pengaturan Kayara (endpoint, API key, model, prompt)")
    action_settings.triggered.connect(open_settings)
    menu.addAction(action_settings)


gui_hooks.profile_did_open.append(setup_menu)
