import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { marked } from "marked";

marked.setOptions({ gfm: true, breaks: false });

const API_BASE = "http://localhost:8000";
const SUPPORTED_TYPES = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"];
const MAX_FILE_SIZE = 50 * 1024 * 1024;

function bboxToRect(bbox) {
  if (!bbox || bbox.length < 4) return null;
  if (bbox.length >= 8) {
    const xs = [bbox[0], bbox[2], bbox[4], bbox[6]];
    const ys = [bbox[1], bbox[3], bbox[5], bbox[7]];
    return {
      minX: Math.min(...xs),
      minY: Math.min(...ys),
      maxX: Math.max(...xs),
      maxY: Math.max(...ys),
    };
  }
  return { minX: bbox[0], minY: bbox[1], maxX: bbox[2], maxY: bbox[3] };
}

function pointInRect(x, y, r) {
  return x >= r.minX && x <= r.maxX && y >= r.minY && y <= r.maxY;
}

function computeBlockSpans(text, blocks) {
  if (!text || !blocks?.length) return blocks.map(() => ({ start: null, end: null }));
  let pos = 0;
  return blocks.map((block) => {
    const chunk = block.text ?? "";
    if (!chunk) return { start: null, end: null };
    let idx = text.indexOf(chunk, pos);
    if (idx === -1) idx = text.indexOf(chunk);
    if (idx === -1) return { start: null, end: null };
    const span = { start: idx, end: idx + chunk.length };
    pos = idx + chunk.length;
    return span;
  });
}

function lineColAtOffset(text, offset) {
  if (offset == null || offset < 0 || !text) return { line: null, col: null };
  const head = text.slice(0, offset);
  const lines = head.split("\n");
  const line = lines.length;
  const col = (lines[lines.length - 1] ?? "").length + 1;
  return { line, col };
}

function offsetFromPointInTextElement(el, clientX, clientY) {
  if (!el) return null;
  let range = null;
  if (document.caretRangeFromPoint) {
    range = document.caretRangeFromPoint(clientX, clientY);
  } else if (document.caretPositionFromPoint) {
    const pos = document.caretPositionFromPoint(clientX, clientY);
    if (pos?.offsetNode) {
      range = document.createRange();
      range.setStart(pos.offsetNode, pos.offset);
      range.setEnd(pos.offsetNode, pos.offset);
    }
  }
  if (!range || !el.contains(range.startContainer)) return null;
  if (range.startContainer.nodeType !== Node.TEXT_NODE) return null;
  let off = 0;
  const walk = (node) => {
    if (node === range.startContainer) {
      off += range.startOffset;
      return true;
    }
    if (node.nodeType === Node.TEXT_NODE) {
      off += node.textContent.length;
      return false;
    }
    for (const c of node.childNodes) {
      if (walk(c)) return true;
    }
    return false;
  };
  walk(el);
  return off;
}

const STRUCTURE_COLORS = {
  title: "#3b82f6",
  caption: "#8b5cf6",
  text: "#6366f1",
  table: "#f59e0b",
  figure: "#22c55e",
  header: "#6b7280",
  footer: "#6b7280",
  equation: "#ec4899",
  footnote: "#9ca3af",
  list: "#14b8a6",
};

