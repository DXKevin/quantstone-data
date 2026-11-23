import { AlertCircle, CheckCircle2, ChevronDown, ChevronRight, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, type CollectionJobCreatePayload, type CollectionOverview, type CollectionPurpose, type CollectorDefinition, type CollectorOperation, type CollectorParameter, type DailyCompletion, type DatasetOverview, type DatasetStatus, type DatasetSummary } from "./api";
import CoverageHeatmap from "./CoverageHeatmap";

const statusLabels: Record<DatasetStatus, string> = {
  draft: "草稿",
  active: "已启用",
  paused: "已暂停",
  deprecated: "已停用",
};

const jobStatusLabels: Record<string, string> = {
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

const operationLabels: Record<string, string> = {
  initial: "首次采集",
  incremental: "增量更新",
  repair: "缺口修复",
  replace: "范围重建",
};

const dailyStatusLabels: Record<string, string> = {
  complete: "已更新",
  missing: "缺失",
  failed: "采集失败",
  abnormal: "文件异常",
  pending: "待采集",
  stale: "需更新",
  none: "—",
};

const layoutLabels: Record<string, string> = {
  daily: "单日文件",
  yearly_with_delta: "年度主文件 + 日增量",
  snapshot: "完整快照",
};

type PendingStart = {
  datasetId: string;
  displayName: string;
  purpose: CollectionPurpose;
  operation: CollectorOperation;
  values: Record<string, string>;
};

export default function OverviewPage({ datasets, collectors, onOpen, onOpenCollectionJob }: { datasets: DatasetSummary[]; collectors: CollectorDefinition[]; onOpen: (id: string) => void; onOpenCollectionJob: (jobId: string) => void }) {
  const [items, setItems] = useState<DatasetOverview[]>([]);
  const [collection, setCollection] = useState<CollectionOverview | null>(null);
  const [dailyCompletion, setDailyCompletion] = useState<DailyCompletion | null>(null);
  const [dailyExpanded, setDailyExpanded] = useState(false);
  const [tasksExpanded, setTasksExpanded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingKey, setStartingKey] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingStart, setPendingStart] = useState<PendingStart | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [datasets, collectionData, dailyData] = await Promise.all([
        api.getDatasetOverview(),
        api.getCollectionOverview(),
        api.getDailyCompletion(30),
      ]);
      setItems(datasets);
      setCollection(collectionData);
      setDailyCompletion(dailyData);
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

  const datasetById = useMemo(
    () => new Map(datasets.map((dataset) => [dataset.id, dataset])),
    [datasets],
  );

  function resolveBinding(datasetId: string, purpose: CollectionPurpose) {
    const summary = datasetById.get(datasetId);
    const binding = summary?.collection_bindings.find((entry) => entry.purpose === purpose);
    if (!binding) return null;
    const collector = collectors.find((entry) => entry.key === binding.collector_key);
    const operation = collector?.operations.find((entry) => entry.key === binding.operation);
    return operation ? { binding, operation } : null;
  }

  async function refreshCollection() {
    try {
      setCollection(await api.getCollectionOverview());
    } catch {
      // 概览刷新失败不影响任务已提交的结果。
    }
  }

  async function startCollection(item: DatasetOverview, purpose: CollectionPurpose) {
    setActionNotice(null);
    setActionError(null);
    const resolved = resolveBinding(item.dataset_id, purpose);
    if (!resolved) {
      setActionError("该数据集没有绑定对应的采集器操作。");
      return;
    }
    if (resolved.operation.parameters.some((parameter) => parameter.required)) {
      const values = Object.fromEntries(
        resolved.operation.parameters.map((parameter) => [
          parameter.name,
          parameter.data_type === "date" && parameter.name === "end_date" ? localToday() : "",
        ]),
      );
      setPendingStart({
        datasetId: item.dataset_id,
        displayName: item.display_name,
        purpose,
        operation: resolved.operation,
        values,
      });
      return;
    }
    await submitStart(item.dataset_id, item.display_name, purpose, resolved.operation, {});
  }

  async function submitStart(
    datasetId: string,
    displayName: string,
    purpose: CollectionPurpose,
    operation: CollectorOperation,
    values: Record<string, string>,
  ) {
    const key = `${datasetId}:${purpose}`;
    setStartingKey(key);
    setActionNotice(null);
    setActionError(null);
    try {
      const parameters = Object.fromEntries(
        operation.parameters
          .filter((parameter) => values[parameter.name]?.trim())
          .map((parameter) => [parameter.name, convertParameterValue(parameter, values[parameter.name])]),
      );
      const payload: CollectionJobCreatePayload = {
        dataset_id: datasetId,
        operation: purpose,
        input_method: "collector",
        start_date: null,
        end_date: null,
        collector_key: null,
        parameters,
      };
      const job = await api.createCollectionJob(payload);
      await api.executeCollectionJob(job.id);
      setPendingStart(null);
      setActionNotice(`${displayName} 的${operationLabels[purpose]}已提交执行，可在采集页查看进度。`);
      await refreshCollection();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "无法启动采集任务");
    } finally {
      setStartingKey(null);
    }
  }

  function submitPending(event: FormEvent) {
    event.preventDefault();
    if (!pendingStart) return;
    const missing = pendingStart.operation.parameters.find(
      (parameter) => parameter.required && !pendingStart.values[parameter.name]?.trim(),
    );
    if (missing) {
      setActionError(`请填写${missing.description || missing.name}`);
      return;
    }
    void submitStart(
      pendingStart.datasetId,
      pendingStart.displayName,
      pendingStart.purpose,
      pendingStart.operation,
      pendingStart.values,
    );
  }

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <p className="eyebrow">OVERVIEW</p>
          <h1>数据概览</h1>
          <p className="subtitle">按数据集聚合已发布的分区、行数、体积和覆盖情况，并汇总最近采集运行。</p>
        </div>
        <button className="toolbar-button" onClick={() => void load()}><RefreshCw size={15} />刷新</button>
      </header>

      {actionNotice && <div className="notice-banner"><CheckCircle2 size={17} />{actionNotice}</div>}
      {actionError && !pendingStart && <div className="form-error"><AlertCircle size={17} />{actionError}</div>}

      <CoverageHeatmap onOpen={onOpen} />

      <section className="summary-strip">
        <div><span>数据集</span><strong>{totals.datasets}</strong></div>
        <div><span>已发布分区</span><strong>{totals.partitions.toLocaleString()}</strong></div>
        <div><span>总行数</span><strong>{totals.rows.toLocaleString()}</strong></div>
        <div><span>总体积</span><strong>{formatBytes(totals.bytes)}</strong></div>
      </section>

      {dailyCompletion && dailyCompletion.datasets.length > 0 && (
        <section className="panel daily-completion-panel">
          <div className="panel-toolbar">
            <div>
              <h2>日更数据完成率</h2>
              <span>最近 {dailyCompletion.days} 个交易日 · {dailyCompletion.today}</span>
            </div>
            <strong className="daily-completion-total-percent">
              {dailyCompletion.total.completion_percent === null
                ? "—"
                : `${dailyCompletion.total.completion_percent}%`}
            </strong>
          </div>
          <div className="daily-completion-total">
            <div className="coverage-bar">
              <i style={{ width: `${Math.min(dailyCompletion.total.completion_percent ?? 0, 100)}%` }} />
            </div>
            <span>
              总计 {dailyCompletion.total.complete.toLocaleString()} / {dailyCompletion.total.expected.toLocaleString()} 个应完成项
            </span>
            <small>
              缺失 {dailyCompletion.total.missing} · 失败 {dailyCompletion.total.failed + dailyCompletion.total.abnormal}
              {dailyCompletion.total.pending ? ` · 待采集 ${dailyCompletion.total.pending}` : ""}
            </small>
          </div>
          <button
            type="button"
            className="daily-completion-toggle"
            aria-expanded={dailyExpanded}
            onClick={() => setDailyExpanded((expanded) => !expanded)}
          >
            {dailyExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span>完成率明细</span>
            <small>{dailyCompletion.datasets.length} 个数据集</small>
          </button>
          {dailyExpanded && (
            <div className="daily-completion-list">
              {dailyCompletion.datasets.map((row) => (
                <div className="daily-completion-row" key={row.dataset_id}>
                  <div className="daily-completion-name">
                    <strong>{row.display_name}</strong>
                    <code>{row.dataset_id}</code>
                  </div>
                  <span className={`daily-status daily-status-${row.latest_status ?? "none"}`}>
                    {row.latest_trade_date ? `${row.latest_trade_date} · ${dailyStatusLabels[row.latest_status ?? "none"]}` : "无交易日"}
                  </span>
                  {row.layout === "snapshot" ? (
                    <>
                      <div className="daily-completion-progress">
                        <div className="coverage-bar">
                          <i style={{ width: `${row.completion_percent ?? 0}%` }} />
                        </div>
                        <small>{row.last_updated_at ? `最近更新 ${formatDate(row.last_updated_at)}` : "尚未更新"}</small>
                      </div>
                      <span />
                    </>
                  ) : (
                    <>
                      <div className="daily-completion-progress">
                        <div className="coverage-bar">
                          <i style={{ width: `${Math.min(row.completion_percent ?? 0, 100)}%` }} />
                        </div>
                        <small>{row.complete} / {row.expected} · {row.completion_percent ?? "—"}%</small>
                      </div>
                      <span className="daily-completion-gaps">
                        {row.missing || row.failed || row.abnormal || row.pending
                          ? `缺失 ${row.missing} · 失败 ${row.failed + row.abnormal}${row.pending ? ` · 待采集 ${row.pending}` : ""}`
                          : ""}
                      </span>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {collection && (
        <section className="panel collection-overview-panel">
          <div className="panel-toolbar">
            <div>
              <h2>采集概览</h2>
              <span>{collection.total_jobs} 个任务 · 最近 24 小时</span>
            </div>
            <span className="collection-last">
              最近完成 {collection.last_completed_at ? formatDate(collection.last_completed_at) : "—"}
            </span>
          </div>
          <div className="collection-metrics">
            <div><span>执行中</span><strong>{collection.running}</strong></div>
            <div><span>排队中</span><strong>{collection.queued}</strong></div>
            <div><span>等待文件</span><strong>{collection.awaiting_file}</strong></div>
            <div><span>24h 成功</span><strong>{collection.succeeded_24h}</strong></div>
            <div><span>24h 失败</span><strong>{collection.failed_24h}</strong></div>
          </div>
          <button
            type="button"
            className="collection-tasks-toggle"
            aria-expanded={tasksExpanded}
            onClick={() => setTasksExpanded((expanded) => !expanded)}
          >
            {tasksExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <span>最近采集任务</span>
            <small>{collection.recent_jobs.length} 个</small>
          </button>
          {tasksExpanded && (
            <div className="recent-collection-list">
              {collection.recent_jobs.length ? collection.recent_jobs.map((job) => (
                <button
                  type="button"
                  className="recent-collection-row"
                  key={job.id}
                  onClick={() => onOpenCollectionJob(job.id)}
                >
                  <span className={`job-status job-status-${job.status}`}><i />{jobStatusLabels[job.status] ?? job.status}</span>
                  <span className="recent-collection-name">
                    <strong>{job.display_name}</strong>
                    <code>{operationLabels[job.operation] ?? job.operation} · {job.dataset_id}</code>
                  </span>
                  <time>{formatDate(job.updated_at)}</time>
                </button>
              )) : <p className="recent-collection-empty">还没有采集任务。</p>}
            </div>
          )}
        </section>
      )}

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
          {items.map((item) => {
            const summary = datasetById.get(item.dataset_id);
            const purposes = new Set(summary?.collection_bindings.map((binding) => binding.purpose) ?? []);
            const initialCompleted = item.partitions > 0;
            const hasDateCoverage = item.calendar_dataset_id !== null;
            const initialKey = `${item.dataset_id}:initial`;
            const incrementalKey = `${item.dataset_id}:incremental`;
            return (
              <div
                className="overview-card"
                key={item.dataset_id}
                role="button"
                tabIndex={0}
                onClick={() => onOpen(item.dataset_id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onOpen(item.dataset_id);
                  }
                }}
              >
                <div className="overview-card-head">
                  <strong>{item.display_name}</strong>
                  <div className="overview-head-actions">
                    {item.status === "active" && !initialCompleted && purposes.has("initial") && (
                      <button
                        type="button"
                        className="overview-action"
                        disabled={startingKey === initialKey}
                        onClick={(event) => {
                          event.stopPropagation();
                          void startCollection(item, "initial");
                        }}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        {startingKey === initialKey ? "提交中…" : "首次采集"}
                      </button>
                    )}
                    {item.status === "active" && initialCompleted && purposes.has("incremental") && (
                      <button
                        type="button"
                        className="overview-action"
                        disabled={startingKey === incrementalKey}
                        onClick={(event) => {
                          event.stopPropagation();
                          void startCollection(item, "incremental");
                        }}
                        onKeyDown={(event) => event.stopPropagation()}
                      >
                        {startingKey === incrementalKey ? "提交中…" : "增量更新"}
                      </button>
                    )}
                    <span className={`status status-${item.status}`}><i />{statusLabels[item.status]}</span>
                  </div>
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
                      {hasDateCoverage
                        ? item.coverage_percent === null
                          ? "尚无已发布分区"
                          : `${item.coverage_percent}% · ${item.partitions}/${item.expected_partitions ?? 0} 个交易日`
                        : item.partitions > 0
                          ? "100% · 快照已发布"
                          : "0% · 尚未初始化"}
                    </span>
                  </div>
                  <div className="coverage-bar">
                    <i style={{ width: `${hasDateCoverage ? Math.min(item.coverage_percent ?? 0, 100) : item.partitions > 0 ? 100 : 0}%` }} />
                  </div>
                </div>

                <div className="overview-foot">
                  <span>{layoutLabels[item.layout ?? ""] ?? "未配置布局"}</span>
                  <span>最新 {item.latest_partition ?? "—"}</span>
                  <span>{item.published_at ? `发布 ${formatDate(item.published_at)}` : "尚未发布"}</span>
                </div>
              </div>
            );
          })}
        </section>
      )}

      {pendingStart && (
        <div className="modal-backdrop" onClick={() => setPendingStart(null)}>
          <form className="start-dialog" onClick={(event) => event.stopPropagation()} onSubmit={submitPending}>
            <h2>{operationLabels[pendingStart.purpose]} · {pendingStart.displayName}</h2>
            <p>{pendingStart.operation.name}。请填写本次运行参数。</p>
            {pendingStart.operation.parameters.map((parameter) => (
              <label className="input-field" key={parameter.name}>
                <span>{parameter.description || parameter.name}{parameter.required && <b>*</b>}</span>
                <input
                  type={parameter.data_type === "date" ? "date" : ["int", "int32", "int64", "float", "float32", "float64", "number"].includes(parameter.data_type) ? "number" : "text"}
                  value={pendingStart.values[parameter.name] ?? ""}
                  onChange={(event) => setPendingStart((current) => current ? {
                    ...current,
                    values: { ...current.values, [parameter.name]: event.target.value },
                  } : current)}
                />
                <small>{parameter.name}</small>
              </label>
            ))}
            {actionError && <div className="form-error"><AlertCircle size={16} />{actionError}</div>}
            <div className="dialog-actions">
              <button type="button" className="ghost-button" onClick={() => setPendingStart(null)}>取消</button>
              <button type="submit" className="primary-button" disabled={startingKey === `${pendingStart.datasetId}:${pendingStart.purpose}`}>
                {startingKey === `${pendingStart.datasetId}:${pendingStart.purpose}` ? "提交中…" : "开始采集"}
              </button>
            </div>
          </form>
        </div>
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

function convertParameterValue(parameter: CollectorParameter, value: string) {
  if (parameter.data_type === "boolean") return value === "true";
  if (["int", "integer", "int32", "int64"].includes(parameter.data_type)) {
    return Number.parseInt(value, 10);
  }
  if (["float", "float32", "float64", "number"].includes(parameter.data_type)) {
    return Number.parseFloat(value);
  }
  return value;
}

function localToday() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}
