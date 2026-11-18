import { AlertCircle, RefreshCw, Search, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, type DatasetDetail, type DatasetRows } from "./api";

const PREVIEW_LIMIT = 20;
const QUERY_LIMIT = 100_000;

export default function DatasetPreview({ dataset }: { dataset: DatasetDetail }) {
  const [preview, setPreview] = useState<DatasetRows | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});

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
    } catch (reason) {
      setPreview(null);
      setError(reason instanceof Error ? reason.message : "无法读取数据预览");
    } finally {
      setLoading(false);
    }
  }, [dataset.id]);

  useEffect(() => {
    setFilters({});
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

  return (
    <section className="panel dataset-preview">
      <div className="card-title">
        <div><h2>数据预览</h2><p>未筛选时预览 {PREVIEW_LIMIT} 行；按主键查询时最多展示 {QUERY_LIMIT.toLocaleString()} 行。</p></div>
        <div className="preview-actions">
          {preview && <span>读取 {preview.files_read} 个文件 · 展示 {preview.row_count.toLocaleString()} 行</span>}
          <button type="button" className="toolbar-button" onClick={() => void load(filters)} disabled={loading}><RefreshCw size={14} />刷新</button>
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
        </div>
      </form>

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
        <div className="preview-table-wrap">
          <table className="preview-table">
            <thead><tr>{preview.columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
            <tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.columns.map((column) => <td key={column}>{formatCell(row[column])}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}