function getStructureColor(block) {
  const st = block.structure_type || block.type;
  return STRUCTURE_COLORS[st] || STRUCTURE_COLORS.text;
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function computeFontSize(bbox, hierarchyLevel) {
  if (bbox && bbox.length >= 4) {
    const height = bbox[3] - bbox[1];
    const base = Math.max(10, Math.min(height * 0.65, 36));
    if (hierarchyLevel != null && hierarchyLevel <= 1) return Math.min(base * 1.4, 36);
    if (hierarchyLevel != null && hierarchyLevel === 2) return Math.min(base * 1.2, 28);
    return base;
  }
  const sizeMap = { 0: 28, 1: 22, 2: 18, 3: 16, 4: 13, 5: 12, 6: 11 };
  return sizeMap[hierarchyLevel] || 13;
}

function StructureView({ blocks, pageInfos, highlightedBlockIndex, setHighlightedBlockIndex }) {
  const canvasRef = useRef(null);
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });
  const [scale, setScale] = useState(1);

  const pageInfo = pageInfos?.[0] || null;
  const pageW = pageInfo?.width || 1200;
  const pageH = pageInfo?.height || 1600;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setCanvasSize({ w: entry.contentRect.width, h: entry.contentRect.height });
      }
    });
    ro.observe(canvas);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (canvasSize.w > 0 && pageW > 0) {
      setScale(canvasSize.w / pageW);
    }
  }, [canvasSize.w, pageW]);

  const blocksWithBbox = blocks.filter(b => b.bbox && b.bbox.length >= 4);
  const blocksWithoutBbox = blocks.filter(b => !b.bbox || b.bbox.length < 4);

  if (!blocks.length) {
    return (
      <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
        No structure data available for reconstruction
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <style>{`
        .markdown-content h1, .markdown-content h2, .markdown-content h3,
        .markdown-content h4, .markdown-content h5, .markdown-content h6 {
          margin: 0 0 4px 0;
          font-weight: 700;
          line-height: 1.2;
        }
        .markdown-content h1 { font-size: 1.4em; }
        .markdown-content h2 { font-size: 1.2em; }
        .markdown-content h3 { font-size: 1.1em; }
        .markdown-content p { margin: 0 0 4px 0; }
        .markdown-content ul, .markdown-content ol {
          margin: 0;
          padding-left: 16px;
          list-style-position: inside;
        }
        .markdown-content li { margin: 2px 0; }
        .markdown-content code {
          background: #f0f0f0;
          padding: 1px 3px;
          border-radius: 2px;
          font-family: ui-monospace, monospace;
          font-size: 0.9em;
        }
        .markdown-content pre {
          background: #f5f5f5;
          padding: 6px;
          border-radius: 3px;
          overflow: auto;
          font-size: 0.85em;
        }
        .markdown-content pre code {
          background: transparent;
          padding: 0;
        }
        .markdown-content blockquote {
          margin: 4px 0;
          padding-left: 8px;
          border-left: 3px solid #ddd;
          color: #555;
        }
        .markdown-content table {
          width: 100%;
          border-collapse: collapse;
          margin: 4px 0;
          font-size: 0.9em;
        }
        .markdown-content th, .markdown-content td {
          border: 1px solid #ccc;
          padding: 2px 4px;
        }
        .markdown-content th {
          background: #e8e8e8;
          font-weight: 600;
        }
        .markdown-content hr {
          margin: 4px 0;
          border: none;
          border-top: 1px solid #ddd;
        }
        .markdown-content a {
          color: #6366f1;
          text-decoration: underline;
        }
        .markdown-content strong { font-weight: 700; }
        .markdown-content em { font-style: italic; }
      `}</style>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#6b7280" }}>
        <span>Pixel-level reconstruction</span>
        <span>·</span>
        <span>{blocksWithBbox.length} positioned blocks</span>
        {blocksWithoutBbox.length > 0 && (
          <>
            <span>·</span>
            <span>{blocksWithoutBbox.length} without coordinates</span>
          </>
        )}
      </div>
      <div
        ref={canvasRef}
        style={{
          position: "relative",
          width: "100%",
          minHeight: pageH * scale,
          background: "#ffffff",
          borderRadius: 4,
          overflow: "auto",
        }}
      >
        <div style={{ position: "relative", width: pageW, height: pageH }}>
          {blocksWithBbox.map((block, idx) => {
            const globalIdx = blocks.indexOf(block);
            const isHighlighted = highlightedBlockIndex === globalIdx;
            const r = bboxToRect(block.bbox);
            if (!r) return null;
            const left = r.minX;
            const top = r.minY;
            const w = r.maxX - r.minX;
            const h = r.maxY - r.minY;
            const fontSize = computeFontSize(block.bbox, block.hierarchy_level);
            const color = getStructureColor(block);

            if (block.table_html) {
              return (
                <div key={idx} style={{ position: "absolute", left, top, width: w, height: h, overflow: "hidden" }}>
                  <div
                    className="structure-table"
                    style={{ background: "transparent" }}
                    dangerouslySetInnerHTML={{ __html: block.table_html }}
                  />
                  <style>{`
                    .structure-table table { width: 100%; border-collapse: collapse; font-size: ${Math.max(9, fontSize * 0.8)}px; }
                    .structure-table th, .structure-table td { border: 1px solid #ccc; padding: 2px 4px; color: #1a1a1a; }
                    .structure-table th { background: #e8e8e8; font-weight: 600; }
                  `}</style>
                </div>
              );
            }

            return (
              <div
                key={idx}
                onMouseEnter={() => setHighlightedBlockIndex(globalIdx)}
                onMouseLeave={() => setHighlightedBlockIndex(null)}
                style={{
                  position: "absolute",
                  left,
                  top,
                  width: w,
                  minHeight: h,
                  padding: "1px 2px",
                  background: isHighlighted ? hexToRgba(color, 0.15) : "transparent",
                  border: isHighlighted ? `1px solid ${color}` : "1px solid transparent",
                  borderRadius: 1,
                  transition: "background 0.1s, border-color 0.1s",
                  cursor: "pointer",
                  overflow: "hidden",
                }}
              >
                <div
                  className="markdown-content"
                  style={{
                    fontSize,
                    lineHeight: 1.3,
                    color: "#1a1a1a",
                    fontFamily: block.structure_type === "equation" ? "Georgia, serif" : "inherit",
                    fontWeight: (block.hierarchy_level != null && block.hierarchy_level <= 1) ? 700 : (block.hierarchy_level === 2 ? 600 : 400),
                    wordBreak: "break-word",
                  }}
                  dangerouslySetInnerHTML={{ __html: marked.parse(block.text || "") }}
                />
              </div>
            );
          })}
          {blocksWithBbox.length === 0 && (
            <div style={{ padding: 24, color: "#666", fontSize: 14, textAlign: "center" }}>
              No blocks with bounding box coordinates available.
              Structure reconstruction requires bbox data from OCR.
            </div>
          )}
        </div>
      </div>
      {blocksWithoutBbox.length > 0 && (
        <div style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
          <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>
            Blocks without coordinates ({blocksWithoutBbox.length})
          </div>
          {blocksWithoutBbox.slice(0, 10).map((block, i) => (
            <div key={i} style={{ fontSize: 12, color: "#6b7280", marginBottom: 4, paddingLeft: (block.hierarchy_level || 0) * 8 }}>
              <span style={{ color: getStructureColor(block), marginRight: 6 }}>●</span>
              {block.text?.slice(0, 80)}{block.text?.length > 80 ? "..." : ""}
            </div>
          ))}
          {blocksWithoutBbox.length > 10 && (
            <div style={{ fontSize: 11, color: "#4b5563" }}>... and {blocksWithoutBbox.length - 10} more</div>
          )}
        </div>
      )}
    </div>
  );
}

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

