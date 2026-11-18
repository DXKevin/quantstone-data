import { AlertCircle, Database, HardDrive, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  api,
  type CatalogPartition,
  type DatasetSummary,
  type StorageOverview,
} from "./api";

export default function StoragePage({ datasets }: { datasets: DatasetSummary[] }) {
  const [overview, setOverview] = useState<StorageOverview | null>(null);
  const [partitions, setPartitions] = useState<CatalogPartition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summary, items] = await Promise.all([
        api.getStorageOverview(),
        api.listCatalogPartitions(),
      ]);
      setOverview(summary);
      setPartitions(items);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取存储信息");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="page">
      <header className="page-header">
        <div><p className="eyebrow">DATA STORAGE</p><h1>数据存储</h1><p className="subtitle">查看正式发布文件、Catalog 分区与暂存运行。</p></div>
        <button className="toolbar-button" onClick={() => void load()}><RefreshCw size={15} />刷新</button>
      </header>

      {error && <div className="form-error"><AlertCircle size={17} />{error}</div>}
      {loading || !overview ? (
        <div className="panel state-box"><div className="loader" /><p>正在读取存储信息…</p></div>
      ) : <>
        <section className="storage-root panel">
          <div><HardDrive size={19} /><span>数据根目录</span></div><code>{overview.data_root}</code>
        </section>
        <section className="summary-strip storage-summary">
          <div><span>正式文件</span><strong>{overview.published_files.toLocaleString()}</strong></div>
          <div><span>Catalog 分区</span><strong>{overview.published_partitions.toLocaleString()}</strong></div>
          <div><span>已发布行数</span><strong>{overview.published_rows.toLocaleString()}</strong></div>
          <div><span>登记体积</span><strong>{formatBytes(overview.published_bytes)}</strong></div>
        </section>
        <section className="storage-health">
          <span><i className={overview.staged_runs ? "pending" : "ok"} />暂存运行 {overview.staged_runs}</span>
          <span><i className={overview.missing_files ? "bad" : "ok"} />缺失文件 {overview.missing_files}</span>
        </section>
        <section className="panel">
          <div className="panel-toolbar"><div><h2>正式文件目录</h2><span>{partitions.length} 条 Catalog 记录</span></div></div>
          {partitions.length === 0 ? <div className="state-box"><Database size={27} /><strong>尚无已发布文件</strong><p>数据通过审核并发布后会显示在这里。</p></div> : <div className="storage-table">
            <div className="storage-row storage-head"><span>数据集 / 分区</span><span>文件路径</span><span>行数</span><span>体积</span><span>校验值</span><span>发布时间</span></div>
            {partitions.map((item) => <div className="storage-row" key={`${item.dataset_id}:${item.partition_key}`}>
              <span className="storage-dataset"><strong>{datasetName(datasets, item.dataset_id)}</strong><code>{item.dataset_id}</code><small>{item.partition_key}</small></span>
              <code className="storage-path" title={item.file_path}>{item.file_path}</code>
              <span>{item.row_count.toLocaleString()}</span>
              <span>{formatBytes(item.size_bytes)}</span>
              <code title={item.sha256}>{item.sha256.slice(0, 12)}…</code>
              <span>{formatDate(item.published_at)}</span>
            </div>)}
          </div>}
        </section>
      </>}
    </div>
  );
}

function datasetName(datasets: DatasetSummary[], id: string) {
  return datasets.find((item) => item.id === id)?.display_name ?? id;
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
