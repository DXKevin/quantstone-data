export type DatasetStatus = "draft" | "active" | "paused" | "deprecated";

export interface DatasetSummary {
  id: string;
  display_name: string;
  provider: string;
  region: string;
  instrument: string;
  market: string | null;
  status: DatasetStatus;
  current_schema_version: number;
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
  "display_name" | "description" | "primary_key" | "time_field" | "fields"
>;

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
};
