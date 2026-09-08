from aqt.qt import QApplication

import time

import aqt

_last_clip_change = 0.0


def watch_clipboard():
    """Pantau kapan clipboard terakhir berubah. Panggil sekali saat setup."""
    try:
        QApplication.clipboard().dataChanged.connect(_on_clip_change)
    except Exception:
        pass


def _on_clip_change():
    global _last_clip_change
    _last_clip_change = time.time()


def get_selected_text():
    """Coba ambil selected text dari reviewer/editor/browser, fallback clipboard."""
    try:
        if aqt.mw.reviewer and getattr(aqt.mw.reviewer, "web", None):
            text = aqt.mw.reviewer.web.selectedText()
            if text and text.strip():
                return text.strip()
    except Exception:
        pass

    try:
        editor = _active_editor()
        if editor and getattr(editor, "web", None):
            text = editor.web.selectedText()
            if text and text.strip():
                return text.strip()
    except Exception:
        pass

    try:
        if hasattr(aqt.mw, "browser") and aqt.mw.browser:
            browser = aqt.mw.browser
            if getattr(browser, "editor", None) and browser.editor.web:
                text = browser.editor.web.selectedText()
                if text and text.strip():
                    return text.strip()
    except Exception:
        pass

    # Clipboard fallback — hanya kalau baru di-copy (<30 dtk), clipboard basi ditolak
    try:
        text = QApplication.clipboard().text()
        if text and text.strip() and time.time() - _last_clip_change < 30:
            print(f"[kayara] clipboard fallback: {text[:50]}")
            return text.strip()
    except Exception:
        pass

    print("[kayara] no selected text found")
    return None


def _active_editor():
    editor = None
    if hasattr(aqt.mw, "editor") and aqt.mw.editor:
        editor = aqt.mw.editor
    return editor


def get_current_note():
    """Ambil note aktif dari reviewer/editor/browser untuk Save to Card."""
    try:
        if aqt.mw.reviewer and aqt.mw.reviewer.card:
            return aqt.mw.reviewer.card.note()
    except Exception:
        pass

    try:
        if hasattr(aqt.mw, "editor") and aqt.mw.editor and aqt.mw.editor.note:
            return aqt.mw.editor.note
    except Exception:
        pass

    try:
        if hasattr(aqt.mw, "browser") and aqt.mw.browser:
            selected = aqt.mw.browser.selected_cards()
            if selected:
                card = aqt.mw.col.get_card(selected[0])
                return card.note()
    except Exception:
        pass

    return None


def save_to_field(note, field_name, content, mode):
    """mode: 'append' atau 'replace'. Return True jika sukses."""
    if note is None or field_name not in note:
        return False
    if mode == "replace":
        note[field_name] = content
    else:
        existing = note[field_name] or ""
        sep = "<br>" if existing else ""
        note[field_name] = existing + sep + content
    note.flush()
    aqt.mw.reset()
    return True
