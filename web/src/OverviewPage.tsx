import { AlertCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type DatasetOverview, type DatasetStatus } from "./api";

const statusLabels: Record<DatasetStatus, string> = {
  draft: "草稿",
  active: "已启用",
  paused: "已暂停",
  deprecated: "已停用",
};

const layoutLabels: Record<string, string> = {
  daily: "单日文件",
  yearly_with_delta: "年度主文件 + 日增量",
  snapshot: "完整快照",
};

export default function OverviewPage({ onOpen }: { onOpen: (id: string) => void }) {
  const [items, setItems] = useState<DatasetOverview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await api.getDatasetOverview());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载概览");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const totals = useMemo(
    () => ({
      datasets: items.length,
      partitions: items.reduce((sum, item) => sum + item.partitions, 0),
      rows: items.reduce((sum, item) => sum + item.rows, 0),
      bytes: items.reduce((sum, item) => sum + item.size_bytes, 0),
      missing: items.reduce((sum, item) => sum + item.missing_files, 0),
    }),
    [items],
  );

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h1>数据概览</h1>
          <p className="subtitle">按数据集聚合已发布的分区、行数、体积和覆盖情况。</p>
        </div>
        <button className="toolbar-button" onClick={() => void load()}><RefreshCw size={15} />刷新</button>
      </header>

      <section className="summary-strip">
        <div><span>数据集</span><strong>{totals.datasets}</strong></div>
        <div><span>已发布分区</span><strong>{totals.partitions.toLocaleString()}</strong></div>
        <div><span>总行数</span><strong>{totals.rows.toLocaleString()}</strong></div>
        <div><span>总体积</span><strong>{formatBytes(totals.bytes)}</strong></div>
      </section>

      {error && <div className="form-error"><AlertCircle size={17} />{error}</div>}
      {totals.missing > 0 && (
        <div className="warning-banner"><AlertCircle size={17} />有 {totals.missing} 个 Catalog 分区对应的文件缺失。</div>
      )}

      {loading ? (
        <div className="state-box"><div className="loader" /><p>正在汇总数据…</p></div>
      ) : items.length === 0 ? (
        <div className="state-box empty-state"><strong>还没有数据集</strong><p>先在数据集页面创建并启用一个数据集。</p></div>
      ) : (
        <section className="overview-grid">
          {items.map((item) => (
            <button
              type="button"
              className="overview-card"
              key={item.dataset_id}
              onClick={() => onOpen(item.dataset_id)}
            >
              <div className="overview-card-head">
                <strong>{item.display_name}</strong>
                <span className={`status status-${item.status}`}><i />{statusLabels[item.status]}</span>
              </div>
              <code className="overview-id">{item.dataset_id}</code>

              <div className="overview-metrics">
                <div><span>分区</span><b>{item.partitions.toLocaleString()}</b></div>
                <div><span>行数</span><b>{item.rows.toLocaleString()}</b></div>
                <div><span>体积</span><b>{formatBytes(item.size_bytes)}</b></div>
              </div>

              <div className="overview-coverage">
                <div className="coverage-head">
                  <span>覆盖</span>
                  <span>
                    {item.coverage_percent === null
                      ? "不按日分区"
                      : `${item.coverage_percent}% · ${item.partitions}/${item.expected_partitions ?? 0} 个交易日`}
                  </span>
                </div>
                <div className="coverage-bar">
                  <i style={{ width: `${Math.min(item.coverage_percent ?? 0, 100)}%` }} />
                </div>
              </div>

              <div className="overview-foot">
                <span>{layoutLabels[item.layout ?? ""] ?? "未配置布局"}</span>
                <span>最新 {item.latest_partition ?? "—"}</span>
                <span>{item.published_at ? `发布 ${formatDate(item.published_at)}` : "尚未发布"}</span>
              </div>
            </button>
          ))}
        </section>
      )}
    </div>
  );
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}
