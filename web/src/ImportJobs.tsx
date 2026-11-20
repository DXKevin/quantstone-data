import { AlertCircle, CheckCircle2, FileScan, RefreshCw, ShieldCheck, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  api,
  type DatasetSummary,
  type ImportJob,
  type ImportJobStatus,
  type ImportManifest,
  type ScannerDefinition,
} from "./api";

const ACTIVE_STATUSES: ImportJobStatus[] = [
  "created",
  "scanning",
  "importing",
  "cancelling",
];

const statusLabels: Record<ImportJobStatus, string> = {
  created: "已创建",
  scanning: "扫描中",
  review_ready: "待审核",
  importing: "导入中",
  cancelling: "正在取消",
  cancelled: "已取消",
  succeeded: "已完成",
  failed: "失败",
};

const fileStatusLabels: Record<string, string> = {
  ready: "可导入",
  duplicate: "已存在",
  invalid: "校验失败",
};

const defaultSourceRoots: Record<string, string> = {
  "wind.cn.stock.l2_order.sz": "/home/hhd_data/quantstone-data/imports/wind_l2/sz",
  "wind.cn.stock.l2_trade.sz": "/home/hhd_data/quantstone-data/imports/wind_l2/sz",
  "zhongtai.cn.stock.l2_order.sz": "/home/hhd_data/quantstone-data/imports/zhongtai_l2/sz",
  "zhongtai.cn.stock.l2_trade.sz": "/home/hhd_data/quantstone-data/imports/zhongtai_l2/sz",
};

