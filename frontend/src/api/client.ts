import { getStoredToken, clearStoredToken } from "../lib/token";

export interface RequestOptions extends Omit<RequestInit, "body"> {
  params?: Record<string, string | number | boolean | undefined | null>;
  body?: any;
  requiresAuth?: boolean;
}

export class ApiClientError extends Error {
  public status: number;
  public code?: string;
  public details?: any;

  constructor(message: string, status: number, code?: string, details?: any) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

class ApiClient {
  private baseUrl: string;
  private onUnauthorizedCallback: (() => void) | null = null;

  constructor() {
    this.baseUrl = (
      import.meta.env.VITE_API_BASE_URL ||
      import.meta.env.VITE_API_URL ||
      "/api/v1"
    ).replace(/\/$/, "");
  }

  public setOnUnauthorized(callback: () => void) {
    this.onUnauthorizedCallback = callback;
  }

  private buildUrl(endpoint: string, params?: Record<string, string | number | boolean | undefined | null>): string {
    const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
    const url = new URL(`${this.baseUrl}${cleanEndpoint}`, window.location.origin);

    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    return url.toString();
  }

  public async request<T = any>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { params, body, headers = {}, requiresAuth = true, ...customConfig } = options;

    const token = getStoredToken();
    const requestHeaders: Record<string, string> = {
      Accept: "application/json",
      ...(headers as Record<string, string>),
    };

    if (requiresAuth && token) {
      requestHeaders["Authorization"] = `Bearer ${token}`;
    }

    let requestBody: any = undefined;
    if (body !== undefined) {
      if (body instanceof FormData) {
        requestBody = body;
      } else {
        requestHeaders["Content-Type"] = "application/json";
        requestBody = JSON.stringify(body);
      }
    }

    const config: RequestInit = {
      ...customConfig,
      headers: requestHeaders,
      body: requestBody,
    };

    const url = this.buildUrl(endpoint, params);

    try {
      const response = await fetch(url, config);

      if (response.status === 204) {
        return null as unknown as T;
      }

      let responseData: any;
      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        responseData = await response.json();
      } else {
        responseData = await response.text();
      }

      if (!response.ok) {
        if (response.status === 401) {
          clearStoredToken();
          if (this.onUnauthorizedCallback) {
            this.onUnauthorizedCallback();
          }
        }

        const errorMessage = this.extractErrorMessage(response.status, responseData);
        throw new ApiClientError(
          errorMessage,
          response.status,
          responseData?.code || responseData?.error_code,
          responseData?.detail || responseData?.details
        );
      }

      return responseData as T;
    } catch (error: any) {
      if (error instanceof ApiClientError) {
        throw error;
      }

      // Network or connection failure
      throw new ApiClientError(
        error.message || "Network connection error. Please verify backend connectivity.",
        0,
        "NETWORK_ERROR"
      );
    }
  }

  private extractErrorMessage(status: number, data: any): string {
    if (typeof data === "string" && data.trim()) {
      return data;
    }

    if (data && typeof data === "object") {
      if (typeof data.message === "string" && data.message.trim()) {
        return data.message;
      }
      if (typeof data.detail === "string" && data.detail.trim()) {
        return data.detail;
      }
      if (Array.isArray(data.detail) && data.detail.length > 0) {
        // FastAPI / Pydantic validation error format
        const firstErr = data.detail[0];
        const field = firstErr?.loc ? firstErr.loc.filter((l: string) => l !== "body").join(".") : "";
        return field ? `${field}: ${firstErr.msg}` : firstErr.msg || "Validation error.";
      }
    }

    switch (status) {
      case 400:
        return "Bad Request: The submission data is invalid.";
      case 401:
        return "Authentication required: Invalid or expired credentials.";
      case 403:
        return "Access Forbidden: You do not have permission to perform this action.";
      case 404:
        return "Resource Not Found: The requested entity does not exist.";
      case 409:
        return "Conflict: A resource with these details already exists.";
      case 422:
        return "Unprocessable Entity: Validation failed on request parameters.";
      case 429:
        return "Too Many Requests: Rate limit exceeded. Please wait a moment.";
      case 502:
        return "Bad Gateway: Downstream service or n8n Orchestrator is unreachable.";
      case 504:
        return "Gateway Timeout: Downstream verification service timed out.";
      default:
        return `Server Error (${status}): Please try again later.`;
    }
  }

  public get<T = any>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  public post<T = any>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "POST", body });
  }

  public put<T = any>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "PUT", body });
  }

  public patch<T = any>(endpoint: string, body?: any, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "PATCH", body });
  }

  public delete<T = any>(endpoint: string, options?: RequestOptions): Promise<T> {
    return this.request<T>(endpoint, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
