const base = "";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${base}${path}`, {
    credentials: "include",
    headers: { "content-type": "application/json", ...(init.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}`);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type WorkflowDefinition = {
  nodes: unknown[];
  edges: unknown[];
};

export type Workflow = {
  id: string;
  name: string;
  description: string | null;
  definition: WorkflowDefinition;
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type WorkflowCreate = {
  name: string;
  description?: string | null;
  definition: WorkflowDefinition;
};

export type WorkflowUpdate = Partial<WorkflowCreate>;

export const api = {
  login: (username: string, password: string) =>
    request<{ user_id: string; email: string; role: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<{ user_id: string; email: string; role: string }>("/auth/me"),

  listWorkflows: () => request<Workflow[]>("/api/workflows"),
  getWorkflow: (id: string) => request<Workflow>(`/api/workflows/${id}`),
  createWorkflow: (body: WorkflowCreate) =>
    request<Workflow>("/api/workflows", { method: "POST", body: JSON.stringify(body) }),
  updateWorkflow: (id: string, body: WorkflowUpdate) =>
    request<Workflow>(`/api/workflows/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteWorkflow: (id: string) => request<void>(`/api/workflows/${id}`, { method: "DELETE" }),
};
