/* Kayara — Gemini-style mono dark */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
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

  var py = { send: function(){}, clear: function(){}, copy: function(){}, save: function(){}, saveNew: function(){}, applyAction: function(){}, applyBatch: function(){}, ask: function(){}, undo: function(){}, redo: function(){}, pickModel: function(){} };

  function bindBridge() {
    py = {
      send: function (t) { window.bridge.send(t); },
      clear: function () { window.bridge.clear(); },
      copy: function (t) { window.bridge.copy(t); },
      save: function (t) { window.bridge.save(t); },
      saveNew: function (t) { window.bridge.saveNew(t); },
      applyAction: function (m, f, c) { window.bridge.applyAction(m, f, c); },
      applyBatch: function (s) { window.bridge.applyBatch(s); },
      ask: function (q) { window.bridge.ask(q); },
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

  function addMessage(role, content, anim) {
    var extracted = role === "user" ? { text: content, actions: [] } : extractActions(content);
    var display = extracted.text;
    $("welcome").style.display = "none";
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
    else { bubble.innerHTML = renderMd(display); }
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
    "/tr": "Terjemahkan ke Bahasa Indonesia kalimat/contoh di kartu ini, lalu simpan hasilnya ke field yang paling cocok untuk terjemahan (pakai blok aksi; pilih field dengan mikir, bukan asal yang pertama)."
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
    $("welcome").style.display = "";
    py.clear();
    setStatus("Chat dihapus", "ok");
  };

  window.onResult = function (payload) {
    setBusy(false);
    if (!payload.ok) {
      setStatus(payload.content, "err");
      addMessage("ai", "\u26a0\ufe0f " + payload.content);
      return;
    }
    addMessage("ai", payload.content);
  };

  window.restoreHistory = function (items) {
    items.forEach(function (m) { addMessage(m.role, m.content, false); });
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
