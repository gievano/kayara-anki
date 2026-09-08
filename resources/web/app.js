/* Kayara — Gemini-style mono dark */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  // ponytail: debug — error JS tampil di status bar (QWebEngine ga ada devtools)
  window.onerror = function (msg, src, line) {
    var el = document.getElementById("status");
    if (el) { el.textContent = "JS error: " + msg + " @" + line; el.className = "err"; }
  };
  var chatEl = $("chat");
  var scrollEl = $("chat-scroll");
  var inputEl = $("input");
  var sendBtn = $("send");
  var statusEl = $("status");
  var clearBtn = $("clear-btn");
  var modelBtn = $("model-btn");
  var modelLabel = $("model-label");
  var modelMenu = $("model-menu");
  var typingEl = $("typing");

  var py = { send: function(){}, clear: function(){}, copy: function(){}, save: function(){}, saveNew: function(){}, applyAction: function(){}, applyBatch: function(){}, cancelBatch: function(){}, ask: function(){}, undo: function(){}, redo: function(){}, retry: function(){}, pickModel: function(){} };

  function bindBridge() {
    py = {
      send: function (t) { window.bridge.send(t); },
      clear: function () { window.bridge.clear(); },
      copy: function (t) { window.bridge.copy(t); },
      save: function (t) { window.bridge.save(t); },
      saveNew: function (t) { window.bridge.saveNew(t); },
      applyAction: function (m, f, c) { window.bridge.applyAction(m, f, c); },
      applyBatch: function (s) { window.bridge.applyBatch(s); },
      cancelBatch: function () { window.bridge.cancelBatch(); },
      ask: function (q) { window.bridge.ask(q); },
      retry: function () { window.bridge.retry(); },
      undo: function () { window.bridge.undo(); },
      redo: function () { window.bridge.redo(); },
      pickModel: function (id) { window.bridge.pickModel(id); }
    };
    if (window.KAYARA_PENDING_INPUT) {
      setInput(window.KAYARA_PENDING_INPUT);
      window.KAYARA_PENDING_INPUT = null;
    }
  }

  var models = [];
  try { models = JSON.parse(decodeURIComponent(escape(atob(window.KAYARA_MODELS)))); } catch(e) {}
  var currentModel = window.KAYARA_CURRENT_MODEL || "";
  var busy = false;

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ponytail: render markdown-lite → HTML; escape dulu biar aman
  function renderMd(t) {
    var h = esc(t);
    h = h.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/\*(.+?)\*/g, "<em>$1</em>");
    h = h.replace(/`(.+?)`/g, '<code class="inline">$1</code>');
    h = h.replace(/^#{1,6}\s*(.+)$/gm, "<strong>$1</strong>");
    h = h.replace(/^&gt;\s?(.*)$/gm, '<span class="quote">$1</span>');
    h = h.replace(/^\s*[-*_]{3,}\s*$/gm, "");
    h = h.replace(/^\|(.+)\|$/gm, function (m, inner) {
      if (/^[\s\-:|]+$/.test(inner)) return "";
      return inner.split("|").map(function (c) { return c.trim(); }).join("  ·  ");
    });
    h = h.replace(/^\s*[-*]\s+/gm, "• ");
    h = h.replace(/\n{3,}/g, "\n\n");
    return h.trim();
  }

  // versi plain untuk copy/save
  function stripMd(t) {
    var d = document.createElement("div");
    d.innerHTML = renderMd(t);
    return d.textContent;
  }

  // ponytail: ekstrak blok aksi — SAVE/SET (chip), BATCH (chip), ASK (auto-run)
  function extractActions(text) {
    var found = [];
    var clean = text.replace(/\[\[\s*(SAVE|SET)\s*:\s*([^\]]+?)\s*\]\]\s*([\s\S]*?)\[\[\s*\/\s*\1\s*\]\]/gi,
      function (whole, mode, field, val) {
        found.push({ mode: mode.toUpperCase(), field: field.trim(), content: val.trim() });
        return "";
      });
    if (!found.length) {
      clean = clean.replace(/\[\[\s*(SAVE|SET)\s*:\s*([^\]]+?)\s*\]\]\s*([\s\S]*)$/i,
        function (whole, mode, field, val) {
          found.push({ mode: mode.toUpperCase(), field: field.trim(), content: val.trim() });
          return "";
        });
    }
    clean = clean.replace(/\[\[\s*BATCH\s*\]\]\s*([\s\S]*?)\[\[\s*\/\s*BATCH\s*\]\]/gi,
      function (whole, body) {
        found.push({ mode: "BATCH", field: "", content: body.trim() });
        return "";
      });
    clean = clean.replace(/\[\[\s*ASK\s*:\s*([^\]]+?)\s*\]\]/gi,
      function (whole, q) {
        found.push({ mode: "ASK", field: "", content: q.trim() });
        return "";
      });
    clean = clean.replace(/\[\[\s*CARD\s*\]\]/gi,
      function () {
        found.push({ mode: "CARD", field: "", content: "" });
        return "";
      });
    return { text: clean.trim(), actions: found };
  }

  // ponytail: tool-call chip 2 fase (pending → done) — kerja AI keliatan ala CLI
  function tcLabel(query) {
    if (query === "current") return "Melihat kartu yang tampil";
    if (query.indexOf("decks:") === 0) return "Mencari deck: " + query.slice(6);
    if (query.indexOf("find:") === 0) return "Mencari note: " + query.slice(5);
    if (query.indexOf("note:") === 0) return "Membuka note #" + query.slice(5);
    if (query.indexOf("notetypes") === 0) return "Membaca daftar notetype";
    return query;
  }

  window.addToolCall = function (id, query) {
    var el = document.createElement("div");
    el.className = "msg toolcall";
    el.id = "tc-" + id;
    var chip = document.createElement("div");
    chip.className = "tc-chip";
    chip.innerHTML = '<span class="tc-spin"></span><span class="tc-label"></span>' +
      '<span class="tc-summary"></span><span class="tc-chev">▸</span>';
    chip.querySelector(".tc-label").textContent = tcLabel(query);
    chip.onclick = function () { el.classList.toggle("open"); };
    el.appendChild(chip);
    var pre = document.createElement("pre");
    pre.className = "tc-detail";
    el.appendChild(pre);
    chatEl.appendChild(el);
    scrollBottom();
  };

  window.updateToolCall = function (id, result) {
    var el = document.getElementById("tc-" + id);
    if (!el) return;
    el.classList.add("done");
    el.querySelector(".tc-detail").textContent = result;
    var lines = (result || "").split("\n").filter(function (l) { return l.trim(); });
    var first = (lines[0] || "").trim();
    el.querySelector(".tc-summary").textContent =
      lines.length + " baris" + (first ? " · " + first.slice(0, 42) : "");
    scrollBottom();
  };

  function addMessage(role, content, anim, frozen) {
    var extracted = role === "user" ? { text: content, actions: [] } : extractActions(content);
    var display = extracted.text;
    // ponytail: reply cuma berisi blok ASK → tool-call block yang bicara, skip bubble kosong
    if (role !== "user" && !display && extracted.actions.length && extracted.actions.every(function (a) { return a.mode === "ASK"; })) return;
    var welcomeEl = $("welcome");
    if (welcomeEl) welcomeEl.style.display = "none";
    var msg = document.createElement("div");
    msg.className = "msg " + role;
    if (role !== "user") {
      var name = document.createElement("div");
      name.className = "name";
      name.innerHTML = '<span class="avatar">🌸</span>Kayara';
      msg.appendChild(name);
    }
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    if (role === "user") { bubble.textContent = content; }
    else if (display) { bubble.innerHTML = renderMd(display); }
    else {
      // ponytail: teks kosong tapi ada chip aksi — kasih hint, jangan blank
      bubble.innerHTML = '<span class="empty-hint">⚙️ aksi siap dikonfirmasi ↓</span>';
    }
    msg.appendChild(bubble);
    var actions = document.createElement("div");
    actions.className = "actions";
    var copyLink = document.createElement("a");
    copyLink.textContent = "Copy";
    copyLink.onclick = function () { py.copy(stripMd(content)); setStatus("Copied", "ok"); };
    actions.appendChild(copyLink);
    if (role !== "user") {
      var saveLink = document.createElement("a");
      saveLink.textContent = "Save";
      saveLink.onclick = function () { py.save(stripMd(content)); setStatus("Saved", "ok"); };
      actions.appendChild(saveLink);
      extracted.actions.forEach(function (a) {
        if (a.mode === "ASK") { py.ask(a.content); return; }
        var applyLink = document.createElement("a");
        applyLink.className = "apply";
        if (a.mode === "CARD") {
          // ponytail: +Card cuma muncul kalau AI menandai jawaban layak jadi kartu ([[CARD]])
          applyLink.textContent = "+Card";
          applyLink.onclick = function () { py.saveNew(stripMd(content)); };
        } else if (a.mode === "BATCH") {
          applyLink.textContent = "⚡ Batch";
          applyLink.onclick = function () { py.applyBatch(a.content); };
        } else {
          applyLink.textContent = (a.mode === "SET" ? "✏️→ " : "💾→ ") + a.field;
          applyLink.onclick = function () { py.applyAction(a.mode, a.field, a.content); };
        }
        if (frozen) {
          // ponytail: chip dari riwayat sesi lama — nonaktif, cegah double-apply
          applyLink.classList.add("done");
          applyLink.onclick = function () { setStatus("Aksi dari riwayat — sudah tidak aktif", ""); };
        }
        actions.appendChild(applyLink);
      });
    }
    msg.appendChild(actions);
    chatEl.appendChild(msg);
    if (anim !== false) {
      msg.style.opacity = "0";
      msg.style.transform = "translateY(12px)";
      requestAnimationFrame(function () {
        msg.style.transition = "opacity 0.2s, transform 0.2s";
        msg.style.opacity = "1";
        msg.style.transform = "translateY(0)";
      });
    }
    scrollBottom();
  }

  function showTyping() { typingEl.style.display = "flex"; scrollBottom(); }
  function hideTyping() { typingEl.style.display = "none"; }
  function scrollBottom() { requestAnimationFrame(function () { scrollEl.scrollTop = scrollEl.scrollHeight; }); }

  var statusTimer = null;
  function setStatus(text, kind) {
    statusEl.textContent = text;
    statusEl.className = kind || "";
    if (statusTimer) clearTimeout(statusTimer);
    if (text && kind !== "busy") {
      statusTimer = setTimeout(function () { statusEl.textContent = ""; statusEl.className = ""; }, 2500);
    }
  }

  // ponytail: progress bar batch — dipanggil dari Python via runJavaScript
  window.batchProgress = function (i, total, label) {
    var bar = document.getElementById("batchbar");
    if (!bar) return;
    if (total <= 0) { bar.style.display = "none"; return; }
    bar.style.display = "block";
    var pct = Math.round((i / total) * 100);
    document.getElementById("bb-fill").style.width = pct + "%";
    document.getElementById("bb-text").textContent = label || "⚡ Batch berjalan…";
    document.getElementById("bb-count").textContent = i + " / " + total + " · " + pct + "%";
    var cancelBtn = document.getElementById("bb-cancel");
    if (cancelBtn) {
      cancelBtn.style.display = i >= total ? "none" : "inline";
      cancelBtn.onclick = function () { py.cancelBatch(); };
    }
    if (i >= total) {
      setTimeout(function () { bar.style.display = "none"; }, 4000);
    }
  };

  var SEND_ICON = sendBtn.innerHTML;
  function setBusy(v) {
    busy = v;
    sendBtn.disabled = v;
    sendBtn.innerHTML = v ? "\u2026" : SEND_ICON;
    if (v) { showTyping(); setStatus("Kayara sedang mengetik\u2026", "busy"); }
    else { hideTyping(); setStatus(""); }
  }

  function renderModelMenu() {
    modelMenu.innerHTML = "";
    models.forEach(function (m) {
      var item = document.createElement("div");
      item.className = "model-item" + (m.id === currentModel ? " active" : "");
      item.textContent = m.name;
      item.onclick = function (e) {
        e.stopPropagation();
        currentModel = m.id;
        modelLabel.textContent = m.name;
        toggleMenu(false);
        py.pickModel(m.id);
      };
      modelMenu.appendChild(item);
    });
    var active = models.find(function (m) { return m.id === currentModel; });
    modelLabel.textContent = active ? active.name : "Model";
  }

  function toggleMenu(open) {
    if (open === undefined) open = modelMenu.style.display !== "block";
    modelMenu.style.display = open ? "block" : "none";
  }

  // ponytail: dipanggil Python setelah Settings disimpan — refresh picker tanpa reload
  window.applyModels = function () {
    try { models = JSON.parse(decodeURIComponent(escape(atob(window.KAYARA_MODELS)))); } catch (e) {}
    if (!models.find(function (m) { return m.id === currentModel; })) {
      currentModel = models.length ? models[0].id : "";
    }
    renderModelMenu();
  };

  modelBtn.onclick = function (e) { e.stopPropagation(); toggleMenu(); };
  document.addEventListener("click", function () { toggleMenu(false); });
  modelMenu.onclick = function (e) { e.stopPropagation(); };

  function autoGrow() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 140) + "px";
  }

  // ponytail: shortcut prompt instan; nambah command = tambah 1 baris di sini
  var SLASH = {
    "/tr": "Terjemahkan ke Bahasa Indonesia kalimat/contoh di kartu ini, lalu simpan hasilnya ke field yang paling cocok untuk terjemahan (pakai blok aksi; pilih field dengan mikir, bukan asal yang pertama).",
    "/gj": "Jelaskan grammar/pola kalimat di kartu ini poin per poin, singkat per poin, Bahasa Indonesia. Kalau kartu ini kosakata (bukan kalimat), langsung jelaskan grammar dari kalimat contohnya; kalau tidak ada kalimat contoh, jelaskan penggunaan kosakatanya. Jangan minta izin dulu.",
    "/kartu": "Bikin 1 kartu serupa dari pola kartu ini (kosakata/grammar beda, tingkat kesulitan sama), layak jadi kartu baru."
  };

  function send() {
    var text = inputEl.value.trim();
    if (!text || busy) return;
    var parts = text.split(/\s+/);
    var expanded = SLASH[parts[0]];
    if (expanded) {
      text = expanded + (parts.length > 1 ? "\n" + parts.slice(1).join(" ") : "");
    }
    inputEl.value = "";
    autoGrow();
    addMessage("user", text);
    py.send(text);
  }

  sendBtn.onclick = send;
  inputEl.onkeydown = function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };
  inputEl.oninput = autoGrow;

  clearBtn.onclick = function () {
    chatEl.innerHTML = "";
    var welcomeEl = $("welcome");
    if (welcomeEl) welcomeEl.style.display = "";
    py.clear();
    setStatus("Chat dihapus", "ok");
  };

  // ponytail: streaming — bubble tumbuh per-chunk, finishStream render final + aksi
  var streamEl = null;
  window.beginStream = function () {
    hideTyping();
    var welcomeEl = $("welcome");
    if (welcomeEl) welcomeEl.style.display = "none";
    var msg = document.createElement("div");
    msg.className = "msg ai streaming";
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    msg.appendChild(bubble);
    chatEl.appendChild(msg);
    streamEl = bubble;
    scrollBottom();
  };
  window.appendStream = function (t) {
    if (!streamEl) window.beginStream();
    streamEl.textContent += t;
    scrollBottom();
  };
  window.finishStream = function (content) {
    if (streamEl) { streamEl.parentNode.remove(); streamEl = null; }
    if (content) addMessage("ai", content);
  };

  window.onResult = function (payload) {
    setBusy(false);
    if (!payload.ok) {
      window.finishStream("");
      setStatus(payload.content, "err");
      addMessage("ai", "⚠️ " + payload.content);
      // ponytail: retry manual — error API bisa transient
      var acts = chatEl.lastChild.querySelector(".actions");
      var r = document.createElement("a");
      r.className = "apply";
      r.textContent = "↻ Coba lagi";
      r.onclick = function () { r.style.display = "none"; py.retry(); };
      acts.appendChild(r);
      return;
    }
    addMessage("ai", payload.content);
  };

  window.restoreHistory = function (items) {
    items.forEach(function (m) {
      if (!m.content || !m.content.trim()) return;  // ponytail: jangan render bubble kosong dari history
      addMessage(m.role, m.content, false, true);
    });
  };

  window.clearChat = function () {
    chatEl.innerHTML = "";
    var welcomeEl = $("welcome");
    if (welcomeEl) welcomeEl.style.display = "none";
  };

  window.setStatus = setStatus;
  window.setBusy = setBusy;
  window.setInput = function (text) { inputEl.value = text; autoGrow(); inputEl.focus(); };
  window.appendInput = function (text) {
    inputEl.value = inputEl.value ? inputEl.value + "\n" + text : text;
    autoGrow(); inputEl.focus();
  };

  function init() {
    renderModelMenu();
    document.querySelectorAll(".chip").forEach(function (chip) {
      chip.onclick = function () {
        setInput(chip.getAttribute("data-q"));
      };
    });
    // ponytail: quick-action chip langsung kirim (bukan cuma isi input)
    document.querySelectorAll(".qchip").forEach(function (chip) {
      var q = chip.getAttribute("data-q");
      if (!q) return;
      chip.onclick = function () {
        inputEl.value = q;
        send();
      };
    });
    $("btn-undo").onclick = function () { py.undo(); };
    $("btn-redo").onclick = function () { py.redo(); };
    inputEl.focus();
  }

  window.onBridgeReady = function() { bindBridge(); init(); };
  if (window.bridge) { bindBridge(); init(); }
})();
