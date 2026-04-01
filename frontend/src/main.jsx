import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { createRoot } from "react-dom/client";
import * as pdfjs from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjs.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

const API_BASE = "http://localhost:8000";
const SUPPORTED_TYPES = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt"];
const MAX_FILE_SIZE = 50 * 1024 * 1024;
/** Must match backend PyMuPDF OCR raster scale (fitz.Matrix(2, 2)) */
const PDF_OCR_SCALE = 2;

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
        return (
          <div
            key={globalIdx}
            style={{
              position: "absolute",
              left, top, width: w, height: h,
              border: on ? "2px solid rgba(34, 197, 94, 0.95)" : "1px solid rgba(99, 102, 241, 0.45)",
              background: on ? "rgba(34, 197, 94, 0.22)" : "rgba(99, 102, 241, 0.06)",
              borderRadius: 2,
              transition: "background 0.08s, border-color 0.08s",
            }}
          />
        );
      })}
    </div>
  );
}

function PdfPageCanvas({
  pageNum,
  pdfDoc,
  allBlocks,
  highlightedBlockIndex,
  setHighlightedBlockIndex,
  setPointerMeta,
  fullText,
  blockSpans,
}) {
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);
  const [intrinsic, setIntrinsic] = useState({ w: 0, h: 0 });
  const [display, setDisplay] = useState({ w: 0, h: 0 });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const page = await pdfDoc.getPage(pageNum);
      const viewport = page.getViewport({ scale: PDF_OCR_SCALE });
      const canvas = canvasRef.current;
      if (!canvas || cancelled) return;
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: ctx, viewport }).promise;
      if (!cancelled) setIntrinsic({ w: viewport.width, h: viewport.height });
    })();
    return () => { cancelled = true; };
  }, [pdfDoc, pageNum]);

  const measure = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    const r = c.getBoundingClientRect();
    setDisplay({ w: r.width, h: r.height });
  }, []);

  useEffect(() => {
    measure();
    const ro = new ResizeObserver(() => measure());
    if (wrapRef.current) ro.observe(wrapRef.current);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [measure, intrinsic.w]);

  const pageBlocks = allBlocks.map((b, i) => ({ b, i })).filter(({ b }) => b.page === pageNum);

  const pickBlockIndex = (x, y) => {
    const withBbox = pageBlocks.filter(({ b }) => bboxToRect(b.bbox));
    for (const { b, i } of withBbox) {
      const r = bboxToRect(b.bbox);
      if (r && pointInRect(x, y, r)) return i;
    }
    const noBbox = pageBlocks.filter(({ b }) => !bboxToRect(b.bbox));
    if (noBbox.length === 1 && pageBlocks.length === 1) return noBbox[0].i;
    if (withBbox.length === 0 && noBbox.length >= 1 && pointInRect(x, y, {
      minX: 0, minY: 0, maxX: intrinsic.w, maxY: intrinsic.h,
    })) {
      return noBbox[0].i;
    }
    return null;
  };

  const onMouseMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas || !intrinsic.w) return;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    const idx = pickBlockIndex(x, y);
    setHighlightedBlockIndex(idx);
    const span = idx != null ? blockSpans[idx] : null;
    const offset = span?.start ?? null;
    const { line, col } = lineColAtOffset(fullText || "", offset ?? 0);
    setPointerMeta({
      page: pageNum,
      line: offset != null ? line : null,
      col: offset != null ? col : null,
      charOffset: offset,
      blockIndex: idx,
      region: "source",
    });
  };

  const onMouseLeave = () => {
    setHighlightedBlockIndex(null);
    setPointerMeta(null);
  };

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 11, color: "#8b949e", marginBottom: 6 }}>Page {pageNum}</div>
      <div ref={wrapRef} style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}>
        <canvas
          ref={canvasRef}
          onMouseMove={onMouseMove}
          onMouseLeave={onMouseLeave}
          style={{ display: "block", maxWidth: "100%", height: "auto", cursor: "crosshair" }}
        />
        {intrinsic.w > 0 && (
          <BboxOverlay
            blocks={allBlocks}
            pageNum={pageNum}
            naturalW={intrinsic.w}
            naturalH={intrinsic.h}
            highlightedBlockIndex={highlightedBlockIndex}
            displayW={display.w}
            displayH={display.h}
          />
        )}
      </div>
    </div>
  );
}

