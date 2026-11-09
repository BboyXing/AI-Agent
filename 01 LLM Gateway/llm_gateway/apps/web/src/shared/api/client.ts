import type {
  CallDetail,
  CallPage,
  ModelListResponse,
  UsageSummary,
} from "./types";

export class GatewayApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly requestId?: string;

  constructor(
    message: string,
    options: { status: number; code?: string; requestId?: string },
  ) {
    super(message);
    this.name = "GatewayApiError";
    this.status = options.status;
    this.code = options.code;
    this.requestId = options.requestId;
  }
}

export async function apiRequest<T>(
  path: string,
  apiKey: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${apiKey}`,
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw await responseToError(response);
  }
  return (await response.json()) as T;
}

export async function responseToError(response: Response): Promise<GatewayApiError> {
  let message = `请求失败（HTTP ${response.status}）`;
  let code: string | undefined;
  let requestId = response.headers.get("x-request-id") ?? undefined;
  try {
    const payload = (await response.json()) as {
      error?: {
        message?: string;
        code?: string;
        request_id?: string;
      };
    };
    message = payload.error?.message ?? message;
    code = payload.error?.code;
    requestId = payload.error?.request_id ?? requestId;
  } catch {
    // Keep the HTTP fallback when an upstream or proxy returns non-JSON.
  }
  return new GatewayApiError(message, {
    status: response.status,
    code,
    requestId,
  });
}

export function fetchModels(apiKey: string, signal?: AbortSignal) {
  return apiRequest<ModelListResponse>("/api/v1/models", apiKey, { signal });
}

export function fetchUsageSummary(
  apiKey: string,
  filters: { from: string; to: string },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams(filters);
  return apiRequest<UsageSummary>(
    `/api/v1/usage/summary?${query.toString()}`,
    apiKey,
    { signal },
  );
}

export function fetchCalls(
  apiKey: string,
  filters: {
    from: string;
    to: string;
    limit: number;
    offset: number;
  },
  signal?: AbortSignal,
) {
  const query = new URLSearchParams(
    Object.fromEntries(
      Object.entries(filters).map(([key, value]) => [key, String(value)]),
    ),
  );
  return apiRequest<CallPage>(`/api/v1/usage/calls?${query.toString()}`, apiKey, {
    signal,
  });
}

export function fetchCallDetail(
  apiKey: string,
  requestId: string,
  signal?: AbortSignal,
) {
  return apiRequest<CallDetail>(
    `/api/v1/usage/calls/${encodeURIComponent(requestId)}`,
    apiKey,
    { signal },
  );
}
