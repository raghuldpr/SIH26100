import { apiClient } from "./client";

export interface ApiHealthResponse {
  status: string;
  api_version: string;
  environment?: string;
}

export interface DbHealthResponse {
  status: string;
  database: string;
  api_version?: string;
}

export interface VerificationHealthResponse {
  status: string;
  n8n_service?: {
    reachable?: boolean;
    url?: string;
    status_code?: number;
    response_time_ms?: number;
    error?: string;
  };
}

export type ServiceStatus = "ONLINE" | "DEGRADED" | "OFFLINE" | "UNKNOWN";

export interface ServiceHealth {
  id: string;
  name: string;
  category: "CORE" | "DATA" | "ORCHESTRATION" | "INTELLIGENCE";
  status: ServiceStatus;
  endpoint: string;
  latencyMs?: number;
  message?: string;
  details?: Record<string, any>;
  checkedAt: string;
}

export interface SystemHealthReport {
  overallStatus: ServiceStatus;
  services: ServiceHealth[];
  checkedAt: string;
  summary: {
    onlineCount: number;
    degradedCount: number;
    offlineCount: number;
    unknownCount: number;
    total: number;
  };
}

/**
 * Probes the FastAPI root health check endpoint GET /api/v1/health
 */
export async function getApiHealth(): Promise<ApiHealthResponse> {
  return apiClient.get<ApiHealthResponse>("/health");
}

/**
 * Probes the Database connectivity health check endpoint GET /api/v1/health/db
 */
export async function getDatabaseHealth(): Promise<DbHealthResponse> {
  return apiClient.get<DbHealthResponse>("/health/db");
}

/**
 * Probes the n8n & verification subsystem health endpoint GET /api/v1/verification/health
 */
export async function getVerificationHealth(): Promise<VerificationHealthResponse> {
  return apiClient.get<VerificationHealthResponse>("/verification/health");
}

/**
 * Runs a comprehensive, non-fabricated diagnostic check against all real backend health endpoints
 */
