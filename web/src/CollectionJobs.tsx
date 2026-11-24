import {
  AlertCircle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Clock3,
  FileScan,
  FolderInput,
  FileUp,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UploadCloud,
} from "lucide-react";
import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type CollectionInputMethod,
  type CollectorDefinition,
  type CollectorParameter,
  type CollectionJob,
  type CollectionJobCreatePayload,
  type CollectionLogEntry,
  type CollectionOperation,
  type CollectionProgress,
  type CollectionReview,
  type CollectionRun,
  type DatasetSummary,
  type ImportJob,
  type ImportManifest,
  type ScannerDefinition,
} from "./api";

const operationLabels: Record<CollectionOperation, string> = {
  initial: "首次采集",
  incremental: "增量更新",
  repair: "缺口修复",
  replace: "范围重建",
};

const inputLabels: Record<string, string> = {
  collector: "采集器",
  file_import: "手动文件",
  directory_import: "目录导入",
};

const statusLabels = {
  created: "已创建",
  scanning: "扫描中",
  review_ready: "待确认",
  importing: "导入中",
  queued: "排队中",
  running: "执行中",
  cancelling: "正在取消",
  cancelled: "已取消",
  awaiting_file: "等待文件",
  staged: "已进入临时区",
  review_passed: "审核通过",
  review_failed: "审核异常",
  succeeded: "已发布",
  failed: "执行失败",
};

const runStatusLabels: Record<string, string> = {
  fetching: "采集中",
  staged: "已暂存",
  cancelled: "已取消",
  succeeded: "已发布",
  failed: "失败",
  review_failed: "审核异常",
};

