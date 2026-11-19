import {
  Activity,
  ArrowLeft,
  Ban,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  Cable,
  Database,
  LayoutGrid,
  Layers3,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  CollectorDefinition,
  CollectionReadiness,
  CollectionPurpose,
  DatasetCategory,
  DatasetCreatePayload,
  DatasetDeletionReview,
  DatasetDetail,
  DatasetPreset,
  DatasetSummary,
  MaintenanceJob,
} from "./api";
import CollectionJobs from "./CollectionJobs";
import DatasetPreview from "./DatasetPreview";
import OverviewPage from "./OverviewPage";

type View = "list" | "create" | "edit" | "metadata" | "detail";
type Area = "overview" | "datasets" | "collection";
type DatasetSection = "registry" | "presets";
type CollectionSection = "jobs" | "capabilities";
type CollectionRequest = { datasetId: string; operation: CollectionPurpose };

interface FieldDraft {
  key: number;
  name: string;
  data_type: string;
  nullable: boolean;
  description: string;
  unit: string;
  source_name: string;
  primary: boolean;
}

const fieldTypes = ["string", "int32", "int64", "float32", "float64", "boolean", "date", "timestamp"];

const newField = (key: number): FieldDraft => ({
  key,
  name: "",
  data_type: "string",
  nullable: true,
  description: "",
  unit: "",
  source_name: "",
  primary: false,
});

const statusLabels = {
  draft: "草稿",
  active: "已启用",
  paused: "已暂停",
  deprecated: "已停用",
};

const purposeLabels: Record<CollectionPurpose, string> = {
  initial: "首次采集",
  incremental: "增量更新",
  repair: "缺口修复",
  replace: "范围重建",
};

function App() {
  const [area, setArea] = useState<Area>("overview");
  const [datasetSection, setDatasetSection] = useState<DatasetSection>("registry");
  const [collectionSection, setCollectionSection] = useState<CollectionSection>("jobs");
  const [collectionRequest, setCollectionRequest] = useState<CollectionRequest | null>(null);
  const [collectionJobRequest, setCollectionJobRequest] = useState<string | null>(null);
  const [view, setView] = useState<View>("list");
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [categories, setCategories] = useState<DatasetCategory[]>([]);
  const [presets, setPresets] = useState<DatasetPreset[]>([]);
  const [collectors, setCollectors] = useState<CollectorDefinition[]>([]);
  const [selected, setSelected] = useState<DatasetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const loadDatasets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [datasetItems, collectorItems, presetItems, categoryItems] = await Promise.all([
        api.listDatasets(),
        api.listCollectors(),
        api.listDatasetPresets(),
        api.listDatasetCategories(),
      ]);
      setDatasets(datasetItems);
      setCollectors(collectorItems);
      setPresets(presetItems);
      setCategories(categoryItems);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载数据集");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasets();
  }, [loadDatasets]);

  const filtered = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return datasets;
    return datasets.filter(
      (item) => item.id.toLowerCase().includes(keyword) || item.display_name.toLowerCase().includes(keyword),
    );
  }, [datasets, query]);

  async function openDataset(id: string) {
    setError(null);
    try {
      setSelected(await api.getDataset(id));
      setView("detail");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取数据集");
    }
  }

  async function handleSaved(dataset: DatasetDetail) {
    await loadDatasets();
    setSelected(dataset);
    setView("detail");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Layers3 size={20} strokeWidth={2.2} /></div>
          <div><strong>QuantStone</strong><span>DATA</span></div>
        </div>
        <nav>
          <button className={area === "overview" ? "nav-item active" : "nav-item"} onClick={() => setArea("overview")}><LayoutGrid size={17} />概览</button>
          <button className={area === "datasets" ? "nav-item active" : "nav-item"} onClick={() => { setArea("datasets"); setDatasetSection("registry"); setView("list"); }}><Database size={17} />数据集</button>
          <button className={area === "collection" ? "nav-item active" : "nav-item"} onClick={() => setArea("collection")}><Activity size={17} />采集</button>
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" disabled><CircleHelp size={17} />帮助</button>
          <button className="nav-item" disabled><Settings size={17} />设置</button>
          <div className="version">QuantStone Data · v0.1.0</div>
        </div>
      </aside>

      <main className="main-area">
        {area === "overview" && <OverviewPage datasets={datasets} collectors={collectors} onOpen={(id) => { setArea("datasets"); setDatasetSection("registry"); void openDataset(id); }} onOpenCollectionJob={(jobId) => { setCollectionJobRequest(jobId); setCollectionSection("jobs"); setArea("collection"); }} />}
        {area === "collection" && collectionSection === "jobs" && (
          <CollectionJobs
            datasets={datasets}
            collectors={collectors}
            navigation={<CollectionTabs selected="jobs" onSelect={setCollectionSection} />}
            requestedCollection={collectionRequest}
            onRequestHandled={() => setCollectionRequest(null)}
            requestedJobId={collectionJobRequest}
            onJobRequestHandled={() => setCollectionJobRequest(null)}
          />
        )}
        {area === "collection" && collectionSection === "capabilities" && (
          <CollectorCatalog collectors={collectors} navigation={<CollectionTabs selected="capabilities" onSelect={setCollectionSection} />} />
        )}
        {area === "datasets" && datasetSection === "presets" && (
          <DatasetPresetCatalog
            presets={presets}
            datasets={datasets}
            loading={loading}
            error={error}
            navigation={<DatasetTabs selected="presets" onSelect={setDatasetSection} />}
            onCreated={(dataset) => {
              void handleSaved(dataset);
              setArea("datasets");
              setDatasetSection("registry");
            }}
            onRetry={() => void loadDatasets()}
          />
        )}
        {area === "datasets" && datasetSection === "registry" && view === "list" && (
          <DatasetList
            datasets={filtered}
            allDatasets={datasets}
            total={datasets.length}
            loading={loading}
            error={error}
            query={query}
            onQuery={setQuery}
            onCreate={() => setView("create")}
            onOpen={(id) => void openDataset(id)}
            onRetry={() => void loadDatasets()}
            navigation={<DatasetTabs selected="registry" onSelect={setDatasetSection} />}
            categories={categories}
            onCategoriesChanged={() => void loadDatasets()}
          />
        )}
        {area === "datasets" && datasetSection === "registry" && view === "create" && (
          <DatasetForm collectors={collectors} datasets={datasets} onCancel={() => setView("list")} onSaved={(data) => void handleSaved(data)} />
        )}
        {area === "datasets" && datasetSection === "registry" && view === "edit" && selected && (
          <DatasetForm collectors={collectors} datasets={datasets} dataset={selected} onCancel={() => setView("detail")} onSaved={(data) => void handleSaved(data)} />
        )}
        {area === "datasets" && datasetSection === "registry" && view === "metadata" && selected && (
          <DatasetMetadataForm dataset={selected} onCancel={() => setView("detail")} onSaved={(data) => void handleSaved(data)} />
        )}
        {area === "datasets" && datasetSection === "registry" && view === "detail" && selected && (
          <DatasetDetailView
            dataset={selected}
            onBack={() => setView("list")}
            onEdit={() => setView("edit")}
            onEditMetadata={() => setView("metadata")}
            categories={categories}
            onCollect={(operation) => {
              setCollectionRequest({ datasetId: selected.id, operation });
              setCollectionSection("jobs");
              setArea("collection");
            }}
            onChanged={(data) => {
              setSelected(data);
              void loadDatasets();
            }}
          />
        )}
      </main>
    </div>
  );
}

