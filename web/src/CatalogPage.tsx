import { AlertCircle, Archive, ChevronLeft, ChevronRight, RefreshCw, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type CatalogPartitionItem, type DatasetSummary } from "./api";

const PAGE_SIZE = 100;

export default function CatalogPage({
  datasets,
  onOpenDataset,
}: {
  datasets: DatasetSummary[];
  onOpenDataset: (id: string) => void;
}) {
  const [items, setItems] = useState<CatalogPartitionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [datasetFilter, setDatasetFilter] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.listCatalogPartitions());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取 Catalog");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const datasetNames = useMemo(
    () => new Map(datasets.map((item) => [item.id, item.display_name])),
    [datasets],
  );

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    return items.filter((item) => {
      if (datasetFilter && item.dataset_id !== datasetFilter) return false;
      if (!keyword) return true;
      return (
        item.dataset_id.toLowerCase().includes(keyword) ||
        item.partition_key.toLowerCase().includes(keyword) ||
        item.file_path.toLowerCase().includes(keyword)
      );
    });
  }, [items, datasetFilter, query]);

  useEffect(() => setPage(0), [datasetFilter, query]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const visible = filtered.slice(
    currentPage * PAGE_SIZE,
    currentPage * PAGE_SIZE + PAGE_SIZE,
  );
  const totals = useMemo(
    () => ({
      rows: filtered.reduce((sum, item) => sum + item.row_count, 0),
      bytes: filtered.reduce((sum, item) => sum + item.size_bytes, 0),
      datasets: new Set(filtered.map((item) => item.dataset_id)).size,
    }),
    [filtered],
  );

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">CATALOG</p>
          <h1>Catalog</h1>
          <p className="subtitle">全部已发布分区、文件、行数和发布记录，不按日更或历史数据集过滤。</p>
        </div>
        <button className="toolbar-button" onClick={() => void load()}>
          <RefreshCw size={15} />刷新
        </button>
      </header>

      {error && <div className="form-error"><AlertCircle size={17} />{error}</div>}

      <section className="catalog-stats">
        <div><span>分区</span><strong>{filtered.length.toLocaleString()}</strong><small>全部 {items.length.toLocaleString()}</small></div>
        <div><span>数据集</span><strong>{totals.datasets.toLocaleString()}</strong><small>有 Catalog 记录</small></div>
        <div><span>总行数</span><strong>{formatNumber(totals.rows)}</strong><small>各分区行数之和</small></div>
        <div><span>占用空间</span><strong>{formatBytes(totals.bytes)}</strong><small>正式 Parquet 文件</small></div>
      </section>

      <section className="panel">
        <div className="panel-toolbar catalog-toolbar">
          <div><h2>分区明细</h2><span>包含日分区、历史数据集和 snapshot</span></div>
          <div className="catalog-filters">
            <label className="search-box"><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索数据集、分区或文件路径" /></label>
            <select value={datasetFilter} onChange={(event) => setDatasetFilter(event.target.value)}>
              <option value="">全部数据集</option>
              {[...datasetNames.entries()].map(([id, name]) => <option key={id} value={id}>{name} · {id}</option>)}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="state-box"><div className="loader" /><p>正在读取 Catalog…</p></div>
        ) : visible.length === 0 ? (
          <div className="state-box empty-state"><Archive size={28} /><strong>没有匹配的 Catalog 记录</strong><p>调整数据集或搜索条件。</p></div>
        ) : (
          <>
            <div className="catalog-table">
              <div className="catalog-row catalog-head"><span>数据集</span><span>分区</span><span>行数</span><span>大小</span><span>发布时间</span><span>文件</span></div>
              {visible.map((item) => (
                <div className="catalog-row" key={`${item.dataset_id}-${item.partition_key}-${item.file_path}`}>
                  <span className="catalog-dataset"><button type="button" onClick={() => onOpenDataset(item.dataset_id)}>{datasetNames.get(item.dataset_id) ?? item.dataset_id}</button><code>{item.dataset_id}</code></span>
                  <code>{item.partition_key}</code>
                  <span>{item.row_count.toLocaleString()}</span>
                  <span>{formatBytes(item.size_bytes)}</span>
                  <span>{formatTime(item.published_at)}</span>
                  <span className="catalog-file" title={`${item.file_path}\nsha256: ${item.sha256}`}>{item.file_path}</span>
                </div>
              ))}
            </div>
            <div className="catalog-footer">
              <span>第 {currentPage + 1} / {pageCount} 页 · 每页 {PAGE_SIZE} 条</span>
              <div>
                <button type="button" className="toolbar-button" disabled={currentPage === 0} onClick={() => setPage(currentPage - 1)}><ChevronLeft size={15} />上一页</button>
                <button type="button" className="toolbar-button" disabled={currentPage >= pageCount - 1} onClick={() => setPage(currentPage + 1)}>下一页<ChevronRight size={15} /></button>
              </div>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

function formatBytes(value: number) {
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(2)} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(2)} MB`;
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${value} B`;
}

function formatTime(value: string) {
  if (!value) return "—";
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(normalized));
}
