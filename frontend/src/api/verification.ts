import { apiClient } from "./client";
import {
  N8nVerificationPayload,
  VerificationAuditEventResponse,
  VerificationHistoryItem,
  VerificationResponse,
  VerificationTriggerRequest,
} from "../types";

/**
 * Triggers full multi-agent bid verification workflow via POST /api/v1/verification/run
 */
export async function runVerification(
  request: VerificationTriggerRequest
): Promise<VerificationResponse> {
  return apiClient.post<VerificationResponse>("/verification/run", request);
}

/**
 * Triggers multi-agent bid verification workflow via POST /api/v1/verification/trigger
 */
export async function triggerVerification(
  request: VerificationTriggerRequest
): Promise<VerificationResponse> {
  return apiClient.post<VerificationResponse>("/verification/trigger", request);
}

/**
 * Validates and previews the constructed n8n verification payload via POST /api/v1/verification/build-request
 */
export async function buildVerificationRequest(
  request: VerificationTriggerRequest
): Promise<N8nVerificationPayload> {
  return apiClient.post<N8nVerificationPayload>("/verification/build-request", request);
}

/**
 * Fetches a finalized verification result by verification ID via GET /api/v1/verification/{id}
 */
export async function getVerification(verificationId: string): Promise<VerificationResponse> {
  return apiClient.get<VerificationResponse>(`/verification/${verificationId}`);
}

/**
 * Retrieves chronological verification history for a tender & bidder pair via GET /api/v1/verification/tender/{tenderId}/bidder/{bidderId}
 */
export async function getVerificationHistory(
  tenderId: string,
  bidderId: string
): Promise<VerificationHistoryItem[]> {
  const response = await apiClient.get<VerificationHistoryItem[]>(
    `/verification/tender/${tenderId}/bidder/${bidderId}`
  );
  return Array.isArray(response) ? response : [];
}

/**
 * Retrieves the immutable audit lifecycle trail for a verification ID via GET /api/v1/verification/{id}/audit
 */
export async function getVerificationAudit(
  verificationId: string
): Promise<VerificationAuditEventResponse[]> {
  const response = await apiClient.get<VerificationAuditEventResponse[]>(
    `/verification/${verificationId}/audit`
  );
  return Array.isArray(response) ? response : [];
}

/**
 * Checks verification subsystem & n8n orchestration health via GET /api/v1/verification/health
 */
export async function checkVerificationHealth(): Promise<{
  status: string;
  n8n_service?: Record<string, any>;
}> {
  return apiClient.get<{ status: string; n8n_service?: Record<string, any> }>("/verification/health");
}