function DatasetTabs(props: { selected: DatasetSection; onSelect: (section: DatasetSection) => void }) {
  return (
    <div className="section-tabs" aria-label="数据集页面">
      <button className={props.selected === "registry" ? "active" : ""} onClick={() => props.onSelect("registry")}><Database size={16} />数据集</button>
      <button className={props.selected === "presets" ? "active" : ""} onClick={() => props.onSelect("presets")}><BookOpen size={16} />预置契约</button>
    </div>
  );
}

function CollectionTabs(props: { selected: CollectionSection; onSelect: (section: CollectionSection) => void }) {
  return (
    <div className="section-tabs" aria-label="采集页面">
      <button className={props.selected === "jobs" ? "active" : ""} onClick={() => props.onSelect("jobs")}><Activity size={16} />任务</button>
      <button className={props.selected === "capabilities" ? "active" : ""} onClick={() => props.onSelect("capabilities")}><Cable size={16} />采集能力</button>
    </div>
  );
}

function DatasetPresetCatalog(props: {
  presets: DatasetPreset[];
  datasets: DatasetSummary[];
  loading: boolean;
  error: string | null;
  navigation: ReactNode;
  onCreated: (dataset: DatasetDetail) => void;
  onRetry: () => void;
}) {
  const [creating, setCreating] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const existing = new Map(props.datasets.map((item) => [item.id, item]));

  async function createFromPreset(preset: DatasetPreset) {
    setCreating(preset.key);
    setCreateError(null);
    try {
      props.onCreated(await api.createDataset(preset.contract));
    } catch (reason) {
      setCreateError(reason instanceof Error ? reason.message : "无法从预置契约创建数据集");
    } finally {
      setCreating(null);
    }
  }

  return (
    <div className="page">
      {props.navigation}
      <header className="page-header">
        <div><p className="eyebrow">VERSIONED CONTRACT PRESETS</p><h1>预置契约</h1><p className="subtitle">项目随代码维护的常用数据集契约。选择契约可快速创建 Registry 草稿。</p></div>
      </header>
      <section className="summary-strip">
        <div><span>预置契约</span><strong>{props.presets.length}</strong></div>
        <div><span>已创建</span><strong>{props.presets.filter((item) => existing.has(item.contract.id)).length}</strong></div>
        <div><span>维护方式</span><strong className="summary-text">代码版本管理</strong></div>
        <div><span>创建结果</span><strong className="summary-text">Registry 草稿</strong></div>
      </section>
      {props.error && <div className="error-banner"><span>{props.error}</span><button onClick={props.onRetry}>重试</button></div>}
      {createError && <div className="error-banner"><span>{createError}</span></div>}
      {props.loading && <div className="empty-state">正在加载预置契约…</div>}
      {!props.loading && props.presets.map((preset) => {
        const contract = preset.contract;
        const current = existing.get(contract.id);
        return (
          <section className="panel preset-card" key={preset.key}>
            <div className="preset-header">
              <div><span className="preset-category">{preset.category}</span><h2>{contract.display_name}</h2><code>{contract.id}</code></div>
              {current ? (
                <span className={`status status-${current.status}`}>已创建 · {statusLabels[current.status]}</span>
              ) : (
                <button className="primary-button" disabled={creating === preset.key} onClick={() => void createFromPreset(preset)}>
                  <Plus size={16} />{creating === preset.key ? "正在创建…" : "创建草稿"}
                </button>
              )}
            </div>
            <p className="preset-description">{contract.description}</p>
            <div className="preset-facts">
              <div><span>字段</span><strong>{contract.fields.length}</strong></div>
              <div><span>主键</span><code>{contract.primary_key.join(" + ")}</code></div>
              <div><span>时间字段</span><code>{contract.time_field ?? "—"}</code></div>
              <div><span>存储布局</span><code>{contract.storage_policy?.layout ?? "—"}</code></div>
            </div>
            <div className="preset-contract-grid">
              <div><strong>字段契约</strong><p>{contract.fields.map((item) => `${item.name}: ${item.data_type}${item.nullable ? "?" : ""}`).join(" · ")}</p></div>
              <div><strong>采集绑定</strong><p>{contract.collection_bindings.map((item) => `${purposeLabels[item.purpose]}: ${item.operation}`).join(" · ") || "未绑定"}</p></div>
            </div>
          </section>
        );
      })}
    </div>
  );
}

