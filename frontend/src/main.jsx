import React, { useState, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";

const API_BASE = "http://localhost:8000";
const SUPPORTED_TYPES = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"];
const MAX_FILE_SIZE = 50 * 1024 * 1024;

function Sidebar({ activeView, setActiveView }) {
  const items = [
    { id: "workspace", label: "Workspace", icon: "◈" },
    { id: "history", label: "History", icon: "◷" },
    { id: "templates", label: "Templates", icon: "◰" },
    { id: "apikeys", label: "API Keys", icon: "⚷" },
    { id: "help", label: "Help", icon: "?" },
    { id: "logout", label: "Logout", icon: "⏻" },
  ];
  return (
    <aside style={{
      width: 220, background: "#161b22", borderRight: "1px solid #30363d",
      display: "flex", flexDirection: "column", padding: "16px 0"
    }}>
      <div style={{ padding: "0 16px 24px", borderBottom: "1px solid #30363d", marginBottom: 16 }}>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: "#e6edf3" }}>Structure-OCR</h1>
        <span style={{ fontSize: 11, color: "#8b949e", display: "block", marginTop: 4 }}>Phase 1 Demo</span>
      </div>
      <button onClick={() => setActiveView("workspace")} style={{
        background: activeView === "workspace" ? "#262c36" : "transparent",
        color: activeView === "workspace" ? "#e6edf3" : "#8b949e",
        border: "none", padding: "10px 16px", cursor: "pointer", textAlign: "left",
        fontSize: 14, display: "flex", alignItems: "center", gap: 10, width: "100%"
      }}>
        <span>✦</span> New Extraction
      </button>
      <nav style={{ marginTop: 8 }}>
        {items.map(item => (
          <button key={item.id} onClick={() => setActiveView(item.id)} style={{
            background: "transparent", color: "#8b949e", border: "none",
            padding: "10px 16px", cursor: "pointer", textAlign: "left",
            fontSize: 13, display: "flex", alignItems: "center", gap: 10, width: "100%"
          }}>
            <span>{item.icon}</span> {item.label}
          </button>
        ))}
      </nav>
    </aside>
  );
}

function Header() {
  return (
    <header style={{
      height: 56, background: "#161b22", borderBottom: "1px solid #30363d",
      display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px"
    }}>
      <div style={{ display: "flex", gap: 24, fontSize: 13 }}>
        <a href="#" style={{ color: "#8b949e", textDecoration: "none" }}>Backend Config</a>
        <a href="#" style={{ color: "#8b949e", textDecoration: "none" }}>Status</a>
        <a href="#" style={{ color: "#8b949e", textDecoration: "none" }}>Documentation</a>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <button style={{ background: "transparent", border: "none", color: "#8b949e", cursor: "pointer", fontSize: 18 }}>⚙</button>
        <div style={{ width: 32, height: 32, borderRadius: "50%", background: "#6366f1", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 600 }}>U</div>
      </div>
    </header>
  );
}

