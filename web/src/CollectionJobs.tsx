import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock3,
  FileUp,
  Plus,
  RefreshCw,
  UploadCloud,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  type CollectionInputMethod,
  type CollectionJob,
  type CollectionJobCreatePayload,
  type CollectionOperation,
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
  awaiting_file: "等待文件",
  staged: "已进入临时区",
  review_passed: "审核通过",
  review_failed: "审核异常",
  succeeded: "已发布",
  failed: "执行失败",
};

export default function CollectionJobs({ datasets }: { datasets: DatasetSummary[] }) {
  const [jobs, setJobs] = useState<CollectionJob[]>([]);
  const [view, setView] = useState<"list" | "create">("list");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runningJobId, setRunningJobId] = useState<string | null>(null);
  const [review, setReview] = useState<{ jobId: string; data: CollectionReview } | null>(null);
  const activeDatasets = useMemo(
    () => datasets.filter((dataset) => dataset.status === "active"),
    [datasets],
  );

  const loadJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setJobs(await api.listCollectionJobs());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载采集任务");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

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
      setNotice(result.status === "review_passed" ? "采集完成，暂存数据审核通过。" : "采集完成，但审核发现异常。" );
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

  if (view === "create") {
    return (
      <CreateCollectionJob
        datasets={activeDatasets}
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
        <section className="review-summary">
          <div><strong>{review.data.passed ? "审核通过" : "审核异常"}</strong><span>任务 {review.jobId.slice(0, 8)}</span></div>
          <div><span>审核器</span><code>{review.data.reviewer}</code></div>
          <div><span>数据行数</span><strong>{review.data.row_count.toLocaleString()}</strong></div>
          <div><span>异常数量</span><strong>{review.data.error_count}</strong></div>
          <button type="button" className="toolbar-button" onClick={() => setReview(null)}>关闭</button>
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
            {jobs.map((job) => (
              <div className="job-row" key={job.id}>
                <span className="job-identity"><strong>{datasetName(datasets, job.dataset_id)}</strong><code>{job.dataset_id}</code><small>{job.id.slice(0, 8)}</small></span>
                <span>{operationLabels[job.operation]}</span>
                <span className="job-source"><strong>{inputLabels[job.input_method]}</strong>{job.collector_key && <code>{job.collector_key} · {job.collector_operation}</code>}</span>
                <span>{job.start_date ? <>{job.start_date}<br />至 {job.end_date}</> : "自动计算"}</span>
                <span className="file-cell">{job.source_file_name ? <><strong>{job.source_file_name}</strong><small>{formatBytes(job.source_size_bytes)}</small></> : job.status === "awaiting_file" ? <UploadFileButton onFile={(file) => void uploadExisting(job, file)} /> : "—"}</span>
                <span><JobStatus status={job.status} /></span>
                <span className="job-actions">
                  {job.input_method === "collector" && job.status === "created" && <button type="button" className="mini-upload-button" disabled={runningJobId === job.id} onClick={() => void executeJob(job)}><RefreshCw size={14} />{runningJobId === job.id ? "采集中…" : "执行采集"}</button>}
                  {(job.status === "review_passed" || job.status === "review_failed") && <button type="button" className="mini-upload-button" onClick={() => void showReview(job)}>查看审核</button>}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
      <p className="staging-note"><AlertCircle size={14} />“已进入临时区”只表示文件上传成功，尚未完成解析、校验和正式发布。</p>
    </div>
  );
}

function CreateCollectionJob(props: {
  datasets: DatasetSummary[];
  onCancel: () => void;
  onComplete: (message: string) => Promise<void>;
}) {
  const [datasetId, setDatasetId] = useState(props.datasets[0]?.id ?? "");
  const [operation, setOperation] = useState<CollectionOperation>("initial");
  const [inputMethod, setInputMethod] = useState<CollectionInputMethod>("file_import");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [useDateRange, setUseDateRange] = useState(false);
  const selectedDataset = props.datasets.find((dataset) => dataset.id === datasetId);
  const supportedPurposes = selectedDataset?.collection_bindings.map((item) => item.purpose) ?? [];
  const requiresDateRange =
    inputMethod === "collector" &&
    selectedDataset?.storage_policy?.logical_partition_field === "trade_date" &&
    operation !== "incremental";
  const usesAutomaticIncrementalRange =
    inputMethod === "collector" &&
    selectedDataset?.storage_policy?.logical_partition_field === "trade_date" &&
    operation === "incremental";
  const includesDateRange = requiresDateRange || (useDateRange && !usesAutomaticIncrementalRange);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!datasetId) return setError("没有可用的已启用数据集。");
    if (includesDateRange && (!startDate || !endDate)) return setError("请同时填写开始和结束日期。");
    if (startDate && endDate && startDate > endDate) return setError("开始日期不能晚于结束日期。");
    if (inputMethod === "file_import" && !file) return setError("请选择需要导入的文件。");

    const payload: CollectionJobCreatePayload = {
      dataset_id: datasetId,
      operation,
      input_method: inputMethod,
      start_date: includesDateRange ? startDate : null,
      end_date: includesDateRange ? endDate : null,
      collector_key: null,
      parameters: usesAutomaticIncrementalRange && endDate ? { end_date: endDate } : {},
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
          {!requiresDateRange && !usesAutomaticIncrementalRange && <label className="range-toggle"><input type="checkbox" checked={useDateRange} onChange={(event) => setUseDateRange(event.target.checked)} />本次任务需要指定日期范围</label>}
          {includesDateRange && <div className="form-grid two-columns date-grid"><label className="input-field"><span>开始日期<b>*</b></span><input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label><label className="input-field"><span>结束日期<b>*</b></span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label></div>}
          {usesAutomaticIncrementalRange && <div className="form-grid two-columns date-grid"><label className="input-field"><span>更新截止日期（可选）</span><input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} /></label><div className="operation-help">开始日期由数据集当前水位自动计算；不填截止日期时默认更新到当天。</div></div>}
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