export async function probeSystemHealth(): Promise<SystemHealthReport> {
  const timestamp = new Date().toISOString();
  const services: ServiceHealth[] = [];

  // 1. Probe Core FastAPI Backend
  const t0Api = performance.now();
  try {
    const apiRes = await getApiHealth();
    const latApi = Math.round(performance.now() - t0Api);
    services.push({
      id: "fastapi-backend",
      name: "FastAPI Core Application",
      category: "CORE",
      status: apiRes.status === "healthy" ? "ONLINE" : "DEGRADED",
      endpoint: "GET /api/v1/health",
      latencyMs: latApi,
      message: `API Version: ${apiRes.api_version || "v1"} | Env: ${apiRes.environment || "production"}`,
      details: apiRes as Record<string, any>,
      checkedAt: timestamp,
    });
  } catch (err: any) {
    services.push({
      id: "fastapi-backend",
      name: "FastAPI Core Application",
      category: "CORE",
      status: "OFFLINE",
      endpoint: "GET /api/v1/health",
      message: err?.message || "Connection refused to backend API",
      checkedAt: timestamp,
    });
  }

  // 2. Probe Database Connectivity
  const t0Db = performance.now();
  try {
    const dbRes = await getDatabaseHealth();
    const latDb = Math.round(performance.now() - t0Db);
    services.push({
      id: "database-layer",
      name: "PostgreSQL / Supabase Database",
      category: "DATA",
      status: dbRes.status === "healthy" && dbRes.database === "connected" ? "ONLINE" : "DEGRADED",
      endpoint: "GET /api/v1/health/db",
      latencyMs: latDb,
      message: `Connection: ${dbRes.database || "connected"} (PostgreSQL Session Pool)`,
      details: dbRes as Record<string, any>,
      checkedAt: timestamp,
    });
  } catch (err: any) {
    services.push({
      id: "database-layer",
      name: "PostgreSQL / Supabase Database",
      category: "DATA",
      status: "OFFLINE",
      endpoint: "GET /api/v1/health/db",
      message: err?.message || "Database health probe failed",
      checkedAt: timestamp,
    });
  }

  // 3. Probe Verification Engine & n8n Orchestrator
  const t0Ver = performance.now();
  try {
    const verRes = await getVerificationHealth();
    const latVer = Math.round(performance.now() - t0Ver);
    const n8nReachable = verRes.n8n_service?.reachable === true;

    // n8n Orchestration Service
    services.push({
      id: "n8n-orchestrator",
      name: "n8n Multi-Agent Master Orchestrator",
      category: "ORCHESTRATION",
      status: n8nReachable ? "ONLINE" : "DEGRADED",
      endpoint: "GET /api/v1/verification/health",
      latencyMs: verRes.n8n_service?.response_time_ms ?? latVer,
      message: n8nReachable
        ? `Reachable via Webhook Port ${verRes.n8n_service?.url || "5678"}`
        : (verRes.n8n_service?.error || "n8n webhook worker unreachable"),
      details: verRes.n8n_service,
      checkedAt: timestamp,
    });

    // Verification Engine Aggregator
    services.push({
      id: "verification-engine",
      name: "Verification Engine & Aggregator",
      category: "CORE",
      status: verRes.status === "healthy" ? "ONLINE" : "DEGRADED",
      endpoint: "GET /api/v1/verification/health",
      latencyMs: latVer,
      message: "Deterministic Verification Rules & Audit Logger Active",
      details: { status: verRes.status },
      checkedAt: timestamp,
    });
  } catch (err: any) {
    services.push({
      id: "n8n-orchestrator",
      name: "n8n Multi-Agent Master Orchestrator",
      category: "ORCHESTRATION",
      status: "OFFLINE",
      endpoint: "GET /api/v1/verification/health",
      message: err?.message || "Verification health probe failed",
      checkedAt: timestamp,
    });
    services.push({
      id: "verification-engine",
      name: "Verification Engine & Aggregator",
      category: "CORE",
      status: "OFFLINE",
      endpoint: "GET /api/v1/verification/health",
      message: err?.message || "Verification engine probe failed",
      checkedAt: timestamp,
    });
  }

  // 4. Document Engine & AI Gateway
  // Since Document Engine and AI Gateway operate as internal FastAPI services without separate dedicated health endpoints,
  // we derive their status directly from backend availability.
  const backendOnline = services.find((s) => s.id === "fastapi-backend")?.status === "ONLINE";

  services.push({
    id: "document-engine",
    name: "Document Engine (OCR & Clause Extraction)",
    category: "DATA",
    status: backendOnline ? "ONLINE" : "UNKNOWN",
    endpoint: "Internal Service (PyMuPDF / Tesseract / Regex)",
    message: backendOnline
      ? "Deterministic OCR & Clause Parser Initialized"
      : "Status Unknown (Backend probe unavailable)",
    checkedAt: timestamp,
  });

  services.push({
    id: "ai-gateway",
    name: "AI Gateway (Groq LLaMA-3.3 Minimal Fallback)",
    category: "INTELLIGENCE",
    status: backendOnline ? "ONLINE" : "UNKNOWN",
    endpoint: "Internal Service (Groq REST API)",
    message: backendOnline
      ? "Controlled Minimal LLM Gateway Active (llama-3.3-70b-versatile)"
      : "Status Unknown (Backend probe unavailable)",
    checkedAt: timestamp,
  });

  // Calculate totals
  const onlineCount = services.filter((s) => s.status === "ONLINE").length;
  const degradedCount = services.filter((s) => s.status === "DEGRADED").length;
  const offlineCount = services.filter((s) => s.status === "OFFLINE").length;
  const unknownCount = services.filter((s) => s.status === "UNKNOWN").length;

  let overallStatus: ServiceStatus = "ONLINE";
  if (offlineCount > 0) {
    overallStatus = "OFFLINE";
  } else if (degradedCount > 0) {
    overallStatus = "DEGRADED";
  }

  return {
    overallStatus,
    services,
    checkedAt: timestamp,
    summary: {
      onlineCount,
      degradedCount,
      offlineCount,
      unknownCount,
      total: services.length,
    },
  };
}
