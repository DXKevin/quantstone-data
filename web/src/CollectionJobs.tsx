import {
  AlertCircle,
  ArrowLeft,
  Ban,
  CheckCircle2,
  Clock3,
  FileUp,
  Plus,
  RefreshCw,
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
} from "./api";

const operationLabels: Record<CollectionOperation, string> = {
  initial: "首次采集",
  incremental: "增量更新",
  repair: "缺口修复",
  replace: "范围重建",
};

const inputLabels: Record<CollectionInputMethod, string> = {
  collector: "采集器",
  file_import: "手动文件",
};

const statusLabels = {
  created: "已创建",
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

export default function CollectionJobs({ datasets, collectors, navigation, requestedCollection, onRequestHandled }: {
  datasets: DatasetSummary[];
  collectors: CollectorDefinition[];
  navigation?: ReactNode;
  requestedCollection?: { datasetId: string; operation: CollectionOperation } | null;
  onRequestHandled?: () => void;
}) {
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
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
  const [logs, setLogs] = useState<Record<string, CollectionLogEntry[]>>({});
  const [detailTab, setDetailTab] = useState<"runs" | "logs">("runs");
  const [progress, setProgress] = useState<Record<string, CollectionProgress>>({});
  const [review, setReview] = useState<{ jobId: string; data: CollectionReview } | null>(null);
  const jobsRef = useRef<CollectionJob[]>([]);
  const activeDatasets = useMemo(
    () => datasets.filter((dataset) => dataset.status === "active"),
    [datasets],
  );

  const loadJobs = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      setJobs(await api.listCollectionJobs());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载采集任务");
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    if (!requestedCollection) return;
    setCreationDefaults(requestedCollection);
    setView("create");
    onRequestHandled?.();
  }, [requestedCollection, onRequestHandled]);

  useEffect(() => {
    jobsRef.current = jobs;
  }, [jobs]);

  const hasRunning = jobs.some(
    (job) => job.status === "queued" || job.status === "running" || job.status === "cancelling",
  ) || runningJobId !== null;

  useEffect(() => {
    if (!hasRunning) return;
    let alive = true;

    async function poll() {
      const running = jobsRef.current.filter(
        (job) => job.status === "queued" || job.status === "running" || job.status === "cancelling",
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
      await loadJobs(true);
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
  }, [hasRunning, loadJobs, expandedJobId, detailTab]);

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

  async function loadRuns(jobId: string) {
    try {
      const data = await api.listCollectionRuns(jobId);
      setRuns((current) => ({ ...current, [jobId]: data }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载执行明细");
    }
  }

  async function loadLogs(jobId: string) {
    try {
      const data = await api.listCollectionLogs(jobId);
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

  async function cancelJob(job: CollectionJob) {
    if (confirming !== `${job.id}:cancel`) {
      setConfirming(`${job.id}:cancel`);
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
      await loadJobs();
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
          await loadJobs();
        }}
      />
    );
  }

  const stagedCount = jobs.filter((job) => job.status === "staged").length;
  const waitingCount = jobs.filter((job) => job.status === "awaiting_file").length;
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
        <div><span>任务总数</span><strong>{jobs.length}</strong></div>
        <div><span>等待文件</span><strong>{waitingCount}</strong></div>
        <div><span>已进入临时区</span><strong>{stagedCount}</strong></div>
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
      {!activeDatasets.length && (
        <div className="warning-banner"><AlertCircle size={17} />请先在数据集页面启用至少一个数据集，才能创建采集任务。</div>
      )}

      <section className="panel">
        <div className="panel-toolbar">
          <div><h2>任务记录</h2><span>{jobs.length} 个任务</span></div>
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
              const running = job.status === "queued" || job.status === "running" || job.status === "cancelling";
              const expanded = expandedJobId === job.id;
              const jobRuns = runs[job.id] ?? [];
              const jobLogs = logs[job.id] ?? [];
              return (
              <div className="job-block" key={job.id}>
              <div className={expanded ? "job-row clickable expanded" : "job-row clickable"} onClick={() => void toggleJob(job)}>
                <span className="job-identity"><strong>{datasetName(datasets, job.dataset_id)}</strong><code>{job.dataset_id}</code><small>{job.id.slice(0, 8)} · 创建于 {formatDateTime(job.created_at)}</small>{job.retry_of_job_id && <small>重试自 {job.retry_of_job_id.slice(0, 8)}</small>}<small>{expanded ? "点击收起明细" : "点击查看明细"}</small></span>
                <span>{operationLabels[job.operation]}</span>
                <span className="job-source"><strong>{inputLabels[job.input_method]}</strong>{job.collector_key && <code>{job.collector_key}</code>}{job.collector_operation && <code>{job.collector_operation}</code>}</span>
                <span>{job.start_date ? <>{job.start_date}<br />至 {job.end_date}</> : "自动计算"}</span>
                <span className="file-cell">{job.source_file_name ? <><strong>{job.source_file_name}</strong><small>{formatBytes(job.source_size_bytes)}</small></> : job.status === "awaiting_file" ? <UploadFileButton onFile={(file) => void uploadExisting(job, file)} /> : "—"}</span>
                <span className="job-status-cell">
                  <JobStatus status={job.status} />
                </span>
                <span className="job-actions" onClick={(event) => event.stopPropagation()}>
                  {job.input_method === "collector" && job.status === "created" && <button type="button" className="mini-upload-button" disabled={runningJobId === job.id} onClick={() => void executeJob(job)}>{runningJobId === job.id ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}{runningJobId === job.id ? "提交中…" : "执行采集"}</button>}
                  {job.input_method === "collector" && (job.status === "failed" || job.status === "review_failed" || job.status === "cancelled") && <button type="button" className="mini-upload-button" disabled={retryingJobId === job.id} onClick={() => void retryJob(job)}><RefreshCw size={14} className={retryingJobId === job.id ? "spin" : ""} />{retryingJobId === job.id ? "重试中…" : "重试"}</button>}
                  {running && <button type="button" className="mini-upload-button danger-mini" disabled={job.status === "cancelling"} onClick={() => void cancelJob(job)}><Ban size={14} />{job.status === "cancelling" ? "取消中…" : confirming === `${job.id}:cancel` ? "确认取消" : job.status === "queued" ? "取消排队" : "取消"}</button>}
                  {(job.status === "review_passed" || job.status === "review_failed" || job.status === "succeeded") && <button type="button" className="mini-upload-button" onClick={() => void showReview(job)}>查看审核</button>}
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
                    </div>
                    <button type="button" className="toolbar-button" onClick={() => void (detailTab === "logs" ? loadLogs(job.id) : loadRuns(job.id))}><RefreshCw size={14} />刷新</button>
                  </div>
                  {job.error && <div className="job-error-banner"><AlertCircle size={15} /><span><strong>任务失败原因</strong>{job.error}</span></div>}
                  {detailTab === "runs" && (jobRuns.length ? (
                    <div className="run-table">
                      <div className="run-row run-head"><span>分区</span><span>状态</span><span>行数</span><span>文件</span><span>错误</span></div>
                      {[...jobRuns].reverse().map((run) => (
                        <div className="run-row" key={run.id}>
                          <code>{run.partition_key}</code>
                          <span className={`run-status run-status-${run.status}`}>{runStatusLabels[run.status] ?? run.status}</span>
                          <span>{run.row_count === null ? "—" : run.row_count.toLocaleString()}</span>
                          <code className="run-path">{run.published_path ?? run.staged_path ?? "—"}</code>
                          <span className="run-error">{run.error ?? ""}</span>
                        </div>
                      ))}
                    </div>
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
  const hasRequestedBinding = initialDataset?.collection_bindings.some((binding) => binding.purpose === initialOperation) ?? false;
  const [datasetId, setDatasetId] = useState(initialDataset?.id ?? props.datasets[0]?.id ?? "");
  const [operation, setOperation] = useState<CollectionOperation>(initialOperation);
  const [inputMethod, setInputMethod] = useState<CollectionInputMethod>(hasRequestedBinding ? "collector" : "file_import");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parameterValues, setParameterValues] = useState<Record<string, string>>({});
  const selectedDataset = props.datasets.find((dataset) => dataset.id === datasetId);
  const supportedPurposes = selectedDataset?.collection_bindings.map((item) => item.purpose) ?? [];
  const selectedBinding = selectedDataset?.collection_bindings.find((item) => item.purpose === operation);
  const selectedCollector = props.collectors.find((item) => item.key === selectedBinding?.collector_key);
  const selectedCollectorOperation = selectedCollector?.operations.find((item) => item.key === selectedBinding?.operation);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!datasetId) return setError("没有可用的已启用数据集。");
    const missingParameter = selectedCollectorOperation?.parameters.find((item) => item.required && !parameterValues[item.name]?.trim());
    if (inputMethod === "collector" && !selectedCollectorOperation) return setError("没有找到该任务目的绑定的采集器操作。");
    if (missingParameter) return setError(`请填写必填参数：${missingParameter.name}`);
    if (inputMethod === "file_import" && !file) return setError("请选择需要导入的文件。");

    const parameters = Object.fromEntries(
      (selectedCollectorOperation?.parameters ?? [])
        .filter((item) => parameterValues[item.name] !== undefined && parameterValues[item.name] !== "")
        .map((item) => [item.name, convertParameterValue(item, parameterValues[item.name])]),
    );

    const payload: CollectionJobCreatePayload = {
      dataset_id: datasetId,
      operation,
      input_method: inputMethod,
      start_date: null,
      end_date: null,
      collector_key: null,
      parameters,
    };

    setSubmitting(true);
    try {
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
            <label className="input-field"><span>数据集<b>*</b></span><select value={datasetId} onChange={(event) => { const next = props.datasets.find((item) => item.id === event.target.value); const nextPurposes = next?.collection_bindings.map((item) => item.purpose) ?? []; setDatasetId(event.target.value); if (inputMethod === "collector" && !nextPurposes.includes(operation) && nextPurposes.length) setOperation(nextPurposes[0]); }}>{props.datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.display_name} · {dataset.id}</option>)}</select></label>
            <label className="input-field"><span>任务目的<b>*</b></span><select value={operation} onChange={(event) => setOperation(event.target.value as CollectionOperation)}>{Object.entries(operationLabels).filter(([value]) => inputMethod === "file_import" || supportedPurposes.includes(value as CollectionOperation)).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
          </div>
          <div className="operation-help">{operationDescription(operation)}</div>
          {inputMethod === "collector" && selectedCollectorOperation && <div className="collector-parameter-form"><div className="binding-preview"><strong>{selectedCollector?.name}</strong><span>{selectedCollector?.key} · {selectedCollectorOperation.key}</span><span>{selectedCollectorOperation.description}</span></div>{selectedCollectorOperation.parameters.length ? <div className="form-grid two-columns date-grid">{selectedCollectorOperation.parameters.map((parameter) => <CollectorParameterInput key={parameter.name} parameter={parameter} value={parameterValues[parameter.name] ?? ""} onChange={(value) => setParameterValues((current) => ({ ...current, [parameter.name]: value }))} />)}</div> : <div className="operation-help">该操作不需要运行参数。</div>}</div>}
        </div>
      </section>

      <section className="form-section job-form-section">
        <div className="section-number">02</div><div className="section-intro"><h2>数据输入</h2><p>采集器与手动文件只是获取方式，后续使用同一校验和发布流程。</p></div>
        <div className="form-content">
          <div className="method-cards">
            <button type="button" className={inputMethod === "file_import" ? "method-card selected" : "method-card"} onClick={() => setInputMethod("file_import")}><FileUp size={22} /><strong>手动文件</strong><span>上传本地文件到 staging</span></button>
            <button type="button" className={inputMethod === "collector" ? "method-card selected" : "method-card"} onClick={() => { setInputMethod("collector"); if (!supportedPurposes.includes(operation) && supportedPurposes.length) setOperation(supportedPurposes[0]); }}><RefreshCw size={22} /><strong>采集器</strong><span>由采集器获取供应商数据</span></button>
          </div>
          {inputMethod === "file_import" ? (
            <label className={file ? "file-drop selected" : "file-drop"}><input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /><UploadCloud size={25} /><strong>{file ? file.name : "选择需要导入的文件"}</strong><span>{file ? formatBytes(file.size) : "文件将先进入临时区，不会直接写入正式数据"}</span></label>
          ) : <div className="operation-help">采集器由数据集预先绑定，创建任务后在任务列表执行。</div>}
        </div>
      </section>
    </form>
  );
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
  return parts.join(" · ");
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
  return ({ INFO: "信息", WARNING: "警告", ERROR: "错误", CRITICAL: "严重" } as Record<string, string>)[level] ?? level;
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
