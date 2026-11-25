import { AlertCircle, Download, RefreshCw, Search, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, UIEvent } from "react";
import { api, type DatasetDetail, type DatasetRows } from "./api";

const PREVIEW_LIMIT = 20;
const QUERY_LIMIT = 100_000;
const ROW_HEIGHT = 34;
const VIEWPORT_HEIGHT = 520;
const OVERSCAN_ROWS = 8;

export default function DatasetPreview({ dataset }: { dataset: DatasetDetail }) {
  const [preview, setPreview] = useState<DatasetRows | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [appliedFilters, setAppliedFilters] = useState<Record<string, string>>({});
  const [downloadFormat, setDownloadFormat] = useState<"csv" | "parquet">("parquet");
  const [downloading, setDownloading] = useState(false);
  const [downloadMessage, setDownloadMessage] = useState<string | null>(null);

  const load = useCallback(async (requestedFilters: Record<string, string> = {}) => {
    setLoading(true);
    setError(null);
    try {
      const activeFilters = Object.fromEntries(
        Object.entries(requestedFilters).filter(([, value]) => value.trim()),
      );
      setPreview(await api.readDatasetRows(
        dataset.id,
        activeFilters,
        Object.keys(activeFilters).length ? QUERY_LIMIT : PREVIEW_LIMIT,
      ));
      setAppliedFilters(activeFilters);
    } catch (reason) {
      setPreview(null);
      setError(reason instanceof Error ? reason.message : "无法读取数据预览");
    } finally {
      setLoading(false);
    }
  }, [dataset.id]);

  useEffect(() => {
    setFilters({});
    setAppliedFilters({});
    setDownloadMessage(null);
    void load({});
  }, [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    void load(filters);
  }

  function clearFilters() {
    setFilters({});
    void load({});
  }

  async function downloadSelection() {
    setDownloading(true);
    setDownloadMessage(null);
    try {
      const rowCount = await api.downloadDatasetRows(dataset.id, appliedFilters, downloadFormat);
      setDownloadMessage(`已生成 ${rowCount.toLocaleString()} 行 ${downloadFormat.toUpperCase()} 文件。`);
    } catch (reason) {
      setDownloadMessage(reason instanceof Error ? reason.message : "下载失败");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <section className="panel dataset-preview">
      <div className="card-title">
        <div><h2>数据预览</h2><p>未筛选时预览 {PREVIEW_LIMIT} 行；按主键查询时最多展示 {QUERY_LIMIT.toLocaleString()} 行。</p></div>
        <div className="preview-actions">
          {preview && <span>读取 {preview.files_read} 个文件 · 展示 {preview.row_count.toLocaleString()} 行</span>}
          <button type="button" className="toolbar-button" onClick={() => void load(appliedFilters)} disabled={loading}><RefreshCw size={14} />重新读取</button>
        </div>
      </div>

      <form className="preview-filter" onSubmit={submit}>
        <div className="preview-filter-fields">
          {dataset.schema.primary_key.map((field) => (
            <label key={field}><span>{field}</span><input value={filters[field] ?? ""} onChange={(event) => setFilters((current) => ({ ...current, [field]: event.target.value }))} placeholder={`按 ${field} 精确筛选`} /></label>
          ))}
        </div>
        <div className="preview-filter-actions">
          <button type="submit" className="primary-button" disabled={loading}><Search size={14} />查询</button>
          <button type="button" className="ghost-button" onClick={clearFilters} disabled={loading}><X size={14} />清空</button>
          <select value={downloadFormat} onChange={(event) => setDownloadFormat(event.target.value as "csv" | "parquet")} aria-label="下载格式">
            <option value="parquet">Parquet</option>
            <option value="csv">CSV</option>
          </select>
          <button type="button" className="ghost-button" onClick={() => void downloadSelection()} disabled={downloading || !preview?.filtered || Object.keys(appliedFilters).length === 0}><Download size={14} />{downloading ? "生成中…" : "下载结果"}</button>
        </div>
      </form>

      {downloadMessage && <div className="preview-download-message">{downloadMessage}</div>}

      {preview?.filtered && <div className={preview.truncated ? "preview-query-note warning" : "preview-query-note"}>
        {preview.truncated
          ? `共匹配 ${preview.matched_count?.toLocaleString()} 行，结果过多，仅展示前 ${QUERY_LIMIT.toLocaleString()} 行。`
          : `共匹配 ${preview.matched_count?.toLocaleString()} 行，已全部展示。`}
      </div>}

      {error && <div className="preview-error"><AlertCircle size={16} /><span><strong>预览失败</strong>{error}</span></div>}
      {loading ? (
        <div className="preview-state"><div className="loader" /><span>正在读取已发布数据…</span></div>
      ) : !error && (!preview || preview.rows.length === 0) ? (
        <div className="preview-state"><strong>{preview?.filtered ? "没有匹配数据" : "尚无已发布数据"}</strong><span>{preview?.filtered ? "请调整主键筛选条件。" : "采集并通过审核、发布后会在这里显示。"}</span></div>
      ) : !error && preview ? (
        <VirtualPreviewTable preview={preview} />
      ) : null}
    </section>
  );
}

function VirtualPreviewTable({ preview }: { preview: DatasetRows }) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const visibleRows = Math.ceil(VIEWPORT_HEIGHT / ROW_HEIGHT);
  const start = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN_ROWS);
  const end = Math.min(preview.rows.length, start + visibleRows + OVERSCAN_ROWS * 2);
  const topSpace = start * ROW_HEIGHT;
  const bottomSpace = Math.max(0, (preview.rows.length - end) * ROW_HEIGHT);

  useEffect(() => {
    setScrollTop(0);
    if (viewportRef.current) viewportRef.current.scrollTop = 0;
  }, [preview.rows]);

  function trackScroll(event: UIEvent<HTMLDivElement>) {
    setScrollTop(event.currentTarget.scrollTop);
  }

  return (
    <div className="preview-table-wrap" ref={viewportRef} onScroll={trackScroll}>
      <table className="preview-table">
        <thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
        <tbody>
          {topSpace > 0 && <SpacerRow height={topSpace} columns={preview.columns.length} />}
          {preview.rows.slice(start, end).map((row, index) => (
            <tr key={start + index}>{preview.columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}</tr>
          ))}
          {bottomSpace > 0 && <SpacerRow height={bottomSpace} columns={preview.columns.length} />}
        </tbody>
      </table>
    </div>
  );
}

function SpacerRow({ height, columns }: { height: number; columns: number }) {
  return <tr className="preview-spacer" aria-hidden="true"><td colSpan={columns} style={{ height }} /></tr>;
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
