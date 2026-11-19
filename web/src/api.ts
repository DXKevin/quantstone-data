export type DatasetStatus = "draft" | "active" | "paused" | "deprecated";
export type UpdateFrequency = "daily" | "weekly" | "monthly" | "manual";
export type TimeGranularity = "tick" | "second_3" | "second" | "minute" | "hour" | "day" | "none";
export type CollectionOperation = "initial" | "incremental" | "repair" | "replace";
export type CollectionPurpose = CollectionOperation;
export type CollectionInputMethod = "collector" | "file_import";
export type CollectionJobStatus =
  | "created"
  | "queued"
  | "running"
  | "cancelling"
  | "cancelled"
  | "awaiting_file"
  | "staged"
  | "review_passed"
  | "review_failed"
  | "succeeded"
  | "failed";

export interface DatasetStoragePolicy {
  logical_partition_field: string | null;
  calendar_dataset_id: string | null;
  layout: "daily" | "yearly_with_delta" | "snapshot";
  write_strategy: "append" | "replace_partition" | "replace_snapshot";
  compaction: "yearly" | null;
}

export interface DatasetSummary {
  id: string;
  display_name: string;
  provider: string;
  region: string;
  instrument: string;
  market: string | null;
  category_id: string | null;
  update_frequency: UpdateFrequency;
  time_granularity: TimeGranularity;
  status: DatasetStatus;
  current_schema_version: number;
  collection_bindings: DatasetCollectionBinding[];
  storage_policy: DatasetStoragePolicy | null;
}

export interface DatasetCategory {
  id: string;
  name: string;
  description: string | null;
  dataset_count: number;
  created_at: string;
  updated_at: string;
}

export interface DatasetField {
  name: string;
  data_type: string;
  nullable: boolean;
  description: string;
  unit: string | null;
  source_name: string | null;
  position: number;
}

export interface DatasetDetail extends DatasetSummary {
  dataset_name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  schema: {
    version: number;
    primary_key: string[];
    time_field: string | null;
    created_at: string;
    fields: DatasetField[];
  };
}

export interface DatasetCreatePayload {
  id: string;
  provider: string;
  region: string;
  instrument: string;
  dataset_name: string;
  market: string | null;
  display_name: string;
  description: string | null;
  update_frequency: UpdateFrequency;
  time_granularity: TimeGranularity;
  collection_bindings: DatasetCollectionBinding[];
  storage_policy: DatasetStoragePolicy | null;
  primary_key: string[];
  time_field: string | null;
  fields: Array<{
    name: string;
    data_type: string;
    nullable: boolean;
    description: string;
    unit: string | null;
    source_name: string | null;
  }>;
}

export interface DatasetPreset {
  key: string;
  category: string;
  contract: DatasetCreatePayload;
}

export type DatasetUpdatePayload = Pick<
  DatasetCreatePayload,
  | "display_name"
  | "description"
  | "update_frequency"
  | "time_granularity"
  | "collection_bindings"
  | "storage_policy"
  | "primary_key"
  | "time_field"
  | "fields"
>;

export type DatasetMetadataUpdatePayload = Pick<
  DatasetCreatePayload,
  "display_name" | "description" | "update_frequency" | "time_granularity"
>;

export interface CollectorParameter {
  name: string;
  data_type: string;
  required: boolean;
  description: string;
}

export interface CollectorOperation {
  key: string;
  name: string;
  description: string;
  purpose: CollectionPurpose;
  parameters: CollectorParameter[];
  datasets: string[];
  joint: boolean;
}

export interface DatasetCollectionBinding {
  purpose: CollectionPurpose;
  collector_key: string;
  operation: string;
  parameters: Record<string, unknown>;
}

export interface CollectorDefinition {
  key: string;
  name: string;
  description: string;
  operations: CollectorOperation[];
}

