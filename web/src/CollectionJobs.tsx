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
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type CollectionInputMethod,
  type CollectorDefinition,
  type CollectorParameter,
  type CollectionJob,
  type CollectionJobCreatePayload,
  type CollectionOperation,
  type CollectionProgress,
  type CollectionReview,
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

export default function CollectionJobs({ datasets, collectors }: { datasets: DatasetSummary[]; collectors: CollectorDefinition[] }) {
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
  const [view, setView] = useState<"list" | "create">("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Record<string, CollectionProgress>>({});
  const [review, setReview] = useState<{ jobId: string; data: CollectionReview } | null>(null);
  const jobsRef = useRef<CollectionJob[]>([]);
  const activeDatasets = useMemo(
    () => datasets.filter((dataset) => dataset.status === "active"),
    [datasets],
  );

  const loadJobs = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    setError(null);
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
    jobsRef.current = jobs;
  }, [jobs]);

  const hasRunning = jobs.some(
    (job) => job.status === "running" || job.status === "cancelling",
  ) || runningJobId !== null;

  useEffect(() => {
    if (!hasRunning) return;
    let alive = true;

    async function poll() {
      const running = jobsRef.current.filter(
        (job) => job.status === "running" || job.status === "cancelling",
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
    }

    void poll();
    const timer = window.setInterval(() => void poll(), 2500);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [hasRunning, loadJobs]);

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
      const result = await api.executeCollectionJob(job.id);
      if (result.status === "review_failed") {
        const report = await api.getCollectionReview(job.id);
        setReview({ jobId: job.id, data: report });
        setNotice("采集已停止：部分日期审核异常，具体原因已展开。");
      } else {
        setNotice(result.status === "succeeded" ? "采集、审核和发布均已完成。" : "采集完成，暂存数据审核通过。");
      }
      await loadJobs();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "采集任务执行失败");
    } finally {
      setRunningJobId(null);
    }
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
    if (!window.confirm(`确定取消任务 ${job.id.slice(0, 8)}？已发布的分区会保留。`)) return;
    setError(null);
    setNotice(null);
    try {
      await api.cancelCollectionJob(job.id);
      setNotice("已请求取消，当前分区处理完后停止。");
      await loadJobs();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消任务失败");
    }
  }

  async function deleteJob(job: CollectionJob) {
    if (!window.confirm(`确定删除任务记录 ${job.id.slice(0, 8)}？已发布的数据不会被删除。`)) return;
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
        onCancel={() => setView("list")}
        onComplete={async (message) => {
          setNotice(message);
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
      <header className="page-header">
        <div>
          <p className="eyebrow">COLLECTION JOBS</p>
          <h1>采集任务</h1>
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
              const running = job.status === "running" || job.status === "cancelling";
              return (
              <div className="job-row" key={job.id}>
                <span className="job-identity"><strong>{datasetName(datasets, job.dataset_id)}</strong><code>{job.dataset_id}</code><small>{job.id.slice(0, 8)}</small></span>
                <span>{operationLabels[job.operation]}</span>
                <span className="job-source"><strong>{inputLabels[job.input_method]}</strong>{job.collector_key && <code>{job.collector_key} · {job.collector_operation}</code>}</span>
                <span>{job.start_date ? <>{job.start_date}<br />至 {job.end_date}</> : "自动计算"}</span>
                <span className="file-cell">{job.source_file_name ? <><strong>{job.source_file_name}</strong><small>{formatBytes(job.source_size_bytes)}</small></> : job.status === "awaiting_file" ? <UploadFileButton onFile={(file) => void uploadExisting(job, file)} /> : "—"}</span>
                <span className="job-status-cell">
                  <JobStatus status={job.status} />
                  {jobProgress && <small className="job-progress">{formatProgress(jobProgress)}</small>}
                </span>
                <span className="job-actions">
                  {job.input_method === "collector" && job.status === "created" && <button type="button" className="mini-upload-button" disabled={runningJobId === job.id} onClick={() => void executeJob(job)}>{runningJobId === job.id ? <RefreshCw size={14} className="spin" /> : <RefreshCw size={14} />}{runningJobId === job.id ? "采集中…" : "执行采集"}</button>}
                  {running && <button type="button" className="mini-upload-button danger-mini" disabled={job.status === "cancelling"} onClick={() => void cancelJob(job)}><Ban size={14} />{job.status === "cancelling" ? "取消中…" : "取消"}</button>}
                  {(job.status === "review_passed" || job.status === "review_failed" || job.status === "succeeded") && <button type="button" className="mini-upload-button" onClick={() => void showReview(job)}>查看审核</button>}
                  {!running && <button type="button" className="mini-upload-button quiet-mini" onClick={() => void deleteJob(job)}><Trash2 size={14} />删除</button>}
                </span>
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
  onCancel: () => void;
  onComplete: (message: string) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(props.datasets[0]?.id ?? "");
  const [operation, setOperation] = useState<CollectionOperation>("initial");
  const [inputMethod, setInputMethod] = useState<CollectionInputMethod>("file_import");
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
            <label className="input-field"><span>数据集<b>*</b></span><select value={datasetId} onChange={(event) => { const next = props.datasets.find((item) => item.id === event.target.value); setDatasetId(event.target.value); if (inputMethod === "collector" && next?.collection_bindings.length) setOperation(next.collection_bindings[0].purpose); }}>{props.datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.display_name} · {dataset.id}</option>)}</select></label>
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
            <button type="button" className={inputMethod === "collector" ? "method-card selected" : "method-card"} onClick={() => { setInputMethod("collector"); if (supportedPurposes.length) setOperation(supportedPurposes[0]); }}><RefreshCw size={22} /><strong>采集器</strong><span>由采集器获取供应商数据</span></button>
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

function operationDescription(operation: CollectionOperation) {
  const descriptions: Record<CollectionOperation, string> = {
    initial: "为尚未采集的数据集建立初始时间范围。",
    incremental: "未来由 Catalog 与交易日历计算新增数据和历史缺口。",
    repair: "针对明确的缺失或异常日期范围重新获取数据。",
    replace: "重新生成指定日期范围，并在发布阶段替换已有版本。",
  };
  return descriptions[operation];
}