function UploadCanvas({ file, setFile, preview, setPreview, blocks, onFileSelect }) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) validateAndSetFile(droppedFile);
  }, []);

  const handleDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const handleDragLeave = () => setDragOver(false);

  const validateAndSetFile = (f) => {
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!SUPPORTED_TYPES.includes(ext)) {
      alert("Unsupported file type. Please upload PDF, PNG, JPG, JPEG, WebP, or TXT.");
      return;
    }
    if (f.size > MAX_FILE_SIZE) {
      alert("File too large. Maximum size is 50MB.");
      return;
    }
    setFile(f);
    if (f.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(f);
    } else if (f.type === "application/pdf") {
      setPreview(URL.createObjectURL(f));
    } else {
      setPreview(null);
    }
  };

  const handleChange = (e) => {
    const f = e.target.files?.[0];
    if (f) validateAndSetFile(f);
  };

  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column", background: "#0d1117", padding: 24
    }}>
      <div style={{ marginBottom: 8, fontSize: 13, color: "#8b949e" }}>Source Document</div>
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        style={{
          flex: 1, border: dragOver ? "2px dashed #6366f1" : "2px dashed #30363d",
          borderRadius: 12, display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", cursor: "pointer", transition: "all 0.2s",
          background: dragOver ? "rgba(99, 102, 241, 0.1)" : "#161b22",
          position: "relative", overflow: "hidden"
        }}
      >
        <input ref={fileInputRef} type="file" accept=".pdf,image/*,.txt" onChange={handleChange} style={{ display: "none" }} />
        {!file ? (
          <>
            <div style={{ fontSize: 48, marginBottom: 16, color: "#8b949e" }}>📄</div>
            <div style={{ fontSize: 16, color: "#e6edf3", marginBottom: 8 }}>Drop file here or click to upload</div>
            <div style={{ fontSize: 12, color: "#8b949e" }}>PDF, PNG, JPG, JPEG, WebP, TXT</div>
          </>
        ) : (
          <div style={{ width: "100%", height: "100%", position: "relative" }}>
            {preview && (
              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {file.type.startsWith("image/") ? (
                  <img src={preview} alt="preview" style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
                ) : file.type === "application/pdf" ? (
                  <iframe src={preview} style={{ width: "100%", height: "100%", border: "none" }} />
                ) : null}
              </div>
            )}
            {blocks && blocks.length > 0 && (
              <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none" }}>
                {blocks.filter(b => b.bbox).map((block, i) => (
                  <div key={i} style={{
                    position: "absolute", left: block.bbox[0], top: block.bbox[1],
                    width: block.bbox[2] - block.bbox[0], height: block.bbox[3] - block.bbox[1],
                    border: "2px solid rgba(99, 102, 241, 0.7)", background: "rgba(99, 102, 241, 0.1)",
                    borderRadius: 2
                  }} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResultPanel({ result, loading, error, onExport, onProcess }) {
  const [activeTab, setActiveTab] = useState("layout");
  const tabs = [
    { id: "layout", label: "Layout View" },
    { id: "raw", label: "Raw Text" },
    { id: "table", label: "Table/Excel" },
  ];

  const groupedBlocks = React.useMemo(() => {
    if (!result?.blocks) return {};
    const groups = {};
    result.blocks.forEach(block => {
      const key = block.page || 1;
      if (!groups[key]) groups[key] = [];
      groups[key].push(block);
    });
    return groups;
  }, [result]);

  return (
    <div style={{
      flex: 1, display: "flex", flexDirection: "column", background: "#0d1117", borderLeft: "1px solid #30363d", padding: 24
    }}>
      <div style={{ marginBottom: 8, fontSize: 13, color: "#8b949e" }}>Extraction Results</div>

      <div style={{ display: "flex", gap: 4, marginBottom: 16, background: "#161b22", padding: 4, borderRadius: 8 }}>
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
            flex: 1, padding: "8px 16px", border: "none", borderRadius: 6, cursor: "pointer",
            fontSize: 13, background: activeTab === tab.id ? "#262c36" : "transparent",
            color: activeTab === tab.id ? "#e6edf3" : "#8b949e"
          }}>
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ flex: 1, overflow: "auto", background: "#161b22", borderRadius: 8, padding: 16 }}>
        {loading && <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>Processing document...</div>}
        {error && <div style={{ color: "#ef4444", padding: 16 }}>Error: {error}</div>}
        {!result && !loading && !error && <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>Upload a document and click Process to begin</div>}

        {result && activeTab === "layout" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {Object.entries(groupedBlocks).map(([page, blocks]) => (
              <div key={page} style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>Page {page}</div>
                {blocks.map((block, i) => (
                  <div key={i} style={{
                    background: block.type === "table" ? "rgba(245, 158, 11, 0.1)" : "#262c36",
                    border: block.type === "table" ? "1px solid rgba(245, 158, 11, 0.3)" : "1px solid #30363d",
                    borderRadius: 6, padding: 10, marginBottom: 8, display: "flex", alignItems: "flex-start", gap: 10
                  }}>
                    <span style={{
                      fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "#6366f1", color: "#fff", whiteSpace: "nowrap"
                    }}>{block.type}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap" }}>{block.text}</div>
                      {block.confidence && (
                        <div style={{ fontSize: 11, color: "#8b949e", marginTop: 4 }}>
                          Confidence: {(block.confidence * 100).toFixed(1)}%
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {result && activeTab === "raw" && (
          <pre style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
            {result.text || "No text extracted"}
          </pre>
        )}

        {result && activeTab === "table" && (
          <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
            Table extraction view - blocks with type "table" shown here
          </div>
        )}
      </div>

      {result && (
        <div style={{ marginTop: 16, padding: 12, background: "#161b22", borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 12, color: "#8b949e" }}>
            {result.pages} page(s) • {result.blocks.length} blocks • {result.checksum?.slice(0, 12)}...
          </div>
          <button onClick={onExport} style={{
            padding: "8px 16px", background: "#6366f1", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13
          }}>
            Export JSON
          </button>
        </div>
      )}
    </div>
  );
}

function App() {
  const [activeView, setActiveView] = useState("workspace");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleProcess = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/extract`, { method: "POST", body: formData });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  };

  const handleExport = () => {
    if (!result) return;
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${file?.name || "extraction"}_result.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const avgConfidence = React.useMemo(() => {
    if (!result?.blocks?.length) return 0;
    const withConf = result.blocks.filter(b => b.confidence);
    if (!withConf.length) return 0;
    return withConf.reduce((a, b) => a + b.confidence, 0) / withConf.length * 100;
  }, [result]);

  return (
    <div style={{ display: "flex", height: "100vh", background: "#0f1419" }}>
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <Header />
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          <UploadCanvas
            file={file} setFile={setFile}
            preview={preview} setPreview={setPreview}
            blocks={result?.blocks}
            onFileSelect={() => {}}
          />
          <ResultPanel result={result} loading={loading} error={error} onExport={handleExport} onProcess={handleProcess} />
        </div>
        <div style={{
          height: 40, background: "#161b22", borderTop: "1px solid #30363d",
          display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", fontSize: 12, color: "#8b949e"
        }}>
          <div style={{ display: "flex", gap: 16 }}>
            <span>Engine: {result ? "PaddleOCR" : "Ready"}</span>
            {result && <span>Confidence: {avgConfidence.toFixed(1)}%</span>}
          </div>
          <div style={{ display: "flex", gap: 16 }}>
            {file && <span>File: {file.name}</span>}
            {result && <span>Checksum: {result.checksum?.slice(0, 16)}...</span>}
          </div>
        </div>
      </div>
      {file && (
        <button onClick={handleProcess} disabled={loading} style={{
          position: "fixed", bottom: 80, left: "50%", transform: "translateX(-50%)",
          padding: "14px 32px", background: "#6366f1", color: "#fff", border: "none",
          borderRadius: 50, cursor: loading ? "not-allowed" : "pointer", fontSize: 15, fontWeight: 600,
          boxShadow: "0 4px 20px rgba(99, 102, 241, 0.4)", transition: "all 0.2s"
        }}>
          {loading ? "Processing..." : "Process Document"}
        </button>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App />);
