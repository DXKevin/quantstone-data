import {
  Activity,
  ArrowLeft,
  Check,
  ChevronRight,
  CircleHelp,
  Database,
  FileCode2,
  Layers3,
  Plus,
  Search,
  Settings,
  Trash2,
  X,
} from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { api, DatasetCreatePayload, DatasetDetail, DatasetSummary } from "./api";

type View = "list" | "create" | "detail";

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

function App() {
  const [view, setView] = useState<View>("list");
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [selected, setSelected] = useState<DatasetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const loadDatasets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setDatasets(await api.listDatasets());
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

  async function handleCreated(dataset: DatasetDetail) {
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
          <button className="nav-item active"><Database size={17} />数据集</button>
          <button className="nav-item" disabled><Activity size={17} />采集任务<span>稍后</span></button>
          <button className="nav-item" disabled><FileCode2 size={17} />存储目录<span>稍后</span></button>
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item" disabled><CircleHelp size={17} />帮助</button>
          <button className="nav-item" disabled><Settings size={17} />设置</button>
          <div className="version">QuantStone Data · v0.1.0</div>
        </div>
      </aside>

      <main className="main-area">
        {view === "list" && (
          <DatasetList
            datasets={filtered}
            total={datasets.length}
            loading={loading}
            error={error}
            query={query}
            onQuery={setQuery}
            onCreate={() => setView("create")}
            onOpen={(id) => void openDataset(id)}
            onRetry={() => void loadDatasets()}
          />
        )}
        {view === "create" && (
          <CreateDataset onCancel={() => setView("list")} onCreated={(data) => void handleCreated(data)} />
        )}
        {view === "detail" && selected && (
          <DatasetDetailView
            dataset={selected}
            onBack={() => setView("list")}
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

function DatasetList(props: {
  datasets: DatasetSummary[];
  total: number;
  loading: boolean;
  error: string | null;
  query: string;
  onQuery: (value: string) => void;
  onCreate: () => void;
  onOpen: (id: string) => void;
  onRetry: () => void;
}) {
  return (
    <div className="page">
      <header className="page-header">
        <div><p className="eyebrow">DATASET REGISTRY</p><h1>数据集</h1><p className="subtitle">定义并管理供应商数据集的字段契约与版本。</p></div>
        <button className="primary-button" onClick={props.onCreate}><Plus size={17} />创建数据集</button>
      </header>

      <section className="summary-strip">
        <div><span>数据集总数</span><strong>{props.total}</strong></div>
        <div><span>已启用</span><strong>{props.datasets.filter((item) => item.status === "active").length}</strong></div>
        <div><span>草稿</span><strong>{props.datasets.filter((item) => item.status === "draft").length}</strong></div>
        <div><span>当前模块</span><strong className="summary-text">注册中心</strong></div>
      </section>

      <section className="panel">
        <div className="panel-toolbar">
          <div><h2>全部数据集</h2><span>{props.total} 个数据集</span></div>
          <label className="search-box"><Search size={16} /><input value={props.query} onChange={(event) => props.onQuery(event.target.value)} placeholder="搜索 ID 或名称" /></label>
        </div>

        {props.error ? (
          <div className="state-box error-state"><strong>无法连接 Registry API</strong><p>{props.error}</p><button onClick={props.onRetry}>重新加载</button></div>
        ) : props.loading ? (
          <div className="state-box"><div className="loader" /><p>正在加载数据集…</p></div>
        ) : props.datasets.length === 0 ? (
          <div className="state-box empty-state"><Database size={28} /><strong>还没有数据集</strong><p>创建第一个数据集，开始定义字段契约。</p><button className="secondary-button" onClick={props.onCreate}><Plus size={16} />创建数据集</button></div>
        ) : (
          <div className="dataset-table">
            <div className="table-row table-head"><span>数据集</span><span>供应商</span><span>区域 / 品种</span><span>Schema</span><span>状态</span><span /></div>
            {props.datasets.map((dataset) => (
              <button className="table-row data-row" key={dataset.id} onClick={() => props.onOpen(dataset.id)}>
                <span className="dataset-cell"><strong>{dataset.display_name}</strong><code>{dataset.id}</code></span>
                <span>{dataset.provider}</span>
                <span>{dataset.region.toUpperCase()} / {dataset.instrument}{dataset.market ? ` / ${dataset.market.toUpperCase()}` : ""}</span>
                <span>v{dataset.current_schema_version}</span>
                <span><StatusBadge status={dataset.status} /></span>
                <span className="row-arrow"><ChevronRight size={17} /></span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function CreateDataset(props: { onCancel: () => void; onCreated: (dataset: DatasetDetail) => void }) {
  const [provider, setProvider] = useState("");
  const [region, setRegion] = useState("cn");
  const [instrument, setInstrument] = useState("stock");
  const [datasetName, setDatasetName] = useState("");
  const [market, setMarket] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [timeField, setTimeField] = useState("");
  const [fields, setFields] = useState<FieldDraft[]>([newField(1)]);
  const [nextKey, setNextKey] = useState(2);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const segments = [provider, region, instrument, datasetName, market].filter(Boolean);
  const datasetId = segments.join(".");
  const validFields = fields.filter((field) => field.name.trim());

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

    const payload: DatasetCreatePayload = {
      id: datasetId,
      provider,
      region,
      instrument,
      dataset_name: datasetName,
      market: market || null,
      display_name: displayName,
      description: description || null,
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
      props.onCreated(await api.createDataset(payload));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="page create-page" onSubmit={(event) => void submit(event)}>
      <header className="page-header compact">
        <div><button type="button" className="back-button" onClick={props.onCancel}><ArrowLeft size={16} />返回数据集</button><h1>创建数据集</h1><p className="subtitle">定义供应商数据集的身份与首个 Schema 版本。</p></div>
        <div className="header-actions"><button type="button" className="ghost-button" onClick={props.onCancel}>取消</button><button className="primary-button" disabled={submitting}>{submitting ? "正在创建…" : "创建草稿"}</button></div>
      </header>

      {error && <div className="form-error"><X size={17} />{error}</div>}

      <section className="form-section">
        <div className="section-number">01</div><div className="section-intro"><h2>数据集身份</h2><p>ID 创建后保持稳定，结构变化使用 Schema 版本表示。</p></div>
        <div className="form-content">
          <div className="form-grid five-columns">
            <Input label="供应商" value={provider} onChange={setProvider} placeholder="tushare" required idSegment />
            <Input label="区域" value={region} onChange={setRegion} placeholder="cn" required idSegment />
            <Input label="品种" value={instrument} onChange={setInstrument} placeholder="stock" required idSegment />
            <Input label="数据集名称" value={datasetName} onChange={setDatasetName} placeholder="daily" required idSegment />
            <Input label="市场（可选）" value={market} onChange={setMarket} placeholder="sh" idSegment />
          </div>
          <div className="id-preview"><span>数据集 ID</span><code>{datasetId || "provider.region.instrument.dataset[.market]"}</code></div>
          <div className="form-grid two-columns">
            <Input label="显示名称" value={displayName} onChange={setDisplayName} placeholder="上海股票逐笔委托" required />
            <Input label="说明" value={description} onChange={setDescription} placeholder="说明数据来源、内容和用途" />
          </div>
        </div>
      </section>

      <section className="form-section fields-section">
        <div className="section-number">02</div><div className="section-intro"><h2>字段定义</h2><p>描述字段类型、语义、可空性与主键。</p></div>
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

function DatasetDetailView(props: { dataset: DatasetDetail; onBack: () => void; onChanged: (dataset: DatasetDetail) => void }) {
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
        {dataset.status === "draft" && <button className="primary-button" onClick={() => void activate()} disabled={activating}><Check size={17} />{activating ? "正在启用…" : "启用数据集"}</button>}
      </header>
      {error && <div className="form-error"><X size={17} />{error}</div>}

      <section className="detail-grid">
        <div className="panel detail-card span-two"><div className="card-title"><h2>基本信息</h2><span>Schema v{dataset.schema.version}</span></div><dl className="metadata-grid"><div><dt>供应商</dt><dd>{dataset.provider}</dd></div><div><dt>区域</dt><dd>{dataset.region.toUpperCase()}</dd></div><div><dt>品种</dt><dd>{dataset.instrument}</dd></div><div><dt>市场</dt><dd>{dataset.market?.toUpperCase() || "不限定"}</dd></div><div className="wide"><dt>说明</dt><dd>{dataset.description || "暂无说明"}</dd></div></dl></div>
        <div className="panel detail-card"><div className="card-title"><h2>数据契约</h2></div><dl className="contract-list"><div><dt>字段数量</dt><dd>{dataset.schema.fields.length}</dd></div><div><dt>主键</dt><dd>{dataset.schema.primary_key.join(" + ")}</dd></div><div><dt>时间字段</dt><dd>{dataset.schema.time_field || "未指定"}</dd></div></dl></div>
      </section>

      <section className="panel fields-detail">
        <div className="card-title"><div><h2>字段</h2><p>当前生效的 Schema v{dataset.schema.version}</p></div><span>{dataset.schema.fields.length} 个字段</span></div>
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

function StatusBadge({ status }: { status: DatasetSummary["status"] }) {
  return <span className={`status status-${status}`}><i />{statusLabels[status]}</span>;
}

function Input(props: { label: string; value: string; onChange: (value: string) => void; placeholder?: string; required?: boolean; idSegment?: boolean }) {
  function change(value: string) {
    props.onChange(props.idSegment ? value.toLowerCase().replace(/[^a-z0-9_]/g, "") : value);
  }
  return <label className="input-field"><span>{props.label}{props.required && <b>*</b>}</span><input value={props.value} onChange={(event) => change(event.target.value)} placeholder={props.placeholder} /></label>;
}

export default App;
