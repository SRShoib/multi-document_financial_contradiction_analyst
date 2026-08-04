import type {
  DecisionRequest,
  RunStatus,
  StartRequest,
  UploadResponse,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

/** True for "the server is unreachable" — as opposed to a real HTTP error response. */
export function isNetworkError(err: unknown): err is TypeError {
  return err instanceof TypeError;
}

async function send(path: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new TypeError(
      `Could not reach the analysis engine at ${API_BASE_URL}. Is the FastAPI server running?`,
    );
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // no JSON body; keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return unwrap<T>(
    await send(path, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(init?.headers ?? {}),
      },
    }),
  );
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  samples: () => request<{ samples: string[] }>("/samples"),

  startRun: (body: StartRequest) =>
    request<RunStatus>("/runs", { method: "POST", body: JSON.stringify(body) }),

  getRun: (runId: string) => request<RunStatus>(`/runs/${encodeURIComponent(runId)}`),

  getPending: (runId: string) =>
    request<{ run_id: string; pending: unknown[] }>(
      `/runs/${encodeURIComponent(runId)}/pending`,
    ),

  decide: (runId: string, body: DecisionRequest) =>
    request<RunStatus>(`/runs/${encodeURIComponent(runId)}/decision`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  uploadDocuments: async (files: File[]): Promise<UploadResponse> => {
    const form = new FormData();
    for (const file of files) form.append("files", file);
    // No content-type header here: the browser must set its own
    // multipart/form-data boundary. Setting one manually breaks the request.
    return unwrap<UploadResponse>(await send("/documents", { method: "POST", body: form }));
  },
};