function CollectorCatalog({ collectors, navigation }: { collectors: CollectorDefinition[]; navigation: ReactNode }) {
  return (
    <div className="page">
      {navigation}
      <header className="page-header">
        <div><p className="eyebrow">COLLECTOR REGISTRY</p><h1>采集能力</h1><p className="subtitle">查看采集器、公开操作、运行参数和输出数据集。</p></div>
      </header>
      <section className="summary-strip">
        <div><span>采集器</span><strong>{collectors.length}</strong></div>
        <div><span>操作</span><strong>{collectors.reduce((total, item) => total + item.operations.length, 0)}</strong></div>
        <div><span>联合操作</span><strong>{collectors.flatMap((item) => item.operations).filter((item) => item.joint).length}</strong></div>
        <div><span>注册方式</span><strong className="summary-text">显式注册</strong></div>
      </section>
      {collectors.map((collector) => (
        <section className="panel collector-card" key={collector.key}>
          <div className="card-title"><div><h2 className="collector-title"><span>{collector.name}</span><code>&lt;{collector.key}&gt;</code></h2></div><span>{collector.operations.length} 个操作</span></div>
          <p>{collector.description}</p>
          <div className="collector-compact-table">
            <div className="collector-compact-row collector-compact-head"><span>输出数据集</span><span>更新方式</span><span>操作及各自参数</span></div>
            {groupCollectorOperations(collector).map((group) => (
              <div className="collector-compact-row" key={group.key}>
                <div className="compact-datasets">{group.datasets.map((id) => <code key={id}>{id}</code>)}</div>
                <span>{group.datasets.length > 1 ? "联合更新" : "独立更新"}</span>
                <div className="compact-operation-list">{group.operations.map((operation) => <div className="compact-operation-line" title={operation.description} key={operation.key}><span className={`operation-chip purpose-${operation.purpose}`}><b>{purposeLabels[operation.purpose]}</b><code>{operation.key}</code></span><span className="compact-parameters">{operation.parameters.length ? operation.parameters.map((item) => `${item.name}${item.required ? "*" : ""}`).join("、") : "无参数"}</span></div>)}</div>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function groupCollectorOperations(collector: CollectorDefinition) {
  const groups = new Map<string, { key: string; datasets: string[]; operations: CollectorDefinition["operations"] }>();
  for (const operation of collector.operations) {
    const key = [...operation.datasets].sort().join("|");
    const current = groups.get(key) ?? { key, datasets: operation.datasets, operations: [] };
    current.operations.push(operation);
    groups.set(key, current);
  }
  return [...groups.values()];
}

function DatasetList(props: {
  datasets: DatasetSummary[];
  allDatasets: DatasetSummary[];
  total: number;
  loading: boolean;
  error: string | null;
  query: string;
  onQuery: (value: string) => void;
  onCreate: () => void;
  onOpen: (id: string) => void;
  onRetry: () => void;
  navigation: ReactNode;
  categories: DatasetCategory[];
  onCategoriesChanged: () => void;
}) {
  const [managingCategories, setManagingCategories] = useState(false);
  const [selecting, setSelecting] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [deletionReview, setDeletionReview] = useState<DatasetDeletionReview | null>(null);
  const [reviewing, setReviewing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const groups = [
    ...props.categories.map((category) => ({
      id: category.id,
      name: category.name,
      description: category.description,
      datasets: props.datasets.filter((dataset) => dataset.category_id === category.id),
    })),
    {
      id: null,
      name: "未分类",
      description: "尚未归入任何数据集大类",
      datasets: props.datasets.filter((dataset) => dataset.category_id === null),
    },
  ].filter((group) => group.datasets.length > 0 || !props.query.trim());

  function toggleDataset(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function reviewDeletion() {
    setReviewing(true);
    setDeletionError(null);
    try {
      setDeletionReview(await api.reviewDatasetDeletion([...selectedIds]));
      setConfirmation("");
    } catch (reason) {
      setDeletionError(reason instanceof Error ? reason.message : "删除审查失败");
    } finally {
      setReviewing(false);
    }
  }

  async function commitDeletion() {
    if (!deletionReview) return;
    setDeleting(true);
    setDeletionError(null);
    try {
      await api.deleteDatasets(deletionReview.dataset_ids, deletionReview.review_token, confirmation);
      setDeletionReview(null);
      setSelectedIds(new Set());
      setSelecting(false);
      props.onCategoriesChanged();
    } catch (reason) {
      setDeletionError(reason instanceof Error ? reason.message : "删除失败，请重新审查");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="page">
      {props.navigation}
      <header className="page-header">
        <div><p className="eyebrow">DATASET REGISTRY</p><h1>数据集</h1><p className="subtitle">按大类组织并管理供应商数据集的字段契约与版本。</p></div>
        <div className="header-actions"><button className={selecting ? "danger-button" : "ghost-button"} onClick={() => { setSelecting((value) => !value); setSelectedIds(new Set()); setDeletionError(null); }}><Trash2 size={16} />{selecting ? "退出批量删除" : "批量删除"}</button><button className="ghost-button" onClick={() => setManagingCategories((value) => !value)}><Layers3 size={16} />管理大类</button><button className="primary-button" onClick={props.onCreate}><Plus size={17} />创建数据集</button></div>
      </header>

      <section className="summary-strip">
        <div><span>数据集总数</span><strong>{props.total}</strong></div>
        <div><span>数据集大类</span><strong>{props.categories.length}</strong></div>
        <div><span>已启用</span><strong>{props.datasets.filter((item) => item.status === "active").length}</strong></div>
        <div><span>未分类</span><strong>{props.datasets.filter((item) => item.category_id === null).length}</strong></div>
      </section>

      {managingCategories && <DatasetCategoryManager categories={props.categories} datasets={props.allDatasets} onChanged={props.onCategoriesChanged} />}

      {selecting && <section className="panel deletion-selection-bar"><div><strong>严格删除审查</strong><span>已选择 {selectedIds.size} 个数据集。删除将清除 Registry、任务、Catalog、日志、暂存和正式物理文件。</span></div><button className="danger-button" disabled={!selectedIds.size || reviewing} onClick={() => void reviewDeletion()}>{reviewing ? "正在审查…" : "审查删除影响"}</button></section>}
      {deletionError && !deletionReview && <div className="form-error"><X size={17} />{deletionError}</div>}

      <section className="panel dataset-list-toolbar">
        <div className="panel-toolbar">
          <div><h2>数据集目录</h2><span>{props.total} 个数据集</span></div>
          <label className="search-box"><Search size={16} /><input value={props.query} onChange={(event) => props.onQuery(event.target.value)} placeholder="搜索 ID 或名称" /></label>
        </div>
      </section>

      {props.error ? (
        <div className="panel state-box error-state"><strong>无法连接 Registry API</strong><p>{props.error}</p><button onClick={props.onRetry}>重新加载</button></div>
      ) : props.loading ? (
        <div className="panel state-box"><div className="loader" /><p>正在加载数据集…</p></div>
      ) : props.datasets.length === 0 && props.total === 0 ? (
        <div className="panel state-box empty-state"><Database size={28} /><strong>还没有数据集</strong><p>创建第一个数据集，开始定义字段契约。</p><button className="secondary-button" onClick={props.onCreate}><Plus size={16} />创建数据集</button></div>
      ) : groups.length === 0 ? (
        <div className="panel state-box empty-state"><Search size={28} /><strong>没有匹配的数据集</strong><p>请调整搜索关键词。</p></div>
      ) : groups.map((group) => (
        <section className="panel dataset-group" key={group.id ?? "uncategorized"}>
          <div className="dataset-group-header"><div><h2>{group.name}</h2><p>{group.description}</p></div><div className="dataset-group-actions"><span>{group.datasets.length} 个数据集</span>{group.id && <CategoryQuickAdd categoryId={group.id} datasets={props.allDatasets} onChanged={props.onCategoriesChanged} />}</div></div>
          {group.datasets.length === 0 ? <div className="dataset-group-empty">该大类下还没有数据集。</div> : <div className="dataset-table">
            <div className="table-row table-head"><span>数据集</span><span>供应商</span><span>区域 / 品种</span><span>状态</span><span /></div>
            {group.datasets.map((dataset) => (
              <div className={`table-row data-row${selectedIds.has(dataset.id) ? " selected" : ""}`} key={dataset.id} role="button" tabIndex={0} onClick={() => selecting ? toggleDataset(dataset.id) : props.onOpen(dataset.id)} onKeyDown={(event) => { if (event.key === "Enter") selecting ? toggleDataset(dataset.id) : props.onOpen(dataset.id); }}>
                <span className="dataset-cell">{selecting && <input type="checkbox" checked={selectedIds.has(dataset.id)} onChange={() => toggleDataset(dataset.id)} onClick={(event) => event.stopPropagation()} aria-label={`选择 ${dataset.display_name}`} />}<span><strong>{dataset.display_name}</strong><code>{dataset.id}</code></span></span>
                <span>{dataset.provider}</span>
                <span>{dataset.region.toUpperCase()} / {dataset.instrument}{dataset.market ? ` / ${dataset.market.toUpperCase()}` : ""}</span>
                <span><StatusBadge status={dataset.status} /></span>
                <span className="row-arrow"><ChevronRight size={17} /></span>
              </div>
            ))}
          </div>}
        </section>
      ))}
      {deletionReview && <DatasetDeletionDialog review={deletionReview} confirmation={confirmation} error={deletionError} deleting={deleting} onConfirmation={setConfirmation} onCancel={() => { setDeletionReview(null); setDeletionError(null); }} onDelete={() => void commitDeletion()} />}
    </div>
  );
}

function DatasetDeletionDialog(props: { review: DatasetDeletionReview; confirmation: string; error: string | null; deleting: boolean; onConfirmation: (value: string) => void; onCancel: () => void; onDelete: () => void }) {
  const totals = props.review.items.reduce((result, item) => ({ files: result.files + item.physical_files, bytes: result.bytes + item.physical_bytes, rows: result.rows + item.rows, jobs: result.jobs + item.collection_jobs + item.maintenance_jobs }), { files: 0, bytes: 0, rows: 0, jobs: 0 });
  return <div className="modal-backdrop"><section className="deletion-dialog" role="dialog" aria-modal="true"><header><div><p className="eyebrow">DELETION REVIEW</p><h2>永久删除 {props.review.dataset_ids.length} 个数据集</h2></div><button className="icon-button" onClick={props.onCancel}><X size={17} /></button></header><div className="deletion-warning"><Trash2 size={20} /><div><strong>该操作不可撤销</strong><span>数据库记录和数据根目录中的相关文件都会被直接物理删除。</span></div></div><div className="deletion-totals"><div><span>数据行</span><strong>{totals.rows.toLocaleString()}</strong></div><div><span>物理文件</span><strong>{totals.files}</strong></div><div><span>占用空间</span><strong>{formatDeletionBytes(totals.bytes)}</strong></div><div><span>任务记录</span><strong>{totals.jobs}</strong></div></div><div className="deletion-items">{props.review.items.map((item) => <div key={item.dataset_id}><strong>{item.display_name}</strong><code>{item.dataset_id}</code><span>{item.catalog_partitions} 个分区 · {item.collection_jobs} 个采集任务 · {item.physical_files} 个文件</span></div>)}</div>{props.review.blockers.length > 0 && <div className="deletion-blockers"><strong>当前禁止删除</strong>{props.review.blockers.map((item) => <span key={item}>{item}</span>)}</div>}<label className="deletion-confirm"><span>请输入以下完整文字确认：</span><code>{props.review.confirmation_text}</code><input value={props.confirmation} onChange={(event) => props.onConfirmation(event.target.value)} disabled={!props.review.can_delete || props.deleting} /></label>{props.error && <div className="form-error"><X size={17} />{props.error}</div>}<footer><button className="ghost-button" onClick={props.onCancel}>取消</button><button className="danger-button" disabled={!props.review.can_delete || props.confirmation !== props.review.confirmation_text || props.deleting} onClick={props.onDelete}>{props.deleting ? "正在物理删除…" : "永久删除"}</button></footer></section></div>;
}

function formatDeletionBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function CategoryQuickAdd({ categoryId, datasets, onChanged }: { categoryId: string; datasets: DatasetSummary[]; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [datasetId, setDatasetId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const candidates = datasets.filter((dataset) => dataset.category_id !== categoryId);

  async function add() {
    if (!datasetId) return;
    setSaving(true);
    setError(null);
    try {
      await api.assignDatasetCategory(datasetId, categoryId);
      setDatasetId("");
      setOpen(false);
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "添加数据集失败");
    } finally {
      setSaving(false);
    }
  }

  return <div className="category-quick-add">
    <button type="button" className="secondary-button" onClick={() => { setOpen((value) => !value); setError(null); }}><Plus size={14} />添加数据集</button>
    {open && <div className="category-quick-popover">
      <strong>添加到该大类</strong>
      <select value={datasetId} disabled={saving || !candidates.length} onChange={(event) => setDatasetId(event.target.value)}><option value="">{candidates.length ? "选择数据集" : "没有可添加的数据集"}</option>{candidates.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.display_name}{dataset.category_id ? "（从其他大类移动）" : "（未分类）"}</option>)}</select>
      <div><button type="button" className="ghost-button" onClick={() => setOpen(false)}>取消</button><button type="button" className="primary-button" disabled={saving || !datasetId} onClick={() => void add()}>{saving ? "添加中…" : "确认添加"}</button></div>
      {error && <span>{error}</span>}
    </div>}
  </div>;
}

function DatasetCategoryManager({ categories, datasets, onChanged }: { categories: DatasetCategory[]; datasets: DatasetSummary[]; onChanged: () => void }) {
  const [editing, setEditing] = useState<DatasetCategory | null>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setEditing(null);
    setName("");
    setDescription("");
    setError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return setError("请填写大类名称。");
    setSubmitting(true);
    setError(null);
    try {
      const payload = { name: name.trim(), description: description.trim() || null };
      if (editing) await api.updateDatasetCategory(editing.id, payload);
      else await api.createDatasetCategory(payload);
      reset();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存数据集大类失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(category: DatasetCategory) {
    if (!window.confirm(`确定删除空大类“${category.name}”吗？`)) return;
    setError(null);
    try {
      await api.deleteDatasetCategory(category.id);
      if (editing?.id === category.id) reset();
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "删除数据集大类失败");
    }
  }

  return (
    <section className="panel category-manager">
      <div className="card-title"><div><h2>数据集大类</h2><p>大类只用于人工整理数据集，不影响契约和采集。</p></div><span>{categories.length} 个大类</span></div>
      {error && <div className="maintenance-error"><X size={14} />{error}</div>}
      <form className="category-form" onSubmit={(event) => void submit(event)}>
        <label className="input-field"><span>大类名称<b>*</b></span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：A股数据" /></label>
        <label className="input-field"><span>说明</span><input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="可选" /></label>
        <button className="primary-button" disabled={submitting}>{submitting ? "保存中…" : editing ? "保存修改" : "创建大类"}</button>
        {editing && <button type="button" className="ghost-button" onClick={reset}>取消编辑</button>}
      </form>
      <div className="category-list">
        {categories.map((category) => <div className="category-block" key={category.id}>
          <div className="category-row"><div><strong>{category.name}</strong><span>{category.description || "暂无说明"}</span></div><b>{category.dataset_count} 个数据集</b><button type="button" className="toolbar-button" onClick={() => { setEditing(category); setName(category.name); setDescription(category.description ?? ""); setError(null); }}><Pencil size={13} />编辑</button><button type="button" className="toolbar-button danger-mini" disabled={category.dataset_count > 0} onClick={() => void remove(category)}><Trash2 size={13} />删除</button></div>
          <CategoryDatasetEditor category={category} datasets={datasets} onChanged={onChanged} />
        </div>)}
        {!categories.length && <div className="dataset-group-empty">还没有数据集大类。</div>}
      </div>
    </section>
  );
}

function CategoryDatasetEditor({ category, datasets, onChanged }: { category: DatasetCategory; datasets: DatasetSummary[]; onChanged: () => void }) {
  const [datasetId, setDatasetId] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const members = datasets.filter((dataset) => dataset.category_id === category.id);
  const candidates = datasets.filter((dataset) => dataset.category_id !== category.id);

  async function assign(targetDatasetId: string, targetCategoryId: string | null) {
    setSaving(true);
    setError(null);
    try {
      await api.assignDatasetCategory(targetDatasetId, targetCategoryId);
      setDatasetId("");
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "调整数据集大类失败");
    } finally {
      setSaving(false);
    }
  }

  return <div className="category-datasets">
    <div className="category-members">
      {members.map((dataset) => <span className="category-member" key={dataset.id}><span><strong>{dataset.display_name}</strong><code>{dataset.id}</code></span><button type="button" disabled={saving} title="移出大类" onClick={() => void assign(dataset.id, null)}><X size={13} /></button></span>)}
      {!members.length && <span className="category-no-members">该大类下还没有数据集。</span>}
    </div>
    <div className="category-add-dataset">
      <select value={datasetId} disabled={saving || !candidates.length} onChange={(event) => setDatasetId(event.target.value)}><option value="">选择要添加的数据集</option>{candidates.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.display_name}{dataset.category_id ? "（从其他大类移动）" : "（未分类）"}</option>)}</select>
      <button type="button" className="secondary-button" disabled={saving || !datasetId} onClick={() => void assign(datasetId, category.id)}><Plus size={14} />{saving ? "保存中…" : "添加数据集"}</button>
    </div>
    {error && <span className="category-editor-error">{error}</span>}
  </div>;
}

function DatasetForm(props: { collectors: CollectorDefinition[]; datasets: DatasetSummary[]; dataset?: DatasetDetail; onCancel: () => void; onSaved: (dataset: DatasetDetail) => void }) {
  const editing = Boolean(props.dataset);
  const [provider, setProvider] = useState(props.dataset?.provider ?? "");
  const [region, setRegion] = useState(props.dataset?.region ?? "cn");
  const [instrument, setInstrument] = useState(props.dataset?.instrument ?? "stock");
  const [datasetName, setDatasetName] = useState(props.dataset?.dataset_name ?? "");
  const [market, setMarket] = useState(props.dataset?.market ?? "");
  const [displayName, setDisplayName] = useState(props.dataset?.display_name ?? "");
  const [description, setDescription] = useState(props.dataset?.description ?? "");
  const [bindings, setBindings] = useState<Record<CollectionPurpose, string>>(() => {
    const values = { initial: "", incremental: "", repair: "", replace: "" };
    for (const binding of props.dataset?.collection_bindings ?? []) {
      values[binding.purpose] = `${binding.collector_key}::${binding.operation}`;
    }
    return values;
  });
  const [storageLayout, setStorageLayout] = useState(props.dataset?.storage_policy?.layout ?? "");
  const [partitionField, setPartitionField] = useState(
    props.dataset?.storage_policy?.logical_partition_field ?? "",
  );
  const [calendarDatasetId, setCalendarDatasetId] = useState(
    props.dataset?.storage_policy?.calendar_dataset_id ?? "",
  );
  const [timeField, setTimeField] = useState(props.dataset?.schema.time_field ?? "");
  const initialFields = props.dataset?.schema.fields.map((field, index) => ({
    key: index + 1,
    name: field.name,
    data_type: field.data_type,
    nullable: field.nullable,
    description: field.description,
    unit: field.unit ?? "",
    source_name: field.source_name ?? "",
    primary: props.dataset?.schema.primary_key.includes(field.name) ?? false,
  })) ?? [newField(1)];
  const [fields, setFields] = useState<FieldDraft[]>(initialFields);
  const [nextKey, setNextKey] = useState(initialFields.length + 1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const segments = [provider, region, instrument, datasetName, market].filter(Boolean);
  const datasetId = props.dataset?.id ?? segments.join(".");
  const validFields = fields.filter((field) => field.name.trim());
  const registeredOperations = props.collectors.flatMap((collector) =>
    collector.operations.map((operation) => ({ collector, operation })),
  );

  function updateField(key: number, patch: Partial<FieldDraft>) {
    setFields((current) => current.map((field) => field.key === key ? { ...field, ...patch } : field));
  }

  function addField() {
    setFields((current) => [...current, newField(nextKey)]);
    setNextKey((value) => value + 1);
  }

  function removeField(key: number) {
    setFields((current) => current.length === 1 ? current : current.filter((field) => field.key !== key));
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!provider || !datasetName || !displayName) return setError("请填写供应商、数据集名称和显示名称。");
    if (!validFields.length) return setError("请至少定义一个字段。");
    if (validFields.some((field) => !field.description.trim())) return setError("每个字段都需要填写说明。");
    const primaryKey = validFields.filter((field) => field.primary).map((field) => field.name);
    if (!primaryKey.length) return setError("请至少选择一个主键字段。");
    if (partitionField.trim() && !calendarDatasetId) return setError("日期分区数据集必须绑定交易日历数据集。");

    const payload: DatasetCreatePayload = {
      id: datasetId,
      provider,
      region,
      instrument,
      dataset_name: datasetName,
      market: market || null,
      display_name: displayName,
      description: description || null,
      collection_bindings: (Object.entries(bindings) as Array<[CollectionPurpose, string]>)
        .filter(([, value]) => value)
        .map(([purpose, value]) => {
          const [collector_key, operation] = value.split("::");
          return { purpose, collector_key, operation, parameters: {} };
        }),
      storage_policy: storageLayout
        ? {
            logical_partition_field: partitionField || null,
            calendar_dataset_id: partitionField ? calendarDatasetId || null : null,
            layout: storageLayout as "daily" | "yearly_with_delta" | "snapshot",
            write_strategy: storageLayout === "snapshot" ? "replace_snapshot" : "replace_partition",
            compaction: storageLayout === "yearly_with_delta" ? "yearly" : null,
          }
        : null,
      primary_key: primaryKey,
      time_field: timeField || null,
      fields: validFields.map((field) => ({
        name: field.name,
        data_type: field.data_type,
        nullable: field.nullable,
        description: field.description,
        unit: field.unit || null,
        source_name: field.source_name || null,
      })),
    };

    setSubmitting(true);
    try {
      const saved = editing
        ? await api.updateDataset(datasetId, {
            display_name: payload.display_name,
            description: payload.description,
            collection_bindings: payload.collection_bindings,
            storage_policy: payload.storage_policy,
            primary_key: payload.primary_key,
            time_field: payload.time_field,
            fields: payload.fields,
          })
        : await api.createDataset(payload);
      props.onSaved(saved);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="page create-page" onSubmit={(event) => void submit(event)}>
      <header className="page-header compact">
        <div><button type="button" className="back-button" onClick={props.onCancel}><ArrowLeft size={16} />返回数据集</button><h1>{editing ? "编辑数据集" : "创建数据集"}</h1><p className="subtitle">{editing ? "修改草稿的数据契约，数据集 ID 保持不变。" : "定义供应商数据集的身份与数据契约。"}</p></div>
        <div className="header-actions"><button type="button" className="ghost-button" onClick={props.onCancel}>取消</button><button className="primary-button" disabled={submitting}>{submitting ? "正在保存…" : editing ? "保存修改" : "创建草稿"}</button></div>
      </header>

      {error && <div className="form-error"><X size={17} />{error}</div>}

      <section className="form-section">
        <div className="section-number">01</div><div className="section-intro"><h2>数据集身份</h2><p>ID 创建后保持稳定；已启用契约需要实质变化时，请创建独立的新数据集。</p></div>
        <div className="form-content">
          <div className="form-grid five-columns">
            <Input label="供应商" value={provider} onChange={setProvider} placeholder="tushare" required idSegment disabled={editing} />
            <Input label="区域" value={region} onChange={setRegion} placeholder="cn" required idSegment disabled={editing} />
            <Input label="品种" value={instrument} onChange={setInstrument} placeholder="stock" required idSegment disabled={editing} />
            <Input label="数据集名称" value={datasetName} onChange={setDatasetName} placeholder="daily" required idSegment disabled={editing} />
            <Input label="市场（可选）" value={market} onChange={setMarket} placeholder="sh" idSegment disabled={editing} />
          </div>
          <div className="id-preview"><span>数据集 ID</span><code>{datasetId || "provider.region.instrument.dataset[.market]"}</code></div>
          <div className="form-grid two-columns">
            <Input label="显示名称" value={displayName} onChange={setDisplayName} placeholder="上海股票逐笔委托" required />
            <Input label="说明" value={description} onChange={setDescription} placeholder="说明数据来源、内容和用途" />
          </div>
        </div>
      </section>

      <section className="form-section">
        <div className="section-number">02</div><div className="section-intro"><h2>采集绑定</h2><p>指定负责生成该数据集的采集器操作。</p></div>
        <div className="form-content">
          <div className="binding-grid">
            {(Object.keys(purposeLabels) as CollectionPurpose[]).map((purpose) => {
              const options = registeredOperations.filter(({ operation }) => operation.purpose === purpose);
              return <label className="input-field" key={purpose}><span>{purposeLabels[purpose]}</span><select value={bindings[purpose]} onChange={(event) => setBindings((current) => ({ ...current, [purpose]: event.target.value }))}><option value="">不支持</option>{options.map(({ collector, operation }) => <option key={`${collector.key}::${operation.key}`} value={`${collector.key}::${operation.key}`}>{collector.name} · {operation.name}</option>)}</select></label>;
            })}
          </div>
          {(Object.entries(bindings) as Array<[CollectionPurpose, string]>).filter(([, value]) => value).map(([purpose, value]) => { const [collectorKey, operationKey] = value.split("::"); const operation = registeredOperations.find((item) => item.collector.key === collectorKey && item.operation.key === operationKey)?.operation; return operation ? <div className="binding-preview" key={purpose}><strong>{purposeLabels[purpose]}</strong><span>{collectorKey} · {operation.key}</span><span>{operation.joint ? "联合更新" : "独立更新"}，输出 {operation.datasets.length} 个数据集</span>{operation.datasets.map((id) => <code key={id}>{id}</code>)}</div> : null; })}
        </div>
      </section>

      <section className="form-section">
        <div className="section-number">03</div><div className="section-intro"><h2>存储策略</h2><p>约定逻辑分区和正式 Parquet 文件的组织方式。</p></div>
        <div className="form-content">
          <div className="form-grid two-columns no-margin">
            <label className="input-field"><span>物理布局</span><select value={storageLayout} onChange={(event) => setStorageLayout(event.target.value)}><option value="">暂不配置</option><option value="daily">单日文件</option><option value="yearly_with_delta">年度主文件 + 日增量</option><option value="snapshot">完整快照</option></select></label>
            <label className="input-field"><span>逻辑分区字段</span><input value={partitionField} disabled={!storageLayout || storageLayout === "snapshot"} onChange={(event) => setPartitionField(event.target.value)} placeholder="trade_date" /></label>
          </div>
          {partitionField && <label className="input-field calendar-binding"><span>交易日历数据集</span><select value={calendarDatasetId} onChange={(event) => setCalendarDatasetId(event.target.value)}><option value="">请选择交易日历数据集</option>{props.datasets.filter((item) => item.id !== datasetId && item.storage_policy?.layout === "snapshot").map((item) => <option key={item.id} value={item.id}>{item.display_name} · {item.id}</option>)}</select><small>采集计划只会生成日历中标记为交易日的日期；日历必须先启用并发布数据。</small></label>}
          {partitionField && !props.datasets.some((item) => item.id !== datasetId && item.storage_policy?.layout === "snapshot") && <div className="calendar-warning">当前没有可绑定的交易日历，请先创建并启用交易日历数据集。</div>}
          {storageLayout === "yearly_with_delta" && <div className="operation-help">每日审核通过后立即发布为增量 Parquet，后续按年度合并；Catalog 仍逐日记录覆盖。</div>}
        </div>
      </section>

      <section className="form-section fields-section">
        <div className="section-number">04</div><div className="section-intro"><h2>字段定义</h2><p>描述字段类型、语义、可空性与主键。</p></div>
        <div className="form-content">
          <div className="fields-table">
            <div className="field-row field-head"><span>主键</span><span>字段名</span><span>数据类型</span><span>字段说明</span><span>原始字段</span><span>单位</span><span>可空</span><span /></div>
            {fields.map((field) => (
              <div className="field-row" key={field.key}>
                <label className="check-cell"><input type="checkbox" checked={field.primary} onChange={(event) => updateField(field.key, { primary: event.target.checked })} /><span /></label>
                <input value={field.name} onChange={(event) => updateField(field.key, { name: event.target.value })} placeholder="trade_date" />
                <select value={field.data_type} onChange={(event) => updateField(field.key, { data_type: event.target.value })}>{fieldTypes.map((type) => <option key={type}>{type}</option>)}</select>
                <input value={field.description} onChange={(event) => updateField(field.key, { description: event.target.value })} placeholder="交易日期" />
                <input value={field.source_name} onChange={(event) => updateField(field.key, { source_name: event.target.value })} placeholder="可选" />
                <input value={field.unit} onChange={(event) => updateField(field.key, { unit: event.target.value })} placeholder="可选" />
                <label className="switch-cell"><input type="checkbox" checked={field.nullable} onChange={(event) => updateField(field.key, { nullable: event.target.checked })} /><span /></label>
                <button type="button" className="icon-button" onClick={() => removeField(field.key)} aria-label="删除字段"><Trash2 size={15} /></button>
              </div>
            ))}
          </div>
          <div className="fields-footer">
            <button type="button" className="add-field" onClick={addField}><Plus size={15} />添加字段</button>
            <label className="select-field"><span>时间字段</span><select value={timeField} onChange={(event) => setTimeField(event.target.value)}><option value="">不指定</option>{validFields.map((field) => <option key={field.key} value={field.name}>{field.name}</option>)}</select></label>
          </div>
        </div>
      </section>
    </form>
  );
}

function DatasetMetadataForm(props: { dataset: DatasetDetail; onCancel: () => void; onSaved: (dataset: DatasetDetail) => void }) {
  const [displayName, setDisplayName] = useState(props.dataset.display_name);
  const [description, setDescription] = useState(props.dataset.description ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!displayName.trim()) {
      setError("请填写显示名称。");
      return;
    }
    setSubmitting(true);
    try {
      props.onSaved(await api.updateDatasetMetadata(props.dataset.id, {
        display_name: displayName.trim(),
        description: description.trim() || null,
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="page create-page" onSubmit={(event) => void submit(event)}>
      <header className="page-header compact">
        <div><button type="button" className="back-button" onClick={props.onCancel}><ArrowLeft size={16} />返回数据集</button><h1>编辑基本信息</h1><p className="subtitle">修改展示信息，不改变数据集身份、Schema 或已发布数据。</p></div>
        <div className="header-actions"><button type="button" className="ghost-button" onClick={props.onCancel}>取消</button><button className="primary-button" disabled={submitting}>{submitting ? "正在保存…" : "保存修改"}</button></div>
      </header>

      {error && <div className="form-error"><X size={17} />{error}</div>}

      <section className="form-section">
        <div className="section-number">01</div><div className="section-intro"><h2>展示信息</h2><p>已启用数据集可以更新名称和说明。</p></div>
        <div className="form-content">
          <div className="id-preview"><span>数据集 ID（不可修改）</span><code>{props.dataset.id}</code></div>
          <div className="form-grid two-columns">
            <Input label="显示名称" value={displayName} onChange={setDisplayName} placeholder="数据集显示名称" required />
            <Input label="说明" value={description} onChange={setDescription} placeholder="说明数据来源、内容和用途" />
          </div>
          <div className="operation-help">字段、主键、采集绑定和存储策略属于当前数据集契约；如需实质变更，请创建独立的新数据集。</div>
        </div>
      </section>
    </form>
  );
}

function DatasetDetailView(props: { dataset: DatasetDetail; categories: DatasetCategory[]; onBack: () => void; onEdit: () => void; onEditMetadata: () => void; onCollect: (operation: CollectionPurpose) => void; onChanged: (dataset: DatasetDetail) => void }) {
  const [activating, setActivating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function activate() {
    setActivating(true);
    setError(null);
    try {
      props.onChanged(await api.activateDataset(props.dataset.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "启用失败");
    } finally {
      setActivating(false);
    }
  }

  const dataset = props.dataset;
  return (
    <div className="page">
      <header className="page-header compact">
        <div><button className="back-button" onClick={props.onBack}><ArrowLeft size={16} />返回数据集</button><div className="title-line"><h1>{dataset.display_name}</h1><StatusBadge status={dataset.status} /></div><code className="large-id">{dataset.id}</code></div>
        {dataset.status === "draft" ? <div className="header-actions"><button className="ghost-button" onClick={props.onEdit}><Pencil size={16} />编辑</button><button className="primary-button" onClick={() => void activate()} disabled={activating}><Check size={17} />{activating ? "正在启用…" : "启用数据集"}</button></div> : <div className="header-actions"><button className="ghost-button" onClick={props.onEditMetadata}><Pencil size={16} />编辑基本信息</button></div>}
      </header>
      {error && <div className="form-error"><X size={17} />{error}</div>}

      <section className="detail-grid">
        <div className="panel detail-card span-two"><div className="card-title"><h2>基本信息</h2></div><dl className="metadata-grid"><div><dt>供应商</dt><dd>{dataset.provider}</dd></div><div><dt>区域</dt><dd>{dataset.region.toUpperCase()}</dd></div><div><dt>品种</dt><dd>{dataset.instrument}</dd></div><div><dt>市场</dt><dd>{dataset.market?.toUpperCase() || "不限定"}</dd></div><div className="wide"><dt>说明</dt><dd>{dataset.description || "暂无说明"}</dd></div></dl></div>
        <div className="panel detail-card"><div className="card-title"><h2>数据契约</h2></div><dl className="contract-list"><div><dt>字段数量</dt><dd>{dataset.schema.fields.length}</dd></div><div><dt>主键</dt><dd>{dataset.schema.primary_key.join(" + ")}</dd></div><div><dt>时间字段</dt><dd>{dataset.schema.time_field || "未指定"}</dd></div><div><dt>存储布局</dt><dd>{dataset.storage_policy?.layout || "未配置"}</dd></div>{dataset.storage_policy?.calendar_dataset_id && <div><dt>交易日历</dt><dd>{dataset.storage_policy.calendar_dataset_id}</dd></div>}{dataset.collection_bindings.map((binding) => <div key={binding.purpose}><dt>{purposeLabels[binding.purpose]}</dt><dd>{binding.collector_key} · {binding.operation}</dd></div>)}{!dataset.collection_bindings.length && <div><dt>采集绑定</dt><dd>未绑定</dd></div>}</dl></div>
      </section>

      <DatasetCategoryAssignment dataset={dataset} categories={props.categories} onChanged={props.onChanged} />

      <DatasetCollectionActions dataset={dataset} onCollect={props.onCollect} />

      <DatasetPreview dataset={dataset} />

      {dataset.storage_policy?.compaction === "yearly" && <DatasetMaintenance dataset={dataset} />}

      <section className="panel fields-detail">
        <div className="card-title"><div><h2>字段</h2><p>当前数据集契约</p></div><span>{dataset.schema.fields.length} 个字段</span></div>
        <div className="schema-table">
          <div className="schema-row schema-head"><span>序号</span><span>字段名</span><span>类型</span><span>说明</span><span>约束</span></div>
          {dataset.schema.fields.map((field, index) => (
            <div className="schema-row" key={field.name}><span>{String(index + 1).padStart(2, "0")}</span><code>{field.name}</code><span>{field.data_type}</span><span>{field.description}</span><span className="constraints">{dataset.schema.primary_key.includes(field.name) && <em>主键</em>}{!field.nullable && <em>非空</em>}{dataset.schema.time_field === field.name && <em>时间</em>}</span></div>
          ))}
        </div>
      </section>
    </div>
  );
}

function DatasetCategoryAssignment({ dataset, categories, onChanged }: { dataset: DatasetDetail; categories: DatasetCategory[]; onChanged: (dataset: DatasetDetail) => void }) {
  const [categoryId, setCategoryId] = useState(dataset.category_id ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setCategoryId(dataset.category_id ?? ""), [dataset.category_id]);

  async function save() {
    setSaving(true);
    setError(null);
    try {
      onChanged(await api.assignDatasetCategory(dataset.id, categoryId || null));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "保存数据集大类失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel dataset-category-assignment">
      <div><strong>数据集大类</strong><span>手动将该数据集归入一个大类，仅影响目录展示。</span></div>
      <select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">未分类</option>{categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select>
      <button type="button" className="primary-button" disabled={saving || categoryId === (dataset.category_id ?? "")} onClick={() => void save()}>{saving ? "保存中…" : "保存分类"}</button>
      {error && <span className="category-assignment-error">{error}</span>}
    </section>
  );
}

function DatasetCollectionActions({ dataset, onCollect }: { dataset: DatasetDetail; onCollect: (operation: CollectionPurpose) => void }) {
  const [readiness, setReadiness] = useState<CollectionReadiness | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setReadiness(null);
    setError(null);
    void api.getCollectionReadiness(dataset.id)
      .then((result) => { if (active) setReadiness(result); })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : "无法读取采集状态"); });
    return () => { active = false; };
  }, [dataset.id]);

  const initialRequired = readiness?.initial_required ?? true;
  return (
    <section className="panel dataset-collection-panel">
      <div className="card-title">
        <div><h2>数据采集</h2><p>{initialRequired ? "该数据集必须先完成首次采集并发布数据，之后才能执行其他采集。" : "首次采集已完成，可以执行增量更新或其他契约操作。"}</p></div>
        {readiness && <span className={initialRequired ? "collection-gate pending" : "collection-gate ready"}>{initialRequired ? "等待首次采集" : "可增量更新"}</span>}
      </div>
      {error && <div className="maintenance-error"><X size={14} />{error}</div>}
      <div className="dataset-collection-actions">
        {dataset.collection_bindings.map((binding) => {
          const isInitial = binding.purpose === "initial";
          const disabled = dataset.status !== "active" || !readiness || (isInitial ? !initialRequired : initialRequired);
          const label = isInitial && !initialRequired ? "首次采集已完成" : purposeLabels[binding.purpose];
          return <button type="button" className={isInitial ? "primary-button" : "secondary-button"} disabled={disabled} key={binding.purpose} onClick={() => onCollect(binding.purpose)}><RefreshCw size={15} />{label}</button>;
        })}
        {!dataset.collection_bindings.length && <span className="collection-empty">该数据集尚未绑定采集器操作。</span>}
      </div>
      {dataset.status !== "active" && <p className="collection-hint">请先启用数据集，再开始首次采集。</p>}
    </section>
  );
}

const maintenanceStatusLabels: Record<MaintenanceJob["status"], string> = {
  queued: "排队中",
  running: "合并中",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

function DatasetMaintenance({ dataset }: { dataset: DatasetDetail }) {
  const [jobs, setJobs] = useState<MaintenanceJob[]>([]);
  const [year, setYear] = useState(new Date().getFullYear() - 1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadJobs = useCallback(async (silent = false) => {
    if (!silent) setError(null);
    try {
      setJobs(await api.listMaintenanceJobs(dataset.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取维护任务");
    }
  }, [dataset.id]);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  const active = jobs.some((job) => job.status === "queued" || job.status === "running");
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => void loadJobs(true), 2000);
    return () => window.clearInterval(timer);
  }, [active, loadJobs]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const job = await api.createCompactionJob(dataset.id, year);
      setJobs((current) => [job, ...current]);
      setNotice(`${year} 年数据已提交后台合并。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交合并任务失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancel(job: MaintenanceJob) {
    setError(null);
    try {
      const cancelled = await api.cancelMaintenanceJob(job.id);
      setJobs((current) => current.map((item) => item.id === job.id ? cancelled : item));
      setNotice(`${String(job.parameters.year)} 年合并任务已取消。`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "取消维护任务失败");
    }
  }

  return (
    <section className="panel maintenance-panel">
      <div className="card-title">
        <div><h2>年度数据合并</h2><p>将该年度的日增量 Parquet 合并为一个年度文件；采集与合并共用同一后台队列。</p></div>
        {active && <span><RefreshCw size={12} className="spin" />后台任务运行中</span>}
      </div>
      <div className="maintenance-controls">
        <label><span>合并年份</span><input type="number" min="1990" max="2100" value={year} onChange={(event) => setYear(Number(event.target.value))} /></label>
        <button type="button" className="primary-button" onClick={() => void submit()} disabled={submitting || dataset.status !== "active"}><RefreshCw size={15} className={submitting ? "spin" : ""} />{submitting ? "提交中…" : "开始后台合并"}</button>
        {dataset.status !== "active" && <small>数据集启用后才能执行合并。</small>}
      </div>
      {notice && <div className="maintenance-notice">{notice}</div>}
      {error && <div className="maintenance-error"><X size={14} />{error}</div>}
      <div className="maintenance-list">
        <div className="maintenance-row maintenance-head"><span>年份</span><span>状态</span><span>结果</span><span>更新时间</span><span>操作</span></div>
        {jobs.slice(0, 8).map((job) => (
          <div className="maintenance-row" key={job.id}>
            <strong>{String(job.parameters.year)}</strong>
            <span className={`maintenance-status maintenance-status-${job.status}`}>{maintenanceStatusLabels[job.status]}</span>
            <span className={job.error ? "maintenance-job-error" : ""}>{job.error ?? describeMaintenanceResult(job.result)}</span>
            <span>{formatMaintenanceTime(job.updated_at)}</span>
            <span>{job.status === "queued" ? <button type="button" className="toolbar-button" onClick={() => void cancel(job)}><Ban size={13} />取消排队</button> : "—"}</span>
          </div>
        ))}
        {!jobs.length && <p className="maintenance-empty">还没有年度合并记录。</p>}
      </div>
    </section>
  );
}

function describeMaintenanceResult(result: Record<string, unknown> | null) {
  if (!result) return "—";
  if (result.status === "empty") return "该年份没有可合并分区";
  if (result.status === "already_compacted") return "已经是年度文件";
  const partitions = Number(result.partitions ?? 0).toLocaleString();
  const rows = Number(result.rows ?? 0).toLocaleString();
  return `${partitions} 个分区 · ${rows} 行`;
}

function formatMaintenanceTime(value: string) {
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}Z`;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(normalized));
}

function StatusBadge({ status }: { status: DatasetSummary["status"] }) {
  return <span className={`status status-${status}`}><i />{statusLabels[status]}</span>;
}

function Input(props: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; required?: boolean; idSegment?: boolean; disabled?: boolean }) {
  function change(value: string) {
    props.onChange(props.idSegment ? value.toLowerCase().replace(/[^a-z0-9_]/g, "") : value);
  }
  return <label className="input-field"><span>{props.label}{props.required && <b>*</b>}</span><input value={props.value} onChange={(event) => change(event.target.value)} placeholder={props.placeholder} disabled={props.disabled} /></label>;
}

export default App;
