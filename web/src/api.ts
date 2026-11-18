export type DatasetStatus = "draft" | "active" | "paused" | "deprecated";
export type CollectionOperation = "initial" | "incremental" | "repair" | "replace";
export type CollectionPurpose = CollectionOperation;
export type CollectionInputMethod = "collector" | "file_import";
export type CollectionJobStatus =
  | "created"
  | "awaiting_file"
  | "staged"
  | "review_passed"
  | "review_failed"
  | "succeeded"
  | "failed";

export interface DatasetStoragePolicy {
  logical_partition_field: string | null;
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
  status: DatasetStatus;
  current_schema_version: number;
  collection_bindings: DatasetCollectionBinding[];
  storage_policy: DatasetStoragePolicy | null;
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

export type DatasetUpdatePayload = Pick<
  DatasetCreatePayload,
  | "display_name"
  | "description"
  | "collection_bindings"
  | "storage_policy"
  | "primary_key"
  | "time_field"
  | "fields"
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
  source_file_name: string | null;
  staged_path: string | null;
  source_size_bytes: number | null;
  source_sha256: string | null;
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
}

export interface CollectionReview {
  reviewer: string;
  passed: boolean;
  row_count: number;
  error_count: number;
  errors: Array<Record<string, unknown>>;
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
  activateDataset: (id: string) =>
    request<DatasetDetail>(`/api/v1/datasets/${id}/activate`, { method: "POST" }),
  deleteDataset: (id: string) =>
    request<void>(`/api/v1/datasets/${id}`, { method: "DELETE" }),
  listCollectionJobs: () => request<CollectionJob[]>("/api/v1/collection-jobs"),
  createCollectionJob: (payload: CollectionJobCreatePayload) =>
    request<CollectionJob>("/api/v1/collection-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  executeCollectionJob: (jobId: string) =>
    request<CollectionJob>(`/api/v1/collection-jobs/${jobId}/execute`, { method: "POST" }),
  getCollectionReview: (jobId: string) =>
    request<CollectionReview>(`/api/v1/collection-jobs/${jobId}/review`),
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