function PdfDocumentView(props) {
  const { file, ...rest } = props;
  const [pdfDoc, setPdfDoc] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    let cancelled = false;
    setErr("");
    (async () => {
      try {
        const buf = await file.arrayBuffer();
        const doc = await pdfjs.getDocument({ data: buf }).promise;
        if (!cancelled) setPdfDoc(doc);
      } catch (e) {
        if (!cancelled) setErr(String(e.message || e));
      }
    })();
    return () => { cancelled = true; };
  }, [file]);

  if (err) return <div style={{ color: "#ef4444", padding: 16 }}>PDF: {err}</div>;
  if (!pdfDoc) return <div style={{ color: "#8b949e", padding: 16 }}>Loading PDF…</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      {Array.from({ length: pdfDoc.numPages }, (_, i) => i + 1).map((pn) => (
        <PdfPageCanvas key={pn} pageNum={pn} pdfDoc={pdfDoc} {...rest} />
      ))}
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
    if (!img?.naturalWidth) return;
    const r = img.getBoundingClientRect();
    setImgDisplay({ w: r.width, h: r.height });
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
  }, [measureImage, preview, file]);

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
    const rect = img.getBoundingClientRect();
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
                style={{ position: "relative", display: "inline-block", maxWidth: "100%" }}
                onMouseMove={handleImageMouseMove}
                onMouseLeave={handleImageMouseLeave}
              >
                <img
                  ref={imageRef}
                  src={preview}
                  alt="preview"
                  style={{ maxWidth: "100%", height: "auto", display: "block", cursor: "crosshair" }}
                  onLoad={measureImage}
                />
                {blocks?.length > 0 && imageRef.current?.naturalWidth > 0 && (
                  <BboxOverlay
                    blocks={blocks}
                    naturalW={imageRef.current.naturalWidth}
                    naturalH={imageRef.current.naturalHeight}
                    highlightedBlockIndex={highlightedBlockIndex}
                    displayW={imgDisplay.w}
                    displayH={imgDisplay.h}
                  />
                )}
              </div>
            )}
            {isPdf && preview && (
              <div style={{ width: "100%", cursor: "default" }} onMouseLeave={() => { setHighlightedBlockIndex(null); setPointerMeta(null); }}>
                <PdfDocumentView
                  file={file}
                  allBlocks={blocks ?? []}
                  highlightedBlockIndex={highlightedBlockIndex}
                  setHighlightedBlockIndex={setHighlightedBlockIndex}
                  setPointerMeta={setPointerMeta}
                  fullText={fullText}
                  blockSpans={blockSpans}
                />
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
                        background: isHighlighted ? "rgba(34, 197, 94, 0.2)" : (block.type === "table" ? "rgba(245, 158, 11, 0.1)" : "#262c36"),
                        border: isHighlighted ? "1px solid rgba(34, 197, 94, 0.7)" : (block.type === "table" ? "1px solid rgba(245, 158, 11, 0.3)" : "1px solid #30363d"),
                        borderRadius: 6, padding: 10, marginBottom: 8, display: "flex", alignItems: "flex-start", gap: 10,
                        cursor: "pointer",
                        transition: "background 0.1s, border-color 0.1s"
                      }}
                    >
                      <span style={{
                        fontSize: 10, padding: "2px 6px", borderRadius: 4, background: "#6366f1", color: "#fff", whiteSpace: "nowrap"
                      }}>{block.type}</span>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 13, color: "#e6edf3", whiteSpace: "pre-wrap" }}>{block.text}</div>
                        {block.confidence != null && (
                          <div style={{ fontSize: 11, color: "#8b949e", marginTop: 4 }}>
                            Confidence: {(block.confidence * 100).toFixed(1)}%
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
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
          <div style={{ color: "#8b949e", textAlign: "center", padding: 40 }}>
            Table extraction view - blocks with type &quot;table&quot; shown here
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