export interface CollectionJob {
  id: string;
  dataset_id: string;
  operation: CollectionOperation;
  input_method: CollectionInputMethod;
  status: CollectionJobStatus;
  start_date: string | null;
  end_date: string | null;
  collector_key: string | null;
  collector_operation: string | null;
  parameters: Record<string, unknown>;
  retry_of_job_id: string | null;
  source_file_name: string | null;
  staged_path: string | null;
  source_size_bytes: number | null;
  source_sha256: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CollectionJobCreatePayload {
  dataset_id: string;
  operation: CollectionOperation;
  input_method: CollectionInputMethod;
  start_date: string | null;
  end_date: string | null;
  collector_key: string | null;
  parameters: Record<string, unknown>;
}

export interface CollectionReadiness {
  dataset_id: string;
  initial_required: boolean;
}

export interface CollectionProgress {
  job_id: string;
  status: CollectionJobStatus;
  expected_total: number | null;
  succeeded: number;
  failed: number;
  processed: number;
  latest_partition: string | null;
  percent: number | null;
  started_at: string | null;
  finished_at: string | null;
  elapsed_seconds: number | null;
  eta_seconds: number | null;
  expected_finish_at: string | null;
  eta_basis: "running_rate" | "history" | "insufficient_data" | null;
}

export interface CollectionJobPage {
  items: CollectionJob[];
  total: number;
  limit: number;
  offset: number;
}

export interface CollectionRunPage {
  items: CollectionRun[];
  total: number;
  limit: number;
  offset: number;
}

export interface CollectionRun {
  id: string;
  partition_key: string;
  status: string;
  staged_path: string | null;
  published_path: string | null;
  row_count: number | null;
  error: string | null;
}

export interface CollectionLogEntry {
  timestamp: string;
  level: string;
  event: string;
  logger?: string;
  [key: string]: unknown;
}

export interface CollectionLogs {
  job_id: string;
  entries: CollectionLogEntry[];
}

export type MaintenanceJobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export interface CatalogPartitionItem {
  dataset_id: string;
  partition_key: string;
  file_path: string;
}

export interface AutoCompactionResult {
  jobs: MaintenanceJob[];
  skipped_years: number[];
  candidate_years: number[];
}

export interface MaintenanceJob {
  id: string;
  dataset_id: string;
  operation: string;
  parameters: Record<string, unknown>;
  status: MaintenanceJobStatus;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface CoverageDetail {
  row_count: number | null;
  file_path: string | null;
  error: string | null;
}

export interface CoverageDataset {
  dataset_id: string;
  display_name: string;
  cells: Record<string, string>;
  details: Record<string, CoverageDetail>;
  summary: Record<string, number>;
}

export interface CoverageResponse {
  today: string;
  dates: string[];
  datasets: CoverageDataset[];
}

export interface DailyCompletionRow {
  dataset_id: string;
  display_name: string;
  layout: "date" | "snapshot";
  latest_trade_date: string | null;
  latest_status: "complete" | "missing" | "failed" | "abnormal" | "pending" | "stale" | null;
  complete: number;
  expected: number;
  completion_percent: number | null;
  missing: number;
  failed: number;
  abnormal: number;
  pending: number;
  last_updated_at: string | null;
}

export interface DailyCompletion {
  today: string;
  days: number;
  dates: string[];
  datasets: DailyCompletionRow[];
}

export interface CollectionOverviewJob {
  id: string;
  dataset_id: string;
  display_name: string;
  operation: CollectionOperation;
  input_method: CollectionInputMethod;
  status: CollectionJobStatus;
  updated_at: string;
}

export interface CollectionOverview {
  total_jobs: number;
  queued: number;
  running: number;
  awaiting_file: number;
  staged: number;
  succeeded_24h: number;
  failed_24h: number;
  last_completed_at: string | null;
  recent_jobs: CollectionOverviewJob[];
}

export interface DatasetOverview {
  dataset_id: string;
  display_name: string;
  status: DatasetStatus;
  provider: string;
  region: string;
  instrument: string;
  market: string | null;
  layout: string | null;
  calendar_dataset_id: string | null;
  partitions: number;
  files: number;
  rows: number;
  size_bytes: number;
  first_partition: string | null;
  latest_partition: string | null;
  published_at: string | null;
  missing_files: number;
  expected_partitions: number | null;
  coverage_percent: number | null;
}

export interface DatasetDeletionReview {
  dataset_ids: string[];
  items: Array<{
    dataset_id: string;
    display_name: string;
    status: DatasetStatus;
    collection_jobs: number;
    collection_runs: number;
    maintenance_jobs: number;
    catalog_files: number;
    catalog_partitions: number;
    rows: number;
    physical_files: number;
    physical_bytes: number;
  }>;
  blockers: string[];
  confirmation_text: string;
  review_token: string;
  can_delete: boolean;
}

export interface CollectionReview {
  reviewer: string;
  passed: boolean;
  row_count: number;
  error_count: number;
  errors?: Array<Record<string, unknown>>;
  runs?: Array<{
    reviewer: string;
    passed: boolean;
    row_count: number;
    error_count: number;
    errors: Array<Record<string, unknown>>;
    partition_key?: string;
  }>;
}

export interface DatasetRows {
  dataset_id: string;
  files_read: number;
  row_count: number;
  matched_count: number | null;
  truncated: boolean;
  filtered: boolean;
  columns: string[];
  rows: Array<Record<string, unknown>>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg).join("；")
      : detail || `请求失败（${response.status}）`;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  listDatasets: () => request<DatasetSummary[]>("/api/v1/datasets"),
  listDatasetCategories: () => request<DatasetCategory[]>("/api/v1/dataset-categories"),
  createDatasetCategory: (payload: { name: string; description: string | null }) =>
    request<DatasetCategory>("/api/v1/dataset-categories", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateDatasetCategory: (id: string, payload: { name: string; description: string | null }) =>
    request<DatasetCategory>(`/api/v1/dataset-categories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  deleteDatasetCategory: (id: string) =>
    request<void>(`/api/v1/dataset-categories/${id}`, { method: "DELETE" }),
  assignDatasetCategory: (datasetId: string, categoryId: string | null) =>
    request<DatasetDetail>(`/api/v1/datasets/${datasetId}/category`, {
      method: "PUT",
      body: JSON.stringify({ category_id: categoryId }),
    }),
  listDatasetPresets: () => request<DatasetPreset[]>("/api/v1/dataset-presets"),
  listCollectors: () => request<CollectorDefinition[]>("/api/v1/collectors"),
  getDataset: (id: string) => request<DatasetDetail>(`/api/v1/datasets/${id}`),
  createDataset: (payload: DatasetCreatePayload) =>
    request<DatasetDetail>("/api/v1/datasets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateDataset: (id: string, payload: DatasetUpdatePayload) =>
    request<DatasetDetail>(`/api/v1/datasets/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  updateDatasetMetadata: (id: string, payload: DatasetMetadataUpdatePayload) =>
    request<DatasetDetail>(`/api/v1/datasets/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  activateDataset: (id: string) =>
    request<DatasetDetail>(`/api/v1/datasets/${id}/activate`, { method: "POST" }),
  reviewDatasetDeletion: (datasetIds: string[]) =>
    request<DatasetDeletionReview>("/api/v1/datasets/deletion-review", {
      method: "POST",
      body: JSON.stringify({ dataset_ids: datasetIds }),
    }),
  deleteDatasets: (datasetIds: string[], reviewToken: string, confirmation: string) =>
    request<{ deleted_dataset_ids: string[] }>("/api/v1/datasets/batch-delete", {
      method: "POST",
      body: JSON.stringify({ dataset_ids: datasetIds, review_token: reviewToken, confirmation }),
    }),
  listCollectionJobs: (params: { limit?: number; offset?: number; status?: string; datasetId?: string } = {}) => {
    const query = new URLSearchParams();
    if (params.limit !== undefined) query.set("limit", String(params.limit));
    if (params.offset !== undefined) query.set("offset", String(params.offset));
    if (params.status) query.set("status", params.status);
    if (params.datasetId) query.set("dataset_id", params.datasetId);
    const suffix = query.toString();
    return request<CollectionJobPage>(`/api/v1/collection-jobs${suffix ? `?${suffix}` : ""}`);
  },
  getCollectionReadiness: (datasetId: string) =>
    request<CollectionReadiness>(`/api/v1/collection-jobs/readiness/${encodeURIComponent(datasetId)}`),
  createCollectionJob: (payload: CollectionJobCreatePayload) =>
    request<CollectionJob>("/api/v1/collection-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  executeCollectionJob: (jobId: string) =>
    request<CollectionJob>(`/api/v1/collection-jobs/${jobId}/execute`, { method: "POST" }),
  retryCollectionJob: (jobId: string) =>
    request<CollectionJob>(`/api/v1/collection-jobs/${jobId}/retry`, { method: "POST" }),
  cancelCollectionJob: (jobId: string) =>
    request<CollectionJob>(`/api/v1/collection-jobs/${jobId}/cancel`, { method: "POST" }),
  deleteCollectionJob: (jobId: string) =>
    request<void>(`/api/v1/collection-jobs/${jobId}`, { method: "DELETE" }),
  getCollectionProgress: (jobId: string) =>
    request<CollectionProgress>(`/api/v1/collection-jobs/${jobId}/progress`),
  listCollectionRuns: (jobId: string, limit = 100, offset = 0) =>
    request<CollectionRunPage>(
      `/api/v1/collection-jobs/${jobId}/runs?limit=${limit}&offset=${offset}`,
    ),
  listCollectionLogs: (jobId: string, limit = 500, minLevel?: string) =>
    request<CollectionLogs>(
      `/api/v1/collection-jobs/${jobId}/logs?limit=${limit}${minLevel ? `&min_level=${encodeURIComponent(minLevel)}` : ""}`,
    ),
  getCollectionReview: (jobId: string) =>
    request<CollectionReview>(`/api/v1/collection-jobs/${jobId}/review`),
  listMaintenanceJobs: (datasetId?: string) => {
    const query = datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
    return request<MaintenanceJob[]>(`/api/v1/maintenance-jobs${query}`);
  },
  createCompactionJob: (datasetId: string, year: number) =>
    request<MaintenanceJob>(`/api/v1/datasets/${encodeURIComponent(datasetId)}/compact?year=${year}`, { method: "POST" }),
  compactAllYears: (datasetId: string) =>
    request<AutoCompactionResult>(`/api/v1/datasets/${encodeURIComponent(datasetId)}/compact-all`, { method: "POST" }),
  listCatalogPartitions: (datasetId: string) =>
    request<CatalogPartitionItem[]>(`/api/v1/catalog/partitions?dataset_id=${encodeURIComponent(datasetId)}`),
  cancelMaintenanceJob: (jobId: string) =>
    request<MaintenanceJob>(`/api/v1/maintenance-jobs/${jobId}/cancel`, { method: "POST" }),
  getDatasetOverview: () => request<DatasetOverview[]>("/api/v1/overview/datasets"),
  getCollectionOverview: () => request<CollectionOverview>("/api/v1/overview/collection"),
  getDailyCompletion: (days = 30) =>
    request<DailyCompletion>(`/api/v1/overview/daily-completion?days=${days}`),
  getCoverage: (days: number) =>
    request<CoverageResponse>(`/api/v1/overview/coverage?days=${days}`),
  readDatasetRows: (datasetId: string, filters: Record<string, string> = {}, limit = 20) => {
    const query = new URLSearchParams({ limit: String(limit) });
    Object.entries(filters).forEach(([key, value]) => {
      if (value.trim()) query.set(key, value.trim());
    });
    return request<DatasetRows>(`/api/v1/datasets/${encodeURIComponent(datasetId)}/rows?${query}`);
  },
  downloadDatasetRows: async (datasetId: string, filters: Record<string, string>, format: "csv" | "parquet") => {
    const query = new URLSearchParams({ format });
    Object.entries(filters).forEach(([key, value]) => {
      if (value.trim()) query.set(key, value.trim());
    });
    const response = await fetch(`/api/v1/datasets/${encodeURIComponent(datasetId)}/download?${query}`);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `下载失败（${response.status}）`);
    }
    const disposition = response.headers.get("Content-Disposition") ?? "";
    const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
    const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1];
    const filename = encodedName ? decodeURIComponent(encodedName) : plainName || `${datasetId}.${format}`;
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
    return Number(response.headers.get("X-Row-Count") ?? 0);
  },
  uploadCollectionFile: async (jobId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch(`/api/v1/collection-jobs/${jobId}/file`, {
      method: "POST",
      body: form,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.detail || `文件上传失败（${response.status}）`);
    }
    return response.json() as Promise<CollectionJob>;
  },
};
