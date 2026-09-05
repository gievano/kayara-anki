import base64
import json
import os
import re

from aqt.qt import (
    QDialog,
    QObject,
    QUrl,
    QWebChannel,
    QVBoxLayout,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)

try:
    from aqt.qt import QWebEngineView
except ImportError:
    QWebEngineView = None

from ..core.api_client import KayaraClient
from ..core.session_manager import get_session
from ..core.text_handler import get_current_note, save_to_field
from .save_dialog import NewNoteDialog, SaveDialog

WEB_DIR = os.path.join(os.path.dirname(__file__), "..", "resources", "web")


class _Worker(QThread):
    def __init__(self, client, messages, model_id, temperature, parent=None):
        super().__init__(parent)
        self.client = client
        self.messages = messages
        self.model_id = model_id
        self.temperature = temperature
        self.result = None

    def run(self):
        self.result = self.client.send_message(
            self.messages, self.model_id, self.temperature
        )


class _BatchWorker(QThread):
    """Worker batch: cuma panggil API per kartu (tanpa sentuh collection di thread).
    Hasil diterapkan di main thread saat finished."""

    progress = pyqtSignal(int, int)

    def __init__(self, client, items, model_id, temperature, task, parent=None):
        super().__init__(parent)
        self.client = client
        self.items = items  # list of (nid, source_text)
        self.model_id = model_id
        self.temperature = temperature
        self.task = task
        self.results = []  # list of (nid, output or None)
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        total = len(self.items)
        for i, (nid, source) in enumerate(self.items):
            if self.cancelled:
                break
            messages = [
                {"role": "system", "content": self.task + " Output: hanya hasil akhir, tanpa penjelasan, tanpa markdown."},
                {"role": "user", "content": source},
            ]
            r = self.client.send_message(messages, self.model_id, self.temperature)
            self.results.append((nid, r.content.strip() if r.success else None))
            self.progress.emit(i + 1, total)


class _Bridge(QObject):
    # anchor:js-call-python
    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog

    @pyqtSlot(str)
    def send(self, text):
        self._dialog._send(text)

    @pyqtSlot()
    def clear(self):
        self._dialog._clear()

    @pyqtSlot(str)
    def copy(self, text):
        from aqt.qt import QApplication

        QApplication.clipboard().setText(text)
        self._dialog._push_status("âœ… Tersalin", "ok")

    @pyqtSlot(str)
    def save(self, text):
        self._dialog._save_to_card(text)

    @pyqtSlot(str)
    def saveNew(self, text):
        self._dialog._save_new_card(text)

    @pyqtSlot(str, str, str)
    def applyAction(self, mode, field, content):
        self._dialog._apply_action(mode, field, content)

    @pyqtSlot()
    def undo(self):
        self._dialog._undo()

    @pyqtSlot()
    def redo(self):
        self._dialog._redo()

    @pyqtSlot(str)
    def ask(self, query):
        self._dialog._exec_ask(query)

    @pyqtSlot(str)
    def applyBatch(self, spec):
        self._dialog._apply_batch(spec)

    @pyqtSlot()
    def cancelBatch(self):
        self._dialog._cancel_batch()

    @pyqtSlot(str)
    def pickModel(self, model_id):
        self._dialog._persist_model(model_id)