function BboxOverlay({ blocks, naturalW, naturalH, highlightedBlockIndex, displayW, displayH, pageNum }) {
  if (!naturalW || !naturalH || !displayW || !displayH) return null;
  const sx = displayW / naturalW;
  const sy = displayH / naturalH;
  return (
    <div style={{
      position: "absolute", left: 0, top: 0, width: displayW, height: displayH,
      pointerEvents: "none",
    }}>
      {blocks.map((block, globalIdx) => {
        if (pageNum != null && block.page !== pageNum) return null;
        const r = bboxToRect(block.bbox);
        if (!r) return null;
        const left = r.minX * sx;
        const top = r.minY * sy;
        const w = (r.maxX - r.minX) * sx;
        const h = (r.maxY - r.minY) * sy;
        const on = highlightedBlockIndex === globalIdx;
        const color = getStructureColor(block);
        return (
          <div
            key={globalIdx}
            style={{
              position: "absolute",
              left, top, width: w, height: h,
              border: on ? "2px solid rgba(34, 197, 94, 0.95)" : `2px solid ${hexToRgba(color, 0.55)}`,
              background: on ? "rgba(34, 197, 94, 0.22)" : hexToRgba(color, 0.08),
              borderRadius: 2,
              transition: "background 0.08s, border-color 0.08s",
              overflow: "visible",
            }}
          >
            {on && w > 30 && h > 16 && (
              <span style={{
                position: "absolute", top: -16, left: 0,
                fontSize: 9, color: color, whiteSpace: "nowrap",
                background: "#0d1117", padding: "0 3px", borderRadius: 2,
              }}>
                {block.structure_type || block.type}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function UploadCanvas({
  file,
  setFile,
  preview,
  setPreview,
  blocks,
  highlightedBlockIndex,
  setHighlightedBlockIndex,
  txtContent,
  setTxtContent,
  setPointerMeta,
  fullText,
  blockSpans,
}) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const imageRef = useRef(null);
  const txtPreRef = useRef(null);
  const imgWrapRef = useRef(null);
  const [imgDisplay, setImgDisplay] = useState({ w: 0, h: 0 });

  const measureImage = useCallback(() => {
    const img = imageRef.current;
    if (!img?.complete || !img?.naturalWidth) return;
    const r = img.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      setImgDisplay({ w: r.width, h: r.height });
    }
  }, []);

  useEffect(() => {
    measureImage();
    window.addEventListener("resize", measureImage);
    const ro = new ResizeObserver(() => measureImage());
    if (imgWrapRef.current) ro.observe(imgWrapRef.current);
    return () => {
      window.removeEventListener("resize", measureImage);
      ro.disconnect();
    };
  }, [measureImage]);

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
    setTxtContent("");
    if (f.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(f);
    } else if (f.type === "application/pdf") {
      setPreview(URL.createObjectURL(f));
    } else if (ext === ".txt" || f.type === "text/plain") {
      setPreview(null);
      const reader = new FileReader();
      reader.onload = (e) => setTxtContent(e.target.result ?? "");
      reader.readAsText(f, "UTF-8");
    } else {
      setPreview(null);
    }
  };

  const handleChange = (e) => {
    const f = e.target.files?.[0];
    if (f) validateAndSetFile(f);
  };

  const handleImageMouseMove = (e) => {
    if (!blocks?.length || !imageRef.current) return;
    const img = imageRef.current;
    if (!img.complete || !img.naturalWidth) return;
    const rect = img.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    let foundIndex = null;
    for (let i = 0; i < blocks.length; i++) {
      const r = bboxToRect(blocks[i].bbox);
      if (r && pointInRect(x, y, r)) {
        foundIndex = i;
        break;
      }
    }
    if (foundIndex == null && blocks.length === 1 && !bboxToRect(blocks[0].bbox)) {
      if (x >= 0 && y >= 0 && x <= img.naturalWidth && y <= img.naturalHeight) foundIndex = 0;
    }
    setHighlightedBlockIndex(foundIndex);
    const span = foundIndex != null ? blockSpans[foundIndex] : null;
    const offset = span?.start ?? null;
    const { line, col } = lineColAtOffset(fullText || "", offset ?? 0);
    setPointerMeta({
      page: blocks[foundIndex]?.page ?? 1,
      line: offset != null ? line : null,
      col: offset != null ? col : null,
      charOffset: offset,
      blockIndex: foundIndex,
      region: "source",
    });
  };

  const handleImageMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  const handleTxtMouseMove = (e) => {
    if (!txtContent || !blocks?.length) return;
    const pre = txtPreRef.current;
    const offset = offsetFromPointInTextElement(pre, e.clientX, e.clientY);
    if (offset == null) return;
    let idx = null;
    for (let i = 0; i < blockSpans.length; i++) {
      const s = blockSpans[i];
      if (s.start != null && s.end != null && offset >= s.start && offset < s.end) {
        idx = i;
        break;
      }
    }
    if (idx == null && blocks.length === 1) idx = 0;
    setHighlightedBlockIndex(idx);
    const { line, col } = lineColAtOffset(txtContent, offset);
    setPointerMeta({
      page: 1,
      line,
      col,
      charOffset: offset,
      blockIndex: idx,
      region: "source",
    });
  };

  const handleTxtMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  const isImage = file?.type?.startsWith("image/");
  const isPdf = file?.type === "application/pdf";
  const isTxt = file && (file.type === "text/plain" || file.name?.toLowerCase().endsWith(".txt"));

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
          position: "relative", overflow: "auto"
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
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ width: "100%", height: "100%", position: "relative", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: 16, cursor: "default" }}
          >
            {isImage && preview && (
              <div
                ref={imgWrapRef}
                style={{ position: "relative", display: "inline-block", maxWidth: "100%", maxHeight: "calc(100vh - 200px)", overflow: "auto" }}
              >
                <img
                  ref={imageRef}
                  src={preview}
                  alt="preview"
                  style={{ maxWidth: "100%", height: "auto", display: "block", cursor: "crosshair" }}
                  onLoad={measureImage}
                  onMouseMove={handleImageMouseMove}
                  onMouseLeave={handleImageMouseLeave}
                />
                {blocks?.length > 0 && imgDisplay.w > 0 && imgDisplay.h > 0 && (
                  <BboxOverlay
                    blocks={blocks}
                    naturalW={imageRef.current?.naturalWidth || 1}
                    naturalH={imageRef.current?.naturalHeight || 1}
                    highlightedBlockIndex={highlightedBlockIndex}
                    displayW={imgDisplay.w}
                    displayH={imgDisplay.h}
                    pageNum={null}
                  />
                )}
              </div>
            )}
            {isPdf && preview && (
              <div
                style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}
                onMouseLeave={() => { setHighlightedBlockIndex(null); setPointerMeta(null); }}
              >
                <iframe src={preview} style={{ width: "100%", height: "100%", border: "none" }} />
              </div>
            )}
            {isTxt && (
              <pre
                ref={txtPreRef}
                onMouseMove={handleTxtMouseMove}
                onMouseLeave={handleTxtMouseLeave}
                style={{
                  margin: 0,
                  padding: 12,
                  maxWidth: "100%",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  fontSize: 13,
                  fontFamily: "ui-monospace, monospace",
                  color: "#e6edf3",
                  textAlign: "left",
                  cursor: "text",
                  userSelect: "text",
                }}
              >
                {txtContent || "Reading…"}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function ResultPanel({
  result,
  loading,
  error,
  onExport,
  highlightedBlockIndex,
  setHighlightedBlockIndex,
  activeTab,
  setActiveTab,
  blockSpans,
  setPointerMeta,
  rawPreRef,
}) {
  const tabs = [
    { id: "layout", label: "Layout View" },
    { id: "structure", label: "Structure View" },
    { id: "raw", label: "Raw Text" },
    { id: "table", label: "Table/Excel" },
  ];

  const groupedBlocks = useMemo(() => {
    if (!result?.blocks) return {};
    const groups = {};
    result.blocks.forEach(block => {
      const key = block.page || 1;
      if (!groups[key]) groups[key] = [];
      groups[key].push(block);
    });
    return groups;
  }, [result]);

  const allBlocks = result?.blocks || [];

  const handleRawMouseMove = (e) => {
    if (!result?.text) return;
    const pre = rawPreRef.current;
    const offset = offsetFromPointInTextElement(pre, e.clientX, e.clientY);
    if (offset == null) return;
    let idx = null;
    for (let i = 0; i < blockSpans.length; i++) {
      const s = blockSpans[i];
      if (s.start != null && s.end != null && offset >= s.start && offset < s.end) {
        idx = i;
        break;
      }
    }
    setHighlightedBlockIndex(idx);
    const { line, col } = lineColAtOffset(result.text, offset);
    setPointerMeta({
      page: idx != null ? allBlocks[idx]?.page : null,
      line,
      col,
      charOffset: offset,
      blockIndex: idx,
      region: "raw",
    });
  };

  const handleRawMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  const hl = highlightedBlockIndex != null ? blockSpans[highlightedBlockIndex] : null;

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
            {Object.entries(groupedBlocks).map(([page, pblocks]) => (
              <div key={page} style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>Page {page}</div>
                {pblocks.map((block, i) => {
                  const globalIndex = allBlocks.indexOf(block);
                  const isHighlighted = highlightedBlockIndex === globalIndex;
                  const blockColor = getStructureColor(block);
                  const hierarchyIndent = (block.hierarchy_level || 0) * 12;
                  const hasChildren = block.relations?.some(r => r.startsWith("child:"));
                  const hasParent = !!block.parent_id;
                  return (
                    <div
                      key={i}
                      onMouseEnter={() => {
                        setHighlightedBlockIndex(globalIndex);
                        const s = blockSpans[globalIndex];
                        const off = s?.start;
                        const { line, col } = lineColAtOffset(result.text, off ?? 0);
                        setPointerMeta({
                          page: block.page,
                          line: off != null ? line : null,
                          col: off != null ? col : null,
                          charOffset: off ?? null,
                          blockIndex: globalIndex,
                          region: "layout",
                        });
                      }}
                      onMouseLeave={() => {
                        setHighlightedBlockIndex(null);
                        setPointerMeta(null);
                      }}
                      style={{
                        background: isHighlighted ? "rgba(34, 197, 94, 0.2)" : (block.structure_type === "table" ? "rgba(245, 158, 11, 0.1)" : "#262c36"),
                        border: isHighlighted ? "1px solid rgba(34, 197, 94, 0.7)" : (block.structure_type === "table" ? "1px solid rgba(245, 158, 11, 0.3)" : "1px solid #30363d"),
                        borderLeft: hasParent ? `3px solid ${blockColor}` : undefined,
                        borderRadius: 6, padding: 10, paddingLeft: hasParent ? 10 + hierarchyIndent : 10 + hierarchyIndent, marginBottom: 8, display: "flex", alignItems: "flex-start", gap: 10,
                        cursor: "pointer",
                        transition: "background 0.1s, border-color 0.1s"
                      }}
                    >
                      <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 28 }}>
                        {block.reading_order != null && (
                          <span style={{
                            fontSize: 9, padding: "1px 4px", borderRadius: 3, background: "#374151", color: "#9ca3af", whiteSpace: "nowrap", textAlign: "center"
                          }}>
                            {block.reading_order + 1}
                          </span>
                        )}
                        <span style={{
                          fontSize: 10, padding: "2px 6px", borderRadius: 4, background: blockColor, color: "#fff", whiteSpace: "nowrap"
                        }}>{block.structure_type || block.type}</span>
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap" }}>{block.text}</div>
                        <div style={{ display: "flex", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                          {block.confidence != null && (
                            <span style={{ fontSize: 11, color: "#8b949e" }}>
                              Conf: {(block.confidence * 100).toFixed(1)}%
                            </span>
                          )}
                          {block.group_id && block.group_id !== "single" && (
                            <span style={{ fontSize: 10, color: "#6b7280", fontStyle: "italic" }}>
                              {block.group_id}
                            </span>
                          )}
                          {hasChildren && (
                            <span style={{ fontSize: 10, color: "#6b7280" }}>
                              ▸ {block.relations.filter(r => r.startsWith("child:")).length} child(ren)
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {result && activeTab === "structure" && (
          <StructureView
            blocks={allBlocks}
            pageInfos={result.page_infos}
            highlightedBlockIndex={highlightedBlockIndex}
            setHighlightedBlockIndex={setHighlightedBlockIndex}
          />
        )}

        {result && activeTab === "raw" && (
          <pre
            ref={rawPreRef}
            onMouseMove={handleRawMouseMove}
            onMouseLeave={handleRawMouseLeave}
            style={{
              margin: 0,
              fontSize: 13,
              color: "#e6edf3",
              whiteSpace: "pre-wrap",
              fontFamily: "ui-monospace, monospace",
              cursor: "text",
              lineHeight: 1.5,
            }}
          >
            {hl?.start != null && hl?.end != null ? (
              <>
                {result.text.slice(0, hl.start)}
                <mark style={{
                  background: "rgba(34, 197, 94, 0.35)",
                  color: "inherit",
                  borderRadius: 2,
                  padding: "0 2px",
                }}>
                  {result.text.slice(hl.start, hl.end)}
                </mark>
                {result.text.slice(hl.end)}
              </>
            ) : (
              result.text
            )}
          </pre>
        )}

        {result && activeTab === "table" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {(() => {
              const tableBlocks = result.blocks.filter(b => b.table_html || b.structure_type === "table");
              if (!tableBlocks.length) {
                return (
                  <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
                    No tables detected in this document
                  </div>
                );
              }
              return tableBlocks.map((block, i) => (
                <div key={i} style={{ background: "#1c2128", borderRadius: 8, padding: 12 }}>
                  <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 8 }}>
                    Table {i + 1} {block.confidence != null ? `· Conf: ${(block.confidence * 100).toFixed(1)}%` : ""}
                  </div>
                  {block.table_html ? (
                    <div style={{
                      overflow: "auto",
                      "& table": { width: "100%", borderCollapse: "collapse" },
                    }}>
                      <div dangerouslySetInnerHTML={{ __html: block.table_html }} style={{
                        color: "#e6edf3",
                      }} />
                      <style>{`
                        .structure-table table { width: 100%; border-collapse: collapse; }
                        .structure-table th, .structure-table td { border: 1px solid #30363d; padding: 8px 12px; text-align: left; font-size: 13px; }
                        .structure-table th { background: #262c36; color: #e6edf3; font-weight: 600; }
                        .structure-table tr:nth-child(even) { background: #1c2128; }
                        .structure-table tr:nth-child(odd) { background: #21262d; }
                        .structure-table tr:hover { background: #2d333b; }
                      `}</style>
                      <div className="structure-table" dangerouslySetInnerHTML={{ __html: block.table_html }} />
                    </div>
                  ) : (
                    <div style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap" }}>
                      {block.text}
                    </div>
                  )}
                </div>
              ));
            })()}
          </div>
        )}
      </div>

      {result && (
        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ padding: 12, background: "#161b22", borderRadius: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 12, color: "#8b949e" }}>
              {result.pages} page(s) • {result.blocks.length} blocks • {result.checksum?.slice(0, 12)}...
            </div>
            <button onClick={onExport} style={{
              padding: "8px 16px", background: "#6366f1", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 13
            }}>
              Export JSON
            </button>
          </div>
          <div style={{ padding: 8, background: "#161b22", borderRadius: 8, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 11, color: "#6b7280" }}>Structure:</span>
            {Object.entries(STRUCTURE_COLORS).slice(0, 6).map(([type, color]) => (
              <span key={type} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11 }}>
                <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 2, background: color }} />
                <span style={{ color: "#8b949e", textTransform: "capitalize" }}>{type}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const [activeView, setActiveView] = useState("workspace");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [txtContent, setTxtContent] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [highlightedBlockIndex, setHighlightedBlockIndex] = useState(null);
  const [pointerMeta, setPointerMeta] = useState(null);
  const [activeTab, setActiveTab] = useState("layout");
  const rawPreRef = useRef(null);

  const blockSpans = useMemo(
    () => computeBlockSpans(result?.text ?? "", result?.blocks ?? []),
    [result]
  );

  const handleProcess = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API_BASE}/api/extract`, { method: "POST", body: formData });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`HTTP ${res.status}: ${errorText}`);
      }
      setResult(await res.json());
    } catch (err) {
      const errorMessage = err.message || String(err);
      if (errorMessage.includes("Failed to fetch") || err instanceof TypeError) {
        setError(`无法连接后端服务 (${API_BASE})。请确保后端服务已启动：
          cd backend && uvicorn app.main:app --reload --port 8000`);
      } else {
        setError(errorMessage);
      }
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

  const avgConfidence = useMemo(() => {
    if (!result?.blocks?.length) return 0;
    const withConf = result.blocks.filter(b => b.confidence != null);
    if (!withConf.length) return 0;
    return withConf.reduce((a, b) => a + b.confidence, 0) / withConf.length * 100;
  }, [result]);

  const pointerLabel = useMemo(() => {
    if (!pointerMeta) return "Hover source, layout, or raw text to sync highlight";
    const { page, line, col, charOffset, blockIndex, region } = pointerMeta;
    const parts = [];
    if (page != null) parts.push(`Page ${page}`);
    if (line != null) parts.push(`Line ${line}`);
    if (col != null) parts.push(`Col ${col}`);
    if (charOffset != null) parts.push(`Char ${charOffset}`);
    if (blockIndex != null) parts.push(`Block #${blockIndex + 1}`);
    if (region) parts.push(region);
    return parts.join(" · ");
  }, [pointerMeta]);

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
            highlightedBlockIndex={highlightedBlockIndex}
            setHighlightedBlockIndex={setHighlightedBlockIndex}
            txtContent={txtContent}
            setTxtContent={setTxtContent}
            setPointerMeta={setPointerMeta}
            fullText={result?.text ?? ""}
            blockSpans={blockSpans}
          />
          <ResultPanel
            result={result}
            loading={loading}
            error={error}
            onExport={handleExport}
            highlightedBlockIndex={highlightedBlockIndex}
            setHighlightedBlockIndex={setHighlightedBlockIndex}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            blockSpans={blockSpans}
            setPointerMeta={setPointerMeta}
            rawPreRef={rawPreRef}
          />
        </div>
        <div style={{
          height: 40, background: "#161b22", borderTop: "1px solid #30363d",
          display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 24px", fontSize: 12, color: "#8b949e"
        }}>
          <div style={{ display: "flex", gap: 16, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1, marginRight: 16 }}>
            <span title={pointerLabel}>{pointerLabel}</span>
          </div>
          <div style={{ display: "flex", gap: 16, flexShrink: 0 }}>
            <span>Engine: {result ? "PaddleOCR" : "Ready"}</span>
            {result && <span>Conf: {avgConfidence.toFixed(1)}%</span>}
            {file && <span>{file.name}</span>}
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