export default function ImportJobs({
  datasets,
  navigation,
}: {
  datasets: DatasetSummary[];
  navigation?: ReactNode;
}) {
  const [scanners, setScanners] = useState<ScannerDefinition[]>([]);
  const [jobs, setJobs] = useState<ImportJob[]>([]);
  const [datasetId, setDatasetId] = useState("wind.cn.stock.l2_order.sz");
  const [operation, setOperation] = useState("import_order");
  const [sourceRoot, setSourceRoot] = useState(
    "/home/hhd_data/quantstone-data/imports/wind_l2/sz",
  );
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [transferMode, setTransferMode] = useState<"move" | "copy">("move");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [manifest, setManifest] = useState<ImportManifest | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);
  const [actionJobId, setActionJobId] = useState<string | null>(null);

  const importableDatasets = useMemo(
    () =>
      datasets.filter((dataset) =>
        scanners.some((scanner) =>
          scanner.operations.some((item) => item.dataset_id === dataset.id),
        ),
      ),
    [datasets, scanners],
  );

  const operations = useMemo(
    () =>
      scanners
        .flatMap((scanner) =>
          scanner.operations.map((item) => ({
            ...item,
            scanner_key: scanner.key,
            scanner_name: scanner.name,
          })),
        )
        .filter((item) => item.dataset_id === datasetId),
    [scanners, datasetId],
  );

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [scannerData, jobData] = await Promise.all([
        api.listScanners(),
        api.listImportJobs(),
      ]);
      setScanners(scannerData);
      setJobs(jobData);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载目录导入任务");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!importableDatasets.length) return;
    if (!importableDatasets.some((dataset) => dataset.id === datasetId)) {
      setDatasetId(importableDatasets[0].id);
    }
  }, [importableDatasets, datasetId]);

  useEffect(() => {
    if (operations.length && !operations.some((item) => item.key === operation)) {
      setOperation(operations[0].key);
    }
  }, [operations, operation]);

  useEffect(() => {
    const next = defaultSourceRoots[datasetId];
    if (next) {
      setSourceRoot((current) =>
        current === "" || Object.values(defaultSourceRoots).includes(current)
          ? next
          : current,
      );
    }
  }, [datasetId]);

  const hasActive = jobs.some((job) => ACTIVE_STATUSES.includes(job.status));
  useEffect(() => {
    if (!hasActive) return;
    const timer = window.setInterval(() => void load(true), 2500);
    return () => window.clearInterval(timer);
  }, [hasActive, load]);

  useEffect(() => {
    if (!expandedId || manifest) return;
    const job = jobs.find((item) => item.id === expandedId);
    if (job && job.status !== "created" && job.status !== "scanning") {
      void loadManifest(expandedId);
    }
  }, [expandedId, jobs, manifest]);

  async function loadManifest(jobId: string) {
    setManifestLoading(true);
    try {
      setManifest(await api.getImportManifest(jobId));
    } catch (reason) {
      setManifest(null);
      setError(reason instanceof Error ? reason.message : "无法读取导入清单");
    } finally {
      setManifestLoading(false);
    }
  }

  async function toggleJob(job: ImportJob) {
    if (expandedId === job.id) {
      setExpandedId(null);
      setManifest(null);
      return;
    }
    setExpandedId(job.id);
    setManifest(null);
    await loadManifest(job.id);
  }

  async function createJob(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const job = await api.createImportJob({
        dataset_id: datasetId,
        scanner_key: operations[0]?.scanner_key ?? "wind_l2_sz",
        operation,
        source_root: sourceRoot,
        transfer_mode: transferMode,
        start_date: startDate || null,
        end_date: endDate || null,
      });
      setNotice(`已创建扫描任务 ${job.id.slice(0, 8)}，正在扫描目录。`);
      setExpandedId(job.id);
      setManifest(null);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建扫描任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function executeJob(job: ImportJob) {
    setActionJobId(job.id);
    setError(null);
    setNotice(null);
    try {
      await api.executeImportJob(job.id);
      setNotice("已提交导入，后台正在审核并发布。");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交导入失败");
    } finally {
      setActionJobId(null);
    }
  }

  async function cancelJob(job: ImportJob) {
    setActionJobId(job.id);
    setError(null);
    try {
      await api.cancelImportJob(job.id);
      setNotice("已请求取消目录导入任务。");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消导入任务失败");
    } finally {
      setActionJobId(null);
    }
  }

  return (
    <div className="page">
      {navigation}
      <header className="page-header">
        <div>
          <p className="eyebrow">DIRECTORY IMPORT</p>
          <h1>目录导入</h1>
          <p className="subtitle">扫描已转换的服务器目录，审核清单后按交易日导入。</p>
        </div>
        <button className="toolbar-button" onClick={() => void load()}><RefreshCw size={15} />刷新</button>
      </header>

      {notice && <div className="notice-banner"><CheckCircle2 size={17} />{notice}</div>}
      {error && <div className="form-error"><AlertCircle size={17} />{error}</div>}

      <section className="panel import-create-panel">
        <div className="panel-toolbar"><div><h2>新建扫描</h2><span>源目录必须位于数据根目录的 imports/ 下</span></div></div>
        <form className="import-create-form" onSubmit={(event) => void createJob(event)}>
          <label className="input-field"><span>目标数据集</span><select value={datasetId} onChange={(event) => setDatasetId(event.target.value)}>{importableDatasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.display_name} · {dataset.id}</option>)}</select></label>
          <label className="input-field"><span>扫描操作</span><select value={operation} onChange={(event) => setOperation(event.target.value)}>{operations.map((item) => <option key={item.key} value={item.key}>{item.name}</option>)}</select></label>
          <label className="input-field"><span>源目录</span><input value={sourceRoot} onChange={(event) => setSourceRoot(event.target.value)} placeholder="/home/hhd_data/quantstone-data/imports/wind_l2/sz" /></label>
          <label className="input-field"><span>文件处理</span><select value={transferMode} onChange={(event) => setTransferMode(event.target.value as "move" | "copy")}><option value="move">移动（同盘快速，导入后删除源文件）</option><option value="copy">复制（保留源文件）</option></select></label>
          <label className="input-field"><span>开始日期</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
          <label className="input-field"><span>结束日期</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
          <button className="primary-button" type="submit" disabled={submitting || !operations.length}>{submitting ? "扫描中…" : "开始扫描"}</button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-toolbar"><div><h2>导入任务</h2><span>{jobs.length} 个任务</span></div></div>
        {loading ? (
          <div className="state-box"><div className="loader" /><p>正在加载导入任务…</p></div>
        ) : jobs.length === 0 ? (
          <div className="state-box empty-state"><FileScan size={28} /><strong>还没有目录导入任务</strong><p>先在上方选择数据集和源目录开始扫描。</p></div>
        ) : (
          <div className="import-job-list">
            {jobs.map((job) => {
              const summary = job.summary ?? {};
              const expanded = expandedId === job.id;
              const active = ACTIVE_STATUSES.includes(job.status);
              return (
                <div className="import-job-block" key={job.id}>
                  <div className="import-job-row" onClick={() => void toggleJob(job)}>
                    <span className="import-job-id"><strong>{job.dataset_id}</strong><code>{job.scanner_key} · {job.operation}</code><small>{job.id.slice(0, 8)} · {formatTime(job.created_at)}</small></span>
                    <span className={`job-status job-status-${job.status}`}><i />{statusLabels[job.status]}</span>
                    <span className="import-job-summary">{summaryText(summary)}</span>
                    <span className="import-job-actions" onClick={(event) => event.stopPropagation()}>
                      {job.status === "review_ready" && <button type="button" className="mini-upload-button" disabled={actionJobId === job.id} onClick={() => void executeJob(job)}><ShieldCheck size={14} />确认导入</button>}
                      {active && job.status !== "cancelling" && <button type="button" className="mini-upload-button danger-mini" disabled={actionJobId === job.id} onClick={() => void cancelJob(job)}><X size={14} />取消</button>}
                    </span>
                  </div>
                  {job.error && <div className="import-job-error"><AlertCircle size={14} />{job.error}</div>}
                  {expanded && (
                    <div className="import-manifest">
                      {manifestLoading ? <p className="job-detail-empty">正在读取清单…</p> : manifest ? (
                        <>
                          <div className="import-manifest-head"><span>清单：{manifest.files.length} 个文件</span><span>源目录 {manifest.source_root}</span></div>
                          <div className="import-file-table">
                            <div className="import-file-row import-file-head"><span>交易日</span><span>状态</span><span>行数</span><span>错误</span></div>
                            {manifest.files.slice(0, 300).map((file) => (
                              <div className={`import-file-row import-file-${file.status}`} key={file.partition_key}>
                                <code>{file.partition_key}</code>
                                <span>{fileStatusLabels[file.status] ?? file.status}</span>
                                <span>{file.row_count?.toLocaleString() ?? "—"}</span>
                                <span>{file.errors.map((item) => String(item.rule ?? item.message ?? "")).join("；")}</span>
                              </div>
                            ))}
                          </div>
                        </>
                      ) : <p className="job-detail-empty">尚未生成清单。</p>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}

function summaryText(summary: Record<string, unknown>) {
  const parts = [
    `文件 ${Number(summary.files ?? 0)}`,
    `可导入 ${Number(summary.ready ?? 0)}`,
    `已存在 ${Number(summary.duplicates ?? 0)}`,
    `异常 ${Number(summary.invalid ?? 0)}`,
  ];
  if (summary.imported !== undefined) parts.push(`已导入 ${Number(summary.imported)}`);
  return parts.join(" · ");
}

function formatTime(value: string) {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(normalized));
}
