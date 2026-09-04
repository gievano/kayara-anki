/* Kayara UI */
import { motion, AnimatePresence } from "framer-motion";
import { useState, useRef, useEffect } from "react";

export default function KayaraUI() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState([]);
  const [busy, setBusy] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [status, setStatus] = useState("");
  const chatRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    loadModels();
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleClickOutside = (e) => {
    if (menuRef.current && !menuRef.current.contains(e.target)) setShowMenu(false);
  };

  useEffect(() => { if (showMenu) document.addEventListener("mousedown", handleClickOutside); }, [showMenu]);

  useEffect(() => { if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight; }, [messages, busy]);

  async function loadModels() {
    try {
      const result = await window.bridge?.listModels?.();
      setModels(JSON.parse(result || "[]"));
    } catch (e) { setStatus("Failed"); }
  }

  function handleSend() {
    const text = input.trim();
    if (!text || busy) return;
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setInput("");
    setBusy(true);
    py.send(text);
  }

  function pySend(text) { window.bridge?.send(text); }
  const py = { send: pySend, clear: () => window.bridge?.clear(), copy: (t) => window.bridge?.copy(t), save: (t) => window.bridge?.save(t), pickModel: (id) => window.bridge?.pickModel(id) };

  function handleResult(payload) {
    setBusy(false);
    if (!payload.ok) { setStatus(payload.content); return; }
    setMessages(prev => [...prev, { role: "ai", content: payload.content }]);
  }

  function handleClear() { setMessages([]); py.clear(); setStatus("Chat cleared"); }

  function handleModelSelect(id) {
    setModel(id);
    setShowMenu(false);
    py.pickModel(id);
    setStatus("Model: " + (models.find(m => m.id === id)?.name || id));
  }

  function copyToClipboard(text) { py.copy(text); setStatus("Copied!"); setTimeout(() => setStatus(""), 1500); }
  function saveToCard(text) { py.save(text); setStatus("Saved!"); setTimeout(() => setStatus(""), 1500); }

  return (
    <div id="app">
      <motion.div id="topbar" initial={{ y: -20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3 }}>
        <div id="model-picker">
          <button id="model-btn" onClick={() => setShowMenu(!showMenu)}>{model ? models.find(m => m.id === model)?.name : "Model"}</button>
          <AnimatePresence>
            {showMenu && (
              <motion.div id="model-menu" ref={menuRef} initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.15 }}>
                {models.map(m => <div key={m.id} className="model-item" onClick={() => handleModelSelect(m.id)} style={{ padding: "8px 12px", cursor: "pointer", background: m.id === model ? "#1a1a1a" : "transparent", color: m.id === model ? "#fff" : "#e0e0e0" }}>{m.name}</div>)}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        <button id="clear-btn" onClick={handleClear}>Clear</button>
      </motion.div>

      <motion.div id="main">
        <div id="chat-scroll" ref={chatRef}>
          <div id="chat">
            {messages.length === 0 && <motion.div id="welcome" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5 }}>Start chatting with Kayara.</motion.div>}
            <AnimatePresence initial={false}>
              {messages.map((msg, i) => (
                <motion.div key={i} style={{ display: "flex", flexDirection: "column", gap: "6px", alignItems: msg.role === "user" ? "flex-end" : "flex-start" }} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}>
                  {msg.role !== "user" && <div style={{ fontSize: "12px", color: "#888" }}>Kayara</div>}
                  <div style={{ maxWidth: "80%", padding: "10px 14px", borderRadius: "6px", fontSize: "14px", lineHeight: "1.5", background: "transparent", color: "#e0e0e0" }}>{msg.content}</div>
                  {msg.role !== "user" && (
                    <div style={{ display: "flex", gap: "12px", fontSize: "12px" }}>
                      <a href="#" onClick={(e) => { e.preventDefault(); copyToClipboard(msg.content); }}>Copy</a>
                      <a href="#" onClick={(e) => { e.preventDefault(); saveToCard(msg.content); }}>Save</a>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            {busy && (
              <motion.div style={{ display: "flex", flexDirection: "column", gap: "6px", alignItems: "flex-start" }}>
                <div style={{ fontSize: "12px", color: "#888" }}>Kayara</div>
                <div style={{ display: "flex", gap: "4px" }}>
                  <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 0.8, delay: 0 }} style={{ width: "6px", height: "6px", background: "#888", borderRadius: "50%" }} />
                  <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 0.8, delay: 0.2 }} style={{ width: "6px", height: "6px", background: "#888", borderRadius: "50%" }} />
                  <motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ repeat: Infinity, duration: 0.8, delay: 0.4 }} style={{ width: "6px", height: "6px", background: "#888", borderRadius: "50%" }} />
                </div>
              </motion.div>
            )}
          </div>
        </div>
      </motion.div>

      <motion.div id="composer" initial={{ y: 20, opacity: 0 }} animate={{ y: 0, opacity: 1 }} transition={{ duration: 0.3, delay: 0.1 }}>
        <div style={{ maxWidth: "680px", margin: "0 auto", display: "flex", gap: "8px", alignItems: "flex-end" }}>
          <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (!e.shiftKey) handleSend(); } }} placeholder="Type message..." style={{ flex: 1, background: "#0d0d0d", border: "1px solid #2a2a2a", borderRadius: "6px", padding: "10px 12px", color: "#e0e0e0", fontSize: "14px", resize: "none", outline: "none", minHeight: "40px" }} />
          <button onClick={handleSend} disabled={busy || !input.trim()} style={{ width: "40px", height: "40px", background: "#fff", border: "none", borderRadius: "6px", color: "#0d0d0d", cursor: busy || !input.trim() ? "not-allowed" : "pointer" }}>↑</button>
        </div>
      </motion.div>

      <motion.div id="statusbar" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }}>
        <span style={{ fontSize: "12px", color: "#888" }}>{status}</span>
      </motion.div>
    </div>
  );
}
