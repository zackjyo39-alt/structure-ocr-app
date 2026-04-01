import React, { useState } from "react";
import { createRoot } from "react-dom/client";

const API_BASE = "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError("");
    setResult(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/extract`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(await res.text());
      setResult(await res.json());
    } catch (err) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ fontFamily: "ui-sans-serif, system-ui", padding: 24, maxWidth: 960, margin: "0 auto" }}>
      <h1>PaddleOCR 文档提取</h1>
      <p>支持上传文本、图片、拍照或 PDF，返回文本与结构化块。</p>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12 }}>
        <input type="file" accept=".pdf,image/*,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <button disabled={loading} type="submit">{loading ? "处理中..." : "开始提取"}</button>
      </form>
      {error ? <pre style={{ color: "crimson" }}>{error}</pre> : null}
      {result ? (
        <section style={{ marginTop: 24, display: "grid", gap: 16 }}>
          <div>
            <h2>摘要</h2>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
          <div>
            <h2>纯文本</h2>
            <pre style={{ whiteSpace: "pre-wrap" }}>{result.text}</pre>
          </div>
        </section>
      ) : null}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