class ChatDialog(QDialog):
    def __init__(self, config, addon_name, initial_text=None, parent=None):
        super().__init__(parent or None)
        self.config = config
        self.addon_name = addon_name
        self._initial_text = initial_text
        self.session = get_session()
        self.client = KayaraClient(config, addon_name)
        self._worker = None
        # ponytail: undo/redo stack aksi SAVE/SET — in-memory, hilang saat Anki tutup
        self._undo_stack = []
        self._redo_stack = []
        self._ask_depth = 0
        self._batch_counter = 0
        self._batch_worker = None

        self.setWindowTitle("Kayara")
        self.setWindowFlags(Qt.WindowType.Window)

        # ponytail: side panel ala VS Code — shrink window Anki, dock kanan
        from aqt.qt import QGuiApplication
        import aqt

        self._mw = aqt.mw
        self._mw_was_maximized = self._mw.isMaximized()
        self._mw_orig_geometry = self._mw.geometry()

        screen = QGuiApplication.primaryScreen().availableGeometry()
        w = config["ui"].get("window_width", 420)
        self.resize(w, screen.height())
        self.move(screen.right() - w + 1, screen.top())

        if self._mw_was_maximized:
            self._mw.showNormal()
        self._mw.setGeometry(
            screen.left(), screen.top(), screen.width() - w, screen.height()
        )

        if QWebEngineView is None:
            raise RuntimeError(
                "QWebEngineView tidak tersedia di build Anki ini. "
                "Install: pip install pyqtwebengine di env Anki."
            )

        self._build_ui()
        self._restore_history()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        self.bridge = _Bridge(self)

        channel = QWebChannel(self.view.page())
        channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(channel)

        root.addWidget(self.view)
        self._load_page()

    def _load_page(self):
        html_path = os.path.join(WEB_DIR, "index.html")
        with open(html_path, encoding="utf-8") as f:
            html = f.read()

        # Inject config + qwebchannel.js via base64 (avoid file:// asset issues)
        models = self.config.get("models", [])
        current = self.session.current_model
        if current not in [m["id"] for m in models]:
            idx = self.config.get("default_model_index", 0)
            current = models[idx]["id"] if models else ""
        self.session.current_model = current

        inject = (
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
            "<script>"
            f"window.KAYARA_MODELS='{base64.b64encode(json.dumps(models).encode()).decode()}';"
            f"window.KAYARA_CURRENT_MODEL={json.dumps(current)};"
            f"window.KAYARA_PENDING_INPUT={json.dumps(self._initial_text or '')};"
            "</script>"
        )
        html = html.replace("</head>", inject + "</head>")

        self.view.loadFinished.connect(self._on_page_loaded)
        self.view.setHtml(html, QUrl.fromLocalFile(WEB_DIR + os.sep))

    def _on_page_loaded(self, ok):
        if not ok:
            return
        self.view.page().runJavaScript(
            "new QWebChannel(qt.webChannelTransport, function(ch){"
            " window.bridge = ch.objects.bridge;"
            " if (window.onBridgeReady) window.onBridgeReady();"
            "});"
        )

    def _restore_history(self):
        # ponytail: skip pesan kosong + feedback mesin [HASIL ASK] — bukan buat UI
        history = [
            m
            for m in self.session.history()
            if m["content"].strip() and not m["content"].startswith("[HASIL ASK ")
        ]
        if not history:
            return
        payload = json.dumps(history)
        QTimer.singleShot(
            600,
            lambda: self.view.page().runJavaScript(
                f"if (window.restoreHistory) window.restoreHistory({payload})"
            ),
        )

    # ---------- python-side actions ----------

    def _eval_js(self, script):
        self.view.page().runJavaScript(script)

    def set_input(self, text):
        payload = json.dumps(text or "")
        self._eval_js(
            f"window.appendInput ? window.appendInput({payload})"
            f" : (window.KAYARA_PENDING_INPUT = {payload})"
        )

    def _push_status(self, text, kind=""):
        self._eval_js(
            f"window.setStatus && window.setStatus({json.dumps(text)}, {json.dumps(kind)})"
        )

    def apply_config(self, config):
        """Terapkan config baru dari dialog Settings tanpa restart/reload."""
        self.config = config
        self.client = KayaraClient(config, self.addon_name)
        models = config.get("models", [])
        b64 = base64.b64encode(json.dumps(models).encode()).decode()
        self._eval_js(
            f"window.KAYARA_MODELS='{b64}';"
            "window.applyModels && window.applyModels();"
        )

    def _send(self, text):
        if self._worker is not None and self._worker.isRunning():
            self._push_status("â³ Tunggu respons selesaiâ€¦", "err")
            return

        self.session.add("user", text)
        self._ask_depth = 0
        self._request()

    def _card_context(self):
        """Isi note yang lagi tampil (reviewer/editor/browser) sebagai konteks AI."""
        import re

        note = get_current_note()
        if not note:
            return ""
        parts = []
        try:
            parts.append(f"[notetype: {note.note_type()['name']}]")
        except Exception:
            pass
        for name, val in note.items():
            txt = re.sub(r"<[^>]+>", " ", val)
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                parts.append(f"{name}: {txt}")
        return " | ".join(parts)[:800]

    def _deck_context(self):
        """Info deck & state Anki biar AI aware posisi user."""
        try:
            col = self._mw.col
            deck = col.decks.current()
            counts = col.sched.counts()
            return (
                f"Deck aktif: {deck.get('name', '?')} | "
                f"due: new={counts[0]} learn={counts[1]} review={counts[2]}"
            )
        except Exception:
            return ""

    def _request(self):
        sys_prompt = self.config.get("system_prompt", "")
        extras = []
        deck_ctx = self._deck_context()
        if deck_ctx:
            extras.append("State Anki user: " + deck_ctx)
        ctx = self._card_context()
        if ctx:
            extras.append("Kartu di layar: " + ctx)
        if extras:
            sys_prompt += "\n\nKonteks:\n" + "\n".join(extras)
        messages = [{"role": "system", "content": sys_prompt}] + self.session.history()
        models = self.config.get("models", [])
        current = self.session.current_model
        model_cfg = next(
            (m for m in models if m["id"] == current), models[0] if models else None
        )
        temp = model_cfg.get("temperature", 0.3) if model_cfg else 0.3

        self._eval_js("window.setBusy && window.setBusy(true)")
        self._worker = _Worker(self.client, messages, current, temp, self)
        self._worker.finished.connect(self._on_response)
        self._worker.start()

    def _on_response(self):
        result = self._worker.result if self._worker else None
        self._worker = None

        if result is None:
            self._push_result(False, "Terjadi kesalahan yang tidak diketahui.", False)
            return

        if not result.success:
            self._push_result(False, result.error, result.retryable)
            return

        self.session.add("assistant", result.content)
        self._push_result(True, result.content, False)
        # Agent loop: AI minta data via [[ASK:...]] → eksekusi → kirim balik ke AI
        asks = re.findall(r"\[\[\s*ASK\s*:\s*([^\]]+?)\s*\]\]", result.content, re.I)
        if asks and self._ask_depth < 2:
            self._ask_depth += 1
            outputs = []
            for q in asks[:3]:
                self._push_status(f"🔍 {q}", "")
                res = self._run_query(q.strip())
                outputs.append(f"[HASIL ASK {q}]\n{res}")
                # tampilkan sebagai tool-call block persisten (transparansi ala CLI)
                self.view.page().runJavaScript(
                    f"addToolCall({json.dumps(q.strip())}, {json.dumps(res)})"
                )
            self.session.add("user", "\n\n".join(outputs))
            self._request()

    def _exec_ask(self, query):
        """Dipanggil dari JS (auto) kalau ada blok ASK di luar loop respons."""
        # ponytail: loop utama jalan di _on_response; slot ini cadangan manual
        self._push_status(f"🔍 {query}", "")

    def _run_query(self, q):
        """Eksekusi query read-only terhadap collection. Return string ringkas."""
        import re as _re

        col = self._mw.col
        try:
            if q.lower().startswith("decks:"):
                kw = q[6:].strip().lower()
                names = [n for n in col.decks.all_names() if kw in n.lower()]
                return "Deck: " + (", ".join(names[:30]) or "(tidak ada yang cocok)")
            if q.lower().startswith("notetypes"):
                out = []
                for m in col.models.all_names_and_ids():
                    model = col.models.get(m.id)
                    fields = ", ".join(f["name"] for f in model["flds"])
                    out.append(f"{m.name} [{fields}]")
                return "Notetype:\n" + "\n".join(out[:20])
            if q.lower().startswith("find:"):
                raw = q[5:].strip().replace("notetype:", "note:")
                nids = col.find_notes(raw)[:20]
                if not nids:
                    return "Tidak ada note yang cocok."
                lines = []
                for nid in nids:
                    note = col.get_note(nid)
                    first = _re.sub(r"<[^>]+>", "", note.fields[0])[:40]
                    lines.append(f"id={nid} [{note.note_type()['name']}] {first}")
                return "\n".join(lines)
            if q.lower().startswith("note:"):
                note = col.get_note(int(q[5:].strip()))
                parts = []
                for name, val in note.items():
                    txt = _re.sub(r"<[^>]+>", " ", val).strip()
                    parts.append(f"{name}: {txt}")
                return "\n".join(parts)[:500]
            return "Query tidak dikenal. Format: decks:x / notetypes / find:x / note:id"
        except Exception as e:
            return f"Error query: {e}"

    def _push_result(self, ok, content, retryable):
        payload = json.dumps({"ok": ok, "content": content, "retryable": retryable})
        self._eval_js(f"window.onResult && window.onResult({payload})")

    def _clear(self):
        self.session.clear()

    def _save_to_card(self, content):
        note = get_current_note()
        if note is None:
            self._push_status("âŒ Tidak ada kartu aktif", "err")
            return
        dialog = SaveDialog(note, content, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.field_name:
            success = save_to_field(note, dialog.field_name, content, dialog.mode)
            msg = "âœ… Tersimpan" if success else "âŒ Gagal menyimpan"
            self._push_status(msg, "ok" if success else "err")

    def _save_new_card(self, content):
        dialog = NewNoteDialog(content, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.created:
            self._push_status("✅ Kartu baru tersimpan", "ok")

    def _apply_action(self, mode, field, content):
        """Eksekusi blok [[SAVE]]/[[SET]] dari AI — dengan konfirmasi."""
        from aqt.qt import QMessageBox

        note = get_current_note()
        if note is None:
            self._push_status("❌ Tidak ada kartu aktif", "err")
            return
        if field not in note:
            self._push_status(
                f"❌ Field '{field}' tidak ada. Ada: {', '.join(note.keys())}", "err"
            )
            return
        old_value = note[field] or ""
        # ponytail: guard anti-duplikat — konten yang sama persis jangan di-append 2x
        if mode != "SET" and content.strip() and content.strip() in old_value:
            self._push_status(f"ℹ️ Sudah ada di {field}, skip", "ok")
            return
        verb = "GANTI seluruh isi" if mode == "SET" else "Tambahkan ke"
        ans = QMessageBox.question(
            self,
            "Kayara",
            f"{verb} field '{field}' kartu ini?\n\n{content[:200]}",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        html = content.replace("\n", "<br>")
        if mode == "SET":
            note[field] = html
        else:
            note[field] = old_value + ("<br>" if old_value else "") + html
        note.flush()
        self._undo_stack.append((None, note.id, field, old_value))
        self._redo_stack.clear()
        self._mw.reset()
        self._push_status(f"✅ Tersimpan ke {field}", "ok")

    def _apply_batch(self, spec):
        """Eksekusi blok [[BATCH]]: transformasi massal per kartu via API."""
        from aqt.qt import QMessageBox

        cfg = {}
        for line in spec.strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                cfg[k.strip().lower()] = v.strip()

        target = cfg.get("target")
        source = cfg.get("source")
        task = cfg.get("task", "Terjemahkan ke Bahasa Indonesia")
        if not target or not source:
            self._push_status("❌ BATCH butuh source: dan target:", "err")
            return

        col = self._mw.col
        parts = []
        if cfg.get("deck"):
            parts.append(f'"deck:{cfg["deck"]}"')
        if cfg.get("notetype"):
            parts.append(f'"note:{cfg["notetype"]}"')
        query = " ".join(parts)
        if not query:
            self._push_status("❌ BATCH butuh deck: atau notetype:", "err")
            return

        nids = col.find_notes(query)
        if not nids:
            self._push_status(f"❌ Tidak ada kartu cocok: {query}", "err")
            return

        # Validasi field di kartu pertama
        first = col.get_note(nids[0])
        if source not in first or target not in first:
            self._push_status(
                f"❌ Field tidak ada. Ada: {', '.join(first.keys())}", "err"
            )
            return

        preview = re.sub(r"<[^>]+>", "", first[source])[:100]
        mins = len(nids) * 5 // 60
        ans = QMessageBox.question(
            self,
            "Kayara — Konfirmasi Batch",
            f"Proses {len(nids)} kartu ({query})?\n\n"
            f"Task: {task}\n{source} → {target}\n\n"
            f"Preview: {preview}…\n\n"
            f"Estimasi ±{max(1, mins)} menit. Bisa di-undo 1 klik (↶).",
        )
        if ans != QMessageBox.StandardButton.Yes:
            return

        # Ambil teks sumber di main thread; worker cuma call API
        # ponytail: kartu dengan source kosong diskip — jangan bakar API call
        items = []
        self._batch_skipped = 0
        for nid in nids:
            text = re.sub(r"<[^>]+>", "", col.get_note(nid)[source]).strip()
            if text:
                items.append((nid, text))
            else:
                self._batch_skipped += 1
        if not items:
            self._push_status("❌ Semua kartu sumbernya kosong", "err")
            return

        models = self.config.get("models", [])
        current = self.session.current_model
        model_cfg = next(
            (m for m in models if m["id"] == current), models[0] if models else None
        )
        temp = model_cfg.get("temperature", 0.3) if model_cfg else 0.3

        self._batch_counter += 1
        self._batch_target = target
        self._current_batch_id = self._batch_counter

        total_n = len(items)
        self.view.page().runJavaScript(
            f'batchProgress(0, {total_n}, "⚡ Batch mulai…")'
        )
        self._batch_worker = _BatchWorker(
            self.client, items, current, temp, task, self
        )
        self._batch_worker.progress.connect(
            lambda i, total: self.view.page().runJavaScript(
                f"batchProgress({i}, {total})"
            )
        )
        self._batch_worker.finished.connect(self._on_batch_done)
        self._batch_worker.start()

    def _cancel_batch(self):
        worker = getattr(self, "_batch_worker", None)
        if worker is not None:
            worker.cancel()
            self._push_status("⏹ Membatalkan batch…", "busy")

    def _on_batch_done(self):
        worker = self._batch_worker
        self._batch_worker = None
        if worker is None:
            return
        col = self._mw.col
        bid = self._current_batch_id
        target = self._batch_target
        ok_count = fail_count = 0
        for nid, output in worker.results:
            if output is None:
                fail_count += 1
                continue
            try:
                note = col.get_note(nid)
            except Exception:
                fail_count += 1
                continue
            old = note[target] or ""
            note[target] = old + ("<br>" if old else "") + output.replace("\n", "<br>")
            note.flush()
            self._undo_stack.append((bid, nid, target, old))
            ok_count += 1
        self._redo_stack.clear()
        self._mw.reset()
        skipped = getattr(self, "_batch_skipped", 0)
        skip_txt = f", {skipped} dilewati (kosong)" if skipped else ""
        if worker.cancelled:
            self.view.page().runJavaScript("batchProgress(0, 0)")
            self._push_status(
                f"⏹ Batch dibatalkan ({len(worker.results)}/{len(worker.items)} terproses): "
                f"{ok_count} diterapkan, {fail_count} gagal{skip_txt}. Undo: tombol ↶",
                "err",
            )
            return
        self._push_status(
            f"✅ Batch selesai: {ok_count} berhasil, {fail_count} gagal{skip_txt}. "
            f"Undo semua: tombol ↶",
            "ok",
        )

    def _undo(self):
        self._restore(self._undo_stack, self._redo_stack, "↶ Dikembalikan")

    def _redo(self):
        self._restore(self._redo_stack, self._undo_stack, "↷ Diulang")

    def _restore(self, src, dst, label):
        if not src:
            self._push_status("Tidak ada yang bisa di-undo/redo", "err")
            return
        first = src.pop()
        group = [first]
        # ponytail: entri batch (batch_id bukan None) di-undo sebagai satu grup
        if first[0] is not None:
            while src and src[-1][0] == first[0]:
                group.append(src.pop())
        restored = 0
        for bid, nid, field, value in group:
            try:
                note = self._mw.col.get_note(nid)
            except Exception:
                continue
            dst.append((bid, nid, field, note[field] or ""))
            note[field] = value
            note.flush()
            restored += 1
        if not restored:
            self._push_status("❌ Kartu sudah tidak ada", "err")
            return
        self._mw.reset()
        suffix = f" ({restored} kartu)" if restored > 1 else ""
        self._push_status(f"{label}{suffix}", "ok")

    def _persist_model(self, model_id):
        if self.config.get("features", {}).get("remember_last_model"):
            self.session.current_model = model_id

    def closeEvent(self, event):
        if getattr(self, "_mw_orig_geometry", None):
            if self._mw_was_maximized:
                self._mw.showMaximized()
            else:
                self._mw.setGeometry(self._mw_orig_geometry)
            self._mw_orig_geometry = None
        event.accept()
