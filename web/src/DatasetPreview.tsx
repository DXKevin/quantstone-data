import { AlertCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, type DatasetDetail, type DatasetRows } from "./api";

const PREVIEW_LIMIT = 20;

export default function DatasetPreview({ dataset }: { dataset: DatasetDetail }) {
  const [preview, setPreview] = useState<DatasetRows | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPreview(await api.readDatasetRows(dataset.id, PREVIEW_LIMIT));
    } catch (reason) {
      setPreview(null);
      setError(reason instanceof Error ? reason.message : "无法读取数据预览");
    } finally {
      setLoading(false);
    }
  }, [dataset.id]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="panel dataset-preview">
      <div className="card-title">
        <div><h2>数据预览</h2><p>仅展示 Catalog 中已发布的数据，最多 {PREVIEW_LIMIT} 行。</p></div>
        <div className="preview-actions">
          {preview && <span>读取 {preview.files_read} 个文件 · {preview.row_count} 行</span>}
          <button type="button" className="toolbar-button" onClick={() => void load()} disabled={loading}><RefreshCw size={14} />刷新</button>
        </div>
      </div>

      {error && <div className="preview-error"><AlertCircle size={16} /><span><strong>预览失败</strong>{error}</span></div>}
      {loading ? (
        <div className="preview-state"><div className="loader" /><span>正在读取已发布数据…</span></div>
      ) : !error && (!preview || preview.rows.length === 0) ? (
        <div className="preview-state"><strong>尚无已发布数据</strong><span>采集并通过审核、发布后会在这里显示。</span></div>
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