export default function CollectionJobs({ datasets, collectors, navigation, requestedCollection, onRequestHandled, requestedJobId, onJobRequestHandled }: {
  datasets: DatasetSummary[];
  collectors: CollectorDefinition[];
  navigation?: ReactNode;
  requestedCollection?: { datasetId: string; operation: CollectionOperation } | null;
  onRequestHandled?: () => void;
  requestedJobId?: string | null;
  onJobRequestHandled?: () => void;
}) {
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
  const [importJobs, setImportJobs] = useState<ImportJob[]>([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobPage, setJobPage] = useState(0);
  const jobLimit = 20;
  const [view, setView] = useState<"list" | "create">("list");
  const [creationDefaults, setCreationDefaults] = useState<{ datasetId: string; operation: CollectionOperation } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [runs, setRuns] = useState<Record<string, CollectionRun[]>>({});
  const [runTotals, setRunTotals] = useState<Record<string, number>>({});
  const [logs, setLogs] = useState<Record<string, CollectionLogEntry[]>>({});
  const [detailTab, setDetailTab] = useState<"runs" | "logs">("runs");
  const [logLevel, setLogLevel] = useState("ALL");
  const [progress, setProgress] = useState<Record<string, CollectionProgress>>({});
  const [review, setReview] = useState<{ jobId: string; data: CollectionReview } | null>(null);
  const [directoryManifest, setDirectoryManifest] = useState<{ jobId: string; data: ImportManifest } | null>(null);
  const jobsRef = useRef<CollectionJob[]>([]);
  const activeDatasets = useMemo(
    () => datasets.filter((dataset) => dataset.status === "active"),
    [datasets],
  );

  const jobPageRef = useRef(0);
  useEffect(() => {
    jobPageRef.current = jobPage;
  }, [jobPage]);

  const loadJobs = useCallback(async (silent = false, page = jobPageRef.current) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [data, imports] = await Promise.all([
        api.listCollectionJobs({ limit: jobLimit, offset: page * jobLimit }),
        api.listImportJobs(),
      ]);
      setJobs(data.items);
      setJobTotal(data.total);
      setImportJobs(imports);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载采集任务");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs(false, jobPage);
  }, [jobPage, loadJobs]);

  useEffect(() => {
    if (!requestedCollection) return;
    setCreationDefaults(requestedCollection);
    setView("create");
    onRequestHandled?.();
  }, [requestedCollection, onRequestHandled]);

  useEffect(() => {
    if (!requestedJobId) return;
    setView("list");
    setJobPage(0);
    setExpandedJobId(requestedJobId);
    setDetailTab("runs");
    void loadJobs(false, 0);
    void loadRuns(requestedJobId);
    window.setTimeout(() => document.getElementById(`job-${requestedJobId}`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 400);
    onJobRequestHandled?.();
  }, [requestedJobId]);

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  const hasRunning = jobs.some(
    (job) => ["queued", "running", "scanning", "importing", "cancelling"].includes(job.status),
  ) || runningJobId !== null;

  useEffect(() => {
    if (!hasRunning) return;
    let alive = true;

    async function poll() {
      const running = jobsRef.current.filter(
        (job) => ["queued", "running", "scanning", "importing", "cancelling"].includes(job.status),
      );
      const entries = await Promise.all(
        running.map(async (job) => {
          try {
            return [job.id, await api.getCollectionProgress(job.id)] as const;
          } catch {
            return null;
          }
        }),
      );
      if (!alive) return;
      setProgress((current) => {
        const next = { ...current };
        for (const entry of entries) if (entry) next[entry[0]] = entry[1];
        return next;
      });
      await loadJobs(true, jobPage);
      if (expandedJobId && running.some((job) => job.id === expandedJobId)) {
        if (detailTab === "logs") await loadLogs(expandedJobId);
        else await loadRuns(expandedJobId);
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), 2500);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [hasRunning, loadJobs, expandedJobId, detailTab, jobPage]);

  async function uploadExisting(job: CollectionJob, file: File) {
    setNotice(null);
    setError(null);
    try {
      await api.uploadCollectionFile(job.id, file);
      setNotice(`文件 ${file.name} 已进入 staging，等待后续校验。`);
      await loadJobs();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "文件上传失败");
    }
  }

  async function executeJob(job: CollectionJob) {
    setRunningJobId(job.id);
    setNotice(null);
    setError(null);
    try {
      await api.executeCollectionJob(job.id);
      setNotice("任务已提交后台执行，可以关闭页面或继续操作。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采集任务执行失败");
    } finally {
      setRunningJobId(null);
      await Promise.all([
        loadJobs(true),
        loadRuns(job.id),
        logs[job.id] ? loadLogs(job.id) : Promise.resolve(),
      ]);
    }
  }

  async function retryJob(job: CollectionJob) {
    let retriedJobId: string | null = null;
    setRetryingJobId(job.id);
    setNotice(null);
    setError(null);
    try {
      const retried = await api.retryCollectionJob(job.id);
      retriedJobId = retried.id;
      setRetryingJobId(null);
      setRunningJobId(retried.id);
      setExpandedJobId(retried.id);
      setDetailTab("runs");
      await loadJobs(true);
      await api.executeCollectionJob(retried.id);
      setNotice("重试任务已提交后台执行，并已切换到新任务。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "重试任务失败");
    } finally {
      setRetryingJobId(null);
      setRunningJobId(null);
      await Promise.all([
        loadJobs(true),
        loadRuns(retriedJobId ?? job.id),
        retriedJobId && logs[retriedJobId] ? loadLogs(retriedJobId) : Promise.resolve(),
      ]);
    }
  }

  async function loadRuns(jobId: string, offset = 0, append = false) {
    try {
      const data = await api.listCollectionRuns(jobId, 100, offset);
      setRuns((current) => ({
        ...current,
        [jobId]: append ? [...(current[jobId] ?? []), ...data.items] : data.items,
      }));
      setRunTotals((current) => ({ ...current, [jobId]: data.total }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载执行明细");
    }
  }

  async function loadLogs(jobId: string, level = logLevel) {
    try {
      const data = await api.listCollectionLogs(jobId, 500, level === "ALL" ? undefined : level);
      setLogs((current) => ({ ...current, [jobId]: data.entries }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载运行日志");
    }
  }

  async function toggleJob(job: CollectionJob) {
    if (expandedJobId === job.id) {
      setExpandedJobId(null);
      return;
    }
    setExpandedJobId(job.id);
    setDetailTab("runs");
    if (!runs[job.id]) await loadRuns(job.id);
  }

  async function selectDetailTab(jobId: string, tab: "runs" | "logs") {
    setDetailTab(tab);
    if (tab === "logs" && !logs[jobId]) await loadLogs(jobId);
    if (tab === "runs" && !runs[jobId]) await loadRuns(jobId);
  }

  async function showReview(job: CollectionJob) {
    setError(null);
    try {
      setReview({ jobId: job.id, data: await api.getCollectionReview(job.id) });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取审核报告");
    }
  }

  async function showDirectoryManifest(importJob: ImportJob) {
    setError(null);
    try {
      setDirectoryManifest({ jobId: importJob.collection_job_id ?? importJob.id, data: await api.getImportManifest(importJob.id) });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取目录扫描清单");
    }
  }

  async function executeDirectoryImport(importJob: ImportJob) {
    setRunningJobId(importJob.collection_job_id ?? importJob.id);
    setError(null);
    try {
      await api.executeImportJob(importJob.id);
      setNotice("目录导入已提交，后台正在发布分区。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交目录导入失败");
    } finally {
      setRunningJobId(null);
      await loadJobs(true, jobPage);
    }
  }

  async function cancelDirectoryImport(importJob: ImportJob) {
    setError(null);
    try {
      await api.cancelImportJob(importJob.id);
      setNotice("已请求取消目录任务。");
      await loadJobs(true, jobPage);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消目录任务失败");
    }
  }

  async function cancelJob(job: CollectionJob) {
    if (confirming !== `${job.id}:cancel`) {
      setConfirming(`${job.id}:cancel`);
      setNotice("再次点击“确认取消”即可停止任务；已经发布的分区会保留。");
      return;
    }
    setConfirming(null);
    setError(null);
    setNotice(null);
    try {
      const cancelled = await api.cancelCollectionJob(job.id);
      setNotice(cancelled.status === "cancelled" ? "排队任务已取消。" : "已请求取消，当前分区处理完后停止。");
      await loadJobs();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消任务失败");
    }
  }

  async function deleteJob(job: CollectionJob) {
    if (confirming !== `${job.id}:delete`) {
      setConfirming(`${job.id}:delete`);
      return;
    }
    setConfirming(null);
    setError(null);
    setNotice(null);
    try {
      await api.deleteCollectionJob(job.id);
      if (jobs.length === 1 && jobPage > 0) {
        setJobPage(jobPage - 1);
      } else {
        await loadJobs(false, jobPage);
      }
      setNotice("任务记录已删除。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除任务失败");
    }
  }

  if (view === "create") {
    return (
      <CreateCollectionJob
        datasets={activeDatasets}
        collectors={collectors}
        initialDatasetId={creationDefaults?.datasetId}
        initialOperation={creationDefaults?.operation}
        onCancel={() => { setCreationDefaults(null); setView("list"); }}
        onComplete={async (message) => {
          setNotice(message);
          setCreationDefaults(null);
          setView("list");
          setJobPage(0);
          await loadJobs(false, 0);
        }}
      />
    );
  }

  const stagedCount = jobs.filter((job) => job.status === "staged").length;
  const waitingCount = jobs.filter((job) => job.status === "awaiting_file").length;
  const pageCount = Math.max(1, Math.ceil(jobTotal / jobLimit));
  const failedReviewRuns = review?.data.runs?.filter((run) => !run.passed) ?? [];
  const topLevelErrors = review?.data.errors ?? [];

  return (
    <div className="page">
      {navigation}
      <header className="page-header">
        <div>
          <p className="eyebrow">COLLECTION JOBS</p>
          <h1>采集</h1>
          <p className="subtitle">统一管理采集器任务和手动文件入库。</p>
        </div>
        <button className="primary-button" onClick={() => setView("create")} disabled={!activeDatasets.length}>
          <Plus size={17} />创建任务
        </button>
      </header>

      <section className="summary-strip jobs-summary">
        <div><span>任务总数</span><strong>{jobTotal}</strong></div>
        <div><span>本页等待文件</span><strong>{waitingCount}</strong></div>
        <div><span>本页已进入临时区</span><strong>{stagedCount}</strong></div>
        <div><span>可采集数据集</span><strong>{activeDatasets.length}</strong></div>
      </section>

      {notice && <div className="notice-banner"><CheckCircle2 size={17} />{notice}</div>}
      {error && <div className="form-error"><AlertCircle size={17} />{error}</div>}
      {review && (
        <section className="review-report">
          <div className="review-summary">
            <div><strong>{review.data.passed ? "审核通过" : "审核异常"}</strong><span>任务 {review.jobId.slice(0, 8)}</span></div>
            <div><span>审核器</span><code>{review.data.reviewer}</code></div>
            <div><span>数据行数</span><strong>{review.data.row_count.toLocaleString()}</strong></div>
            <div><span>异常数量</span><strong>{review.data.error_count}</strong></div>
            <button type="button" className="toolbar-button" onClick={() => setReview(null)}>关闭</button>
          </div>
          {!review.data.passed && <div className="review-failures">
            <strong>异常详情</strong>
            {failedReviewRuns.map((run, index) => <div className="review-failure" key={`${run.partition_key ?? "run"}-${index}`}>
              <header><code>{run.partition_key ?? "未分区"}</code><span>{run.row_count.toLocaleString()} 行 · {run.error_count} 项异常</span></header>
              <ul>{(run.errors ?? []).map((item, errorIndex) => <li key={errorIndex}>{describeReviewError(item)}</li>)}</ul>
            </div>)}
            {!failedReviewRuns.length && topLevelErrors.length > 0 && <div className="review-failure"><ul>{topLevelErrors.map((item, index) => <li key={index}>{describeReviewError(item)}</li>)}</ul></div>}
            {!failedReviewRuns.length && !topLevelErrors.length && <div className="review-failure">审核报告未记录规则明细，请查看运行日志。</div>}
          </div>}
        </section>
      )}
      {directoryManifest && (
        <section className="review-report">
          <div className="review-summary">
            <div><strong>目录扫描清单</strong><span>任务 {directoryManifest.jobId.slice(0, 8)}</span></div>
            <div><span>文件</span><strong>{directoryManifest.data.files.length.toLocaleString()}</strong></div>
            <div><span>可导入</span><strong>{Number(directoryManifest.data.summary.ready ?? 0).toLocaleString()}</strong></div>
            <div><span>异常</span><strong>{Number(directoryManifest.data.summary.invalid ?? 0).toLocaleString()}</strong></div>
            <button type="button" className="toolbar-button" onClick={() => setDirectoryManifest(null)}>关闭</button>
          </div>
          <div className="import-manifest">
            <div className="import-manifest-head"><span>最多显示前 300 个文件</span><span>源目录 {directoryManifest.data.source_root}</span></div>
            <div className="import-file-table">
              <div className="import-file-row import-file-head"><span>交易日</span><span>状态</span><span>行数</span><span>错误</span></div>
              {directoryManifest.data.files.slice(0, 300).map((file) => (
                <div className={`import-file-row import-file-${file.status}`} key={`${file.partition_key}:${file.path}`}>
                  <code>{file.partition_key}</code>
                  <span>{file.status === "ready" ? "可导入" : file.status === "duplicate" ? "已存在" : "校验失败"}</span>
                  <span>{file.row_count?.toLocaleString() ?? "—"}</span>
                  <span>{file.errors.map((item) => String(item.rule ?? item.message ?? "")).join("；")}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
      {!activeDatasets.length && (
        <div className="warning-banner"><AlertCircle size={17} />请先在数据集页面启用至少一个数据集，才能创建采集任务。</div>
      )}

      <section className="panel">
        <div className="panel-toolbar">
          <div><h2>任务记录</h2><span>共 {jobTotal} 个任务</span></div>
          <button className="toolbar-button" onClick={() => void loadJobs()}><RefreshCw size={15} />刷新</button>
        </div>
        {loading ? (
          <div className="state-box"><div className="loader" /><p>正在加载采集任务…</p></div>
        ) : jobs.length === 0 ? (
          <div className="state-box empty-state"><Clock3 size={28} /><strong>还没有采集任务</strong><p>创建一个采集器任务，或手动导入本地文件。</p>{activeDatasets.length > 0 && <button className="secondary-button" onClick={() => setView("create")}><Plus size={16} />创建任务</button>}</div>
        ) : (
          <div className="jobs-table">
            <div className="job-row job-head"><span>数据集 / 任务</span><span>任务目的</span><span>输入方式</span><span>日期范围</span><span>文件</span><span>状态</span><span>操作</span></div>
            {jobs.map((job) => {
              const jobProgress = progress[job.id];
              const running = ["queued", "running", "scanning", "importing", "cancelling"].includes(job.status);
              const expanded = expandedJobId === job.id;
              const jobRuns = runs[job.id] ?? [];
              const jobLogs = logs[job.id] ?? [];
              const importJob = importJobs.find((item) => item.collection_job_id === job.id);
              const outputDatasetIds = collectorOutputDatasets(collectors, job);
              return (
              <div className="job-block" key={job.id} id={`job-${job.id}`}>
              <div className={expanded ? "job-row clickable expanded" : "job-row clickable"} onClick={() => void toggleJob(job)}>
                <span className="job-identity"><strong>{outputDatasetIds.length > 1 ? `联合更新 · ${outputDatasetIds.length} 个数据集` : datasetName(datasets, job.dataset_id)}</strong>{outputDatasetIds.map((id) => <code key={id}>{id}</code>)}<small>{job.id.slice(0, 8)} · 创建于 {formatDateTime(job.created_at)}</small>{job.retry_of_job_id && <small>重试自 {job.retry_of_job_id.slice(0, 8)}</small>}<small>{expanded ? "点击收起明细" : "点击查看明细"}</small></span>
                <span>{operationLabels[job.operation]}</span>
                <span className="job-source"><strong>{inputLabels[job.input_method]}</strong>{job.collector_key && <code>{job.collector_key}</code>}{job.collector_operation && <code>{job.collector_operation}</code>}</span>
                <span>{job.start_date ? <>{job.start_date}<br />至 {job.end_date}</> : "自动计算"}</span>
                <span className="file-cell">{job.source_file_name ? <><strong>{job.source_file_name}</strong><small>{formatBytes(job.source_size_bytes)}</small></> : job.status === "awaiting_file" ? <UploadFileButton onFile={(file) => void uploadExisting(job, file)} /> : "—"}</span>
                <span className="job-status-cell">
                  <JobStatus status={job.status} />
                  {jobProgress?.eta_seconds != null && jobProgress.expected_finish_at && (
                    <small className="job-eta">预计 {formatClock(jobProgress.expected_finish_at)} 完成 · 约 {formatDuration(jobProgress.eta_seconds)}</small>
                  )}
                </span>
                <span className="job-actions" onClick={(event) => event.stopPropagation()}>
                  {job.input_method === "collector" && job.status === "created" && <button type="button" className="mini-upload-button" disabled={runningJobId === job.id} onClick={() => void executeJob(job)}>{runningJobId === job.id ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}{runningJobId === job.id ? "提交中…" : "执行采集"}</button>}
                  {job.input_method === "collector" && (job.status === "failed" || job.status === "review_failed" || job.status === "cancelled") && <button type="button" className="mini-upload-button" disabled={retryingJobId === job.id} onClick={() => void retryJob(job)}><RefreshCw size={14} className={retryingJobId === job.id ? "spin" : ""} />{retryingJobId === job.id ? "重试中…" : "重试"}</button>}
                  {job.input_method === "directory_import" && job.status === "review_ready" && importJob && <button type="button" className="mini-upload-button" disabled={runningJobId === job.id} onClick={() => void executeDirectoryImport(importJob)}><ShieldCheck size={14} />确认导入</button>}
                  {job.input_method === "directory_import" && importJob?.manifest_path && <button type="button" className="mini-upload-button" onClick={() => void showDirectoryManifest(importJob)}><FileScan size={14} />扫描清单</button>}
                  {running && <button type="button" className="mini-upload-button danger-mini" disabled={job.status === "cancelling"} onClick={() => void (job.input_method === "directory_import" && importJob ? cancelDirectoryImport(importJob) : cancelJob(job))}><Ban size={14} />{job.status === "cancelling" ? "取消中…" : confirming === `${job.id}:cancel` ? "确认取消" : job.status === "queued" ? "取消排队" : "取消"}</button>}
                  {job.staged_path && (job.status === "review_ready" || job.status === "review_passed" || job.status === "review_failed" || job.status === "succeeded") && <button type="button" className="mini-upload-button" onClick={() => void showReview(job)}>查看审核</button>}
                  {!running && <button type="button" className={confirming === `${job.id}:delete` ? "mini-upload-button danger-mini" : "mini-upload-button quiet-mini"} onClick={() => void deleteJob(job)}><Trash2 size={14} />{confirming === `${job.id}:delete` ? "确认删除" : "删除"}</button>}
                </span>
              </div>
              {expanded && (
                <div className="job-detail">
                  <div className="job-detail-head">
                    <div className="job-detail-tabs">
                      <button type="button" className={detailTab === "runs" ? "active" : ""} onClick={() => void selectDetailTab(job.id, "runs")}>执行明细</button>
                      <button type="button" className={detailTab === "logs" ? "active" : ""} onClick={() => void selectDetailTab(job.id, "logs")}>运行日志</button>
                      {detailTab === "runs" && <span>{jobProgress ? formatProgress(jobProgress) : "尚无运行记录"}</span>}
                      {detailTab === "logs" && <span>最近 {jobLogs.length} 条</span>}
                      {detailTab === "logs" && (
                        <label className="log-level-filter">
                          <span>级别</span>
                          <select
                            value={logLevel}
                            onChange={(event) => {
                              const next = event.target.value;
                              setLogLevel(next);
                              void loadLogs(job.id, next);
                            }}
                          >
                            <option value="ALL">全部</option>
                            <option value="INFO">信息以上</option>
                            <option value="WARNING">警告以上</option>
                            <option value="ERROR">错误以上</option>
                          </select>
                        </label>
                      )}
                    </div>
                    <button type="button" className="toolbar-button" onClick={() => void (detailTab === "logs" ? loadLogs(job.id) : loadRuns(job.id))}><RefreshCw size={14} />刷新</button>
                  </div>
                  {job.error && <div className="job-error-banner"><AlertCircle size={15} /><span><strong>任务失败原因</strong>{job.error}</span></div>}
                  {detailTab === "runs" && (jobRuns.length ? (
                    <>
                    <div className="run-table">
                      <div className="run-row run-head"><span>分区</span><span>状态</span><span>行数</span><span>文件</span><span>错误</span></div>
                      {jobRuns.map((run) => (
                        <div className="run-row" key={run.id}>
                          <code>{run.partition_key}</code>
                          <span className={`run-status run-status-${run.status}`}>{runStatusLabels[run.status] ?? run.status}</span>
                          <span>{run.row_count === null ? "—" : run.row_count.toLocaleString()}</span>
                          <code className="run-path">{run.published_path ?? run.staged_path ?? "—"}</code>
                          <span className="run-error">{run.error ?? ""}</span>
                        </div>
                      ))}
                    </div>
                    <div className="run-footer">
                      <span>已显示 {jobRuns.length} / {runTotals[job.id] ?? jobRuns.length} 条</span>
                      {jobRuns.length < (runTotals[job.id] ?? jobRuns.length) && <button className="toolbar-button" type="button" onClick={() => void loadRuns(job.id, jobRuns.length, true)}>加载更多</button>}
                    </div>
                    </>
                  ) : (
                    <p className="job-detail-empty">还没有分区运行记录。</p>
                  ))}
                  {detailTab === "logs" && (jobLogs.length ? (
                    <div className="job-log-list">
                      {jobLogs.map((entry, index) => (
                        <div className={`job-log-row log-level-${String(entry.level).toLowerCase()}`} key={`${entry.timestamp}-${index}`}>
                          <time>{formatLogTime(entry.timestamp)}</time>
                          <span className="job-log-level">{logLevelLabel(entry.level)}</span>
                          <div><strong>{logEventLabel(entry.event)}</strong>{formatLogFields(entry) && <small>{formatLogFields(entry)}</small>}{typeof entry.exception === "string" && <pre>{entry.exception}</pre>}</div>
                        </div>
                      ))}
                    </div>
                  ) : <p className="job-detail-empty">该任务还没有运行日志。</p>)}
                </div>
              )}
              </div>
              );
            })}
          </div>
        )}
        {jobTotal > jobLimit && (
          <div className="job-pagination">
            <span>共 {jobTotal} 个任务</span>
            <button className="toolbar-button" type="button" disabled={jobPage === 0} onClick={() => setJobPage((page) => Math.max(0, page - 1))}>上一页</button>
            <span>第 {jobPage + 1} / {pageCount} 页</span>
            <button className="toolbar-button" type="button" disabled={(jobPage + 1) * jobLimit >= jobTotal} onClick={() => setJobPage((page) => page + 1)}>下一页</button>
          </div>
        )}
      </section>
      <p className="staging-note"><AlertCircle size={14} />“已进入临时区”只表示文件上传成功，尚未完成解析、校验和正式发布。</p>
    </div>
  );
}

function CreateCollectionJob(props: {
  datasets: DatasetSummary[];
  collectors: CollectorDefinition[];
  initialDatasetId?: string;
  initialOperation?: CollectionOperation;
  onCancel: () => void;
  onComplete: (message: string) => Promise<void>;
}) {
  const initialDataset = props.datasets.find((dataset) => dataset.id === props.initialDatasetId);
  const initialOperation = props.initialOperation ?? "initial";
  const hasRequestedBinding = Boolean(initialDataset && resolveCollectorBinding(initialDataset, initialOperation));
  const [datasetId, setDatasetId] = useState(initialDataset?.id ?? props.datasets[0]?.id ?? "");
  const [operation, setOperation] = useState<CollectionOperation>(initialOperation);
  const [inputMethod, setInputMethod] = useState<CollectionInputMethod>(hasRequestedBinding ? "collector" : "file_import");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parameterValues, setParameterValues] = useState<Record<string, string>>({});
  const [scanners, setScanners] = useState<ScannerDefinition[]>([]);
  const [scannerOperation, setScannerOperation] = useState("");
  const [sourceRoot, setSourceRoot] = useState("");
  const [transferMode, setTransferMode] = useState<"move" | "copy">("move");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const selectedDataset = props.datasets.find((dataset) => dataset.id === datasetId);
  const supportedPurposes = selectedDataset ? collectorPurposes(selectedDataset) : [];
  const selectedBinding = selectedDataset ? resolveCollectorBinding(selectedDataset, operation) : undefined;
  const selectedCollector = props.collectors.find((item) => item.key === selectedBinding?.collector_key);
  const selectedCollectorOperation = selectedCollector?.operations.find((item) => item.key === selectedBinding?.operation);
  const collectorParameters = (selectedCollectorOperation?.parameters ?? []).filter((item) => operation !== "repair" || !["start_date", "end_date"].includes(item.name));
  const directoryOperations = scanners.flatMap((scanner) => scanner.operations.map((item) => ({ ...item, scanner_key: scanner.key, scanner_name: scanner.name }))).filter((item) => item.dataset_id === datasetId);
  const selectedDirectoryOperation = directoryOperations.find((item) => item.key === scannerOperation) ?? directoryOperations[0];
  const firstDirectoryDatasetId = props.datasets.find((dataset) => scanners.some((scanner) => scanner.operations.some((item) => item.dataset_id === dataset.id)))?.id;

  useEffect(() => {
    void api.listScanners().then(setScanners).catch((reason) => setError(reason instanceof Error ? reason.message : "无法加载目录扫描器"));
  }, []);

  useEffect(() => {
    if (directoryOperations.length && !directoryOperations.some((item) => item.key === scannerOperation)) {
      setScannerOperation(directoryOperations[0].key);
    }
  }, [datasetId, scanners]);

  useEffect(() => {
    const defaults: Record<string, string> = {
      "wind.cn.stock.l2_order.sz": "/home/hhd_data/quantstone-data/imports/wind_l2/sz",
      "wind.cn.stock.l2_trade.sz": "/home/hhd_data/quantstone-data/imports/wind_l2/sz",
      "zhongtai.cn.stock.l2_order.sz": "/home/hhd_data/quantstone-data/imports/zhongtai_l2/sz",
      "zhongtai.cn.stock.l2_trade.sz": "/home/hhd_data/quantstone-data/imports/zhongtai_l2/sz",
    };
    if (inputMethod === "directory_import") setSourceRoot(defaults[datasetId] ?? "");
  }, [datasetId, inputMethod]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!datasetId) return setError("没有可用的已启用数据集。");
    const missingParameter = collectorParameters.find((item) => item.required && !parameterValues[item.name]?.trim());
    if (inputMethod === "collector" && !selectedCollectorOperation) return setError("没有找到该任务目的绑定的采集器操作。");
    if (missingParameter) return setError(`请填写必填参数：${missingParameter.name}`);
    if (inputMethod === "file_import" && !file) return setError("请选择需要导入的文件。");
    if (inputMethod === "directory_import" && !selectedDirectoryOperation) return setError("该数据集没有可用的目录扫描器。");
    if (inputMethod === "directory_import" && !sourceRoot.trim()) return setError("请填写服务器源目录。");
    if (inputMethod === "collector" && operation === "repair" && (!startDate || !endDate)) return setError("修复任务必须选择开始日期和结束日期；修复单日时请选择相同日期。");
    if (startDate && endDate && startDate > endDate) return setError("开始日期不能晚于结束日期。");

    const parameters = Object.fromEntries(
      collectorParameters
        .filter((item) => parameterValues[item.name] !== undefined && parameterValues[item.name] !== "")
        .map((item) => [item.name, convertParameterValue(item, parameterValues[item.name])]),
    );

    const payload: CollectionJobCreatePayload = {
      dataset_id: datasetId,
      operation,
      input_method: inputMethod,
      start_date: inputMethod === "collector" && operation === "repair" ? startDate : null,
      end_date: inputMethod === "collector" && operation === "repair" ? endDate : null,
      collector_key: null,
      parameters,
    };

    setSubmitting(true);
    try {
      if (inputMethod === "directory_import" && selectedDirectoryOperation) {
        const importJob = await api.createImportJob({
          dataset_id: datasetId,
          scanner_key: selectedDirectoryOperation.scanner_key,
          operation: selectedDirectoryOperation.key,
          purpose: operation,
          source_root: sourceRoot.trim(),
          transfer_mode: transferMode,
          start_date: startDate || null,
          end_date: endDate || null,
        });
        await props.onComplete(`目录扫描任务 ${importJob.id.slice(0, 8)} 已创建，扫描完成后请确认导入。`);
        return;
      }
      const job = await api.createCollectionJob(payload);
      if (inputMethod === "file_import" && file) {
        try {
          await api.uploadCollectionFile(job.id, file);
        } catch (reason) {
          const message = reason instanceof Error ? reason.message : "文件上传失败";
          throw new Error(`任务已经创建，但文件未上传：${message}`);
        }
        await props.onComplete(`任务已创建，文件 ${file.name} 已进入 staging。`);
      } else {
        await props.onComplete("采集任务已创建，可以在任务列表中执行采集器。");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="page create-page" onSubmit={(event) => void submit(event)}>
      <header className="page-header compact">
        <div><button type="button" className="back-button" onClick={props.onCancel}><ArrowLeft size={16} />返回采集任务</button><h1>创建采集任务</h1><p className="subtitle">选择任务目的和数据输入方式。</p></div>
        <div className="header-actions"><button type="button" className="ghost-button" onClick={props.onCancel}>取消</button><button className="primary-button" disabled={submitting}>{submitting ? "正在提交…" : "创建任务"}</button></div>
      </header>
      {error && <div className="form-error"><AlertCircle size={17} />{error}</div>}

      <section className="form-section job-form-section">
        <div className="section-number">01</div><div className="section-intro"><h2>任务目标</h2><p>确定目标数据集以及本次任务的处理目的。</p></div>
        <div className="form-content">
          <div className="form-grid two-columns no-margin">
            <label className="input-field"><span>数据集<b>*</b></span><select value={datasetId} onChange={(event) => { const next = props.datasets.find((item) => item.id === event.target.value); const nextPurposes = next ? collectorPurposes(next) : []; setDatasetId(event.target.value); if (inputMethod === "collector" && !nextPurposes.includes(operation) && nextPurposes.length) setOperation(nextPurposes[0]); }}>{props.datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.display_name} · {dataset.id}</option>)}</select></label>
            <label className="input-field"><span>任务目的<b>*</b></span><select value={operation} onChange={(event) => setOperation(event.target.value as CollectionOperation)}>{Object.entries(operationLabels).filter(([value]) => inputMethod !== "collector" || supportedPurposes.includes(value as CollectionOperation)).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </div>
          <div className="operation-help">{operationDescription(operation)}</div>
          {inputMethod === "collector" && selectedCollectorOperation && <div className="collector-parameter-form"><div className="binding-preview"><strong>{selectedCollector?.name}</strong><span>{selectedCollector?.key} · {selectedCollectorOperation.key}</span><span>{operation === "repair" ? "使用该采集器重新获取指定交易日，并以新 delta 替换当前逻辑分区。" : selectedCollectorOperation.description}</span></div>{operation === "repair" ? <div className="form-grid two-columns date-grid"><label className="input-field"><span>开始日期<b>*</b></span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label className="input-field"><span>结束日期<b>*</b></span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /><small>修复单日时，开始和结束选择同一天。</small></label></div> : selectedCollectorOperation.parameters.length ? <div className="form-grid two-columns date-grid">{selectedCollectorOperation.parameters.map((parameter) => <CollectorParameterInput key={parameter.name} parameter={parameter} value={parameterValues[parameter.name] ?? ""} onChange={(value) => setParameterValues((current) => ({ ...current, [parameter.name]: value }))} />)}</div> : <div className="operation-help">该操作不需要运行参数。</div>}</div>}
        </div>
      </section>

      <section className="form-section job-form-section">
        <div className="section-number">02</div><div className="section-intro"><h2>数据输入</h2><p>采集器、文件上传和服务器目录使用同一校验与发布流程。</p></div>
        <div className="form-content">
          <div className="method-cards">
            <button type="button" className={inputMethod === "file_import" ? "method-card selected" : "method-card"} onClick={() => setInputMethod("file_import")}><FileUp size={22} /><strong>手动文件</strong><span>上传本地文件到 staging</span></button>
            <button type="button" className={inputMethod === "collector" ? "method-card selected" : "method-card"} onClick={() => { setInputMethod("collector"); if (!supportedPurposes.includes(operation) && supportedPurposes.length) setOperation(supportedPurposes[0]); }}><RefreshCw size={22} /><strong>采集器</strong><span>由采集器获取供应商数据</span></button>
            <button type="button" className={inputMethod === "directory_import" ? "method-card selected" : "method-card"} onClick={() => { setInputMethod("directory_import"); if (!directoryOperations.length && firstDirectoryDatasetId) setDatasetId(firstDirectoryDatasetId); }}><FolderInput size={22} /><strong>服务器目录</strong><span>扫描目录，确认清单后导入</span></button>
          </div>
          {inputMethod === "file_import" ? (
            <label className={file ? "file-drop selected" : "file-drop"}><input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><UploadCloud size={25} /><strong>{file ? file.name : "选择需要导入的文件"}</strong><span>{file ? formatBytes(file.size) : "文件将先进入临时区，不会直接写入正式数据"}</span></label>
          ) : inputMethod === "directory_import" ? (
            <div className="collector-parameter-form">
              <div className="binding-preview"><strong>{selectedDirectoryOperation?.scanner_name ?? "该数据集没有目录扫描器"}</strong><span>{selectedDirectoryOperation ? `${selectedDirectoryOperation.scanner_key} · ${selectedDirectoryOperation.key}` : "请更换数据集"}</span><span>{selectedDirectoryOperation?.description ?? "服务器目录输入只对已注册扫描器的数据集开放。"}</span></div>
              {selectedDirectoryOperation && <div className="form-grid two-columns date-grid">
                <label className="input-field"><span>扫描操作<b>*</b></span><select value={selectedDirectoryOperation.key} onChange={(event) => setScannerOperation(event.target.value)}>{directoryOperations.map((item) => <option key={`${item.scanner_key}:${item.key}`} value={item.key}>{item.name}</option>)}</select></label>
                <label className="input-field"><span>源目录<b>*</b></span><input value={sourceRoot} onChange={(event) => setSourceRoot(event.target.value)} placeholder="/home/hhd_data/quantstone-data/imports/..." /></label>
                <label className="input-field"><span>文件处理</span><select value={transferMode} onChange={(event) => setTransferMode(event.target.value as "move" | "copy")}><option value="move">移动（同盘快速，成功后删除源文件）</option><option value="copy">复制（保留源文件）</option></select></label>
                <label className="input-field"><span>开始日期</span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
                <label className="input-field"><span>结束日期</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label>
              </div>}
            </div>
          ) : <div className="operation-help">采集器由数据集预先绑定，创建任务后在任务列表执行。</div>}
        </div>
      </section>
    </form>
  );
}

function resolveCollectorBinding(dataset: DatasetSummary, purpose: CollectionOperation) {
  const exact = dataset.collection_bindings.find((binding) => binding.purpose === purpose);
  if (exact || purpose !== "repair" || !dataset.storage_policy?.logical_partition_field) return exact;
  return dataset.collection_bindings.find((binding) => binding.purpose === "incremental")
    ?? dataset.collection_bindings.find((binding) => binding.purpose === "initial");
}

function collectorPurposes(dataset: DatasetSummary): CollectionOperation[] {
  const purposes = dataset.collection_bindings.map((binding) => binding.purpose);
  if (dataset.storage_policy?.logical_partition_field && resolveCollectorBinding(dataset, "repair")) {
    purposes.push("repair");
  }
  return [...new Set(purposes)];
}

function CollectorParameterInput(props: {
  parameter: CollectorParameter;
  value: string;
  onChange: (value: string) => void;
}) {
  const { parameter } = props;
  if (parameter.data_type === "boolean") {
    return <label className="input-field"><span>{parameter.name}{parameter.required && <b>*</b>}</span><select value={props.value} onChange={(event) => props.onChange(event.target.value)}><option value="">请选择</option><option value="true">是</option><option value="false">否</option></select><small>{parameter.description}</small></label>;
  }
  const inputType = parameter.data_type === "date" ? "date" : ["int", "integer", "int32", "int64", "float", "float32", "float64", "number"].includes(parameter.data_type) ? "number" : "text";
  return <label className="input-field"><span>{parameter.name}{parameter.required && <b>*</b>}</span><input type={inputType} value={props.value} onChange={(event) => props.onChange(event.target.value)} /><small>{parameter.description}</small></label>;
}

function convertParameterValue(parameter: CollectorParameter, value: string): unknown {
  if (parameter.data_type === "boolean") return value === "true";
  if (["int", "integer", "int32", "int64"].includes(parameter.data_type)) return Number.parseInt(value, 10);
  if (["float", "float32", "float64", "number"].includes(parameter.data_type)) return Number.parseFloat(value);
  return value;
}

function UploadFileButton({ onFile }: { onFile: (file: File) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <><input ref={input} className="hidden-file-input" type="file" onChange={(event) => { const file = event.target.files?.[0]; if (file) onFile(file); }} /><button className="mini-upload-button" type="button" onClick={() => input.current?.click()}><UploadCloud size={14} />上传文件</button></>;
}

function JobStatus({ status }: { status: CollectionJob["status"] }) {
  return <span className={`job-status job-status-${status}`}><i />{statusLabels[status]}</span>;
}

function datasetName(datasets: DatasetSummary[], id: string) {
  return datasets.find((dataset) => dataset.id === id)?.display_name ?? "未知数据集";
}

function collectorOutputDatasets(collectors: CollectorDefinition[], job: CollectionJob) {
  if (!job.collector_key || !job.collector_operation) return [job.dataset_id];
  const operation = collectors
    .find((collector) => collector.key === job.collector_key)
    ?.operations.find((item) => item.key === job.collector_operation);
  return operation?.datasets.length ? operation.datasets : [job.dataset_id];
}

function describeReviewError(error: Record<string, unknown>) {
  const rule = String(error.rule ?? "unknown");
  if (rule === "not_empty") return "接口返回 0 行，该日期没有可审核的数据。";
  if (rule === "partition_matches_trade_date") {
    const expected = error.expected ? `期望 ${String(error.expected)}` : "";
    const actual = Array.isArray(error.actual) ? `实际 ${error.actual.join("、")}` : error.actual ? `实际 ${String(error.actual)}` : "";
    return `数据日期与目标分区不一致${expected || actual ? `（${[expected, actual].filter(Boolean).join("，")}）` : ""}。`;
  }
  if (rule === "required_fields") return `缺少必需字段：${String(error.missing ?? error.fields ?? "未记录")}`;
  if (rule === "primary_key_not_null") return `主键存在空值：${String(error.fields ?? error.field ?? "未记录")}`;
  if (rule === "primary_key_unique") return `主键存在重复记录：${String(error.count ?? "数量未记录")}`;
  if (rule === "schema") return `字段结构不符合数据集契约：${String(error.message ?? "请检查字段名称和类型")}`;
  const detail = error.message ?? error.detail;
  return detail ? `${rule}：${String(detail)}` : `审核规则 ${rule} 未通过。`;
}

function formatProgress(progress: CollectionProgress) {
  const parts = [
    progress.expected_total
      ? `已发布 ${progress.succeeded} / ${progress.expected_total}`
      : `已发布 ${progress.succeeded}`,
  ];
  if (progress.percent !== null) parts.push(`${progress.percent}%`);
  if (progress.failed) parts.push(`失败 ${progress.failed}`);
  if (progress.latest_partition) parts.push(`最新 ${progress.latest_partition}`);
  if (progress.eta_seconds !== null && progress.expected_finish_at) {
    parts.push(`预计 ${formatClock(progress.expected_finish_at)} 完成（约 ${formatDuration(progress.eta_seconds)}）`);
  } else if (progress.status === "running" && progress.eta_basis === "insufficient_data") {
    parts.push("预计完成时间计算中");
  }
  if (progress.status !== "queued" && progress.status !== "running" && progress.status !== "cancelling" && progress.elapsed_seconds !== null) {
    parts.push(`耗时 ${formatDuration(progress.elapsed_seconds)}`);
  }
  return parts.join(" · ");
}

function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`;
}

function formatClock(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatBytes(value: number | null) {
  if (value === null) return "";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function formatDateTime(value: string) {
  // SQLite 返回的 UTC 时间可能不带时区后缀，显式补 Z 后再转换为浏览器本地时间。
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

const logEventLabels: Record<string, string> = {
  collection_job_created: "任务已创建",
  collection_job_started: "任务开始执行",
  collection_job_queued: "任务已进入后台队列",
  collection_run_started: "开始采集分区",
  collection_artifact_staged: "采集结果已暂存",
  review_completed: "数据审核完成",
  partition_published: "分区发布完成",
  collection_job_completed: "任务执行完成",
  collection_run_failed: "分区执行失败",
  collection_job_failed: "任务执行失败",
  collection_job_cancelled: "任务已取消",
  collection_job_retried: "已创建重试任务",
  rate_limit_wait: "等待供应商限流窗口",
  operation_retry_scheduled: "供应商调用失败，准备重试",
};

const logFieldLabels: Record<string, string> = {
  partition_key: "分区",
  row_count: "行数",
  error_count: "异常数",
  passed: "审核通过",
  attempt: "第几次",
  max_attempts: "最多尝试",
  pause_seconds: "等待秒数",
  waited_seconds: "限流等待秒数",
  status: "状态",
  error: "错误",
  file_path: "文件",
  size_bytes: "字节",
  operation: "操作",
  collector: "采集器",
};

function logEventLabel(event: string) {
  return logEventLabels[event] ?? event;
}

function logLevelLabel(level: string) {
  return ({ DEBUG: "调试", INFO: "信息", WARNING: "警告", ERROR: "错误", CRITICAL: "严重" } as Record<string, string>)[level] ?? level;
}

function formatLogTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function formatLogFields(entry: CollectionLogEntry) {
  return Object.entries(entry)
    .filter(([key, value]) => !["timestamp", "level", "logger", "event", "job_id", "run_id", "dataset_id", "exception"].includes(key) && value !== null && value !== "")
    .map(([key, value]) => `${logFieldLabels[key] ?? key}=${typeof value === "object" ? JSON.stringify(value) : String(value)}`)
    .join(" · ");
}

function operationDescription(operation: CollectionOperation) {
  const descriptions: Record<CollectionOperation, string> = {
    initial: "为尚未采集的数据集建立初始时间范围。",
    incremental: "未来由 Catalog 与交易日历计算新增数据和历史缺口。",
    repair: "针对明确的缺失或异常日期范围重新获取数据。",
    replace: "重新生成指定日期范围，并在发布阶段替换已有版本。",
  };
  return descriptions[operation];
}
