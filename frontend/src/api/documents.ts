import { apiClient } from "./client";
import { DocumentResponse, StandardResponse } from "../types";

/**
 * Retrieves document metadata and pre-signed download URL via GET /api/v1/documents/{id}
 */
export async function getDocument(documentId: string): Promise<DocumentResponse> {
  return apiClient.get<DocumentResponse>(`/documents/${documentId}`);
}

/**
 * Triggers document OCR and structured entity extraction via POST /api/v1/documents/{id}/process
 */
export async function processDocument(documentId: string): Promise<DocumentResponse> {
  return apiClient.post<DocumentResponse>(`/documents/${documentId}/process`);
}

/**
 * Retries failed document processing via POST /api/v1/documents/{id}/retry
 */
export async function retryDocument(documentId: string): Promise<DocumentResponse> {
  return apiClient.post<DocumentResponse>(`/documents/${documentId}/retry`);
}

/**
 * Permanently deletes a document from storage and database via DELETE /api/v1/documents/{id}
 */
export async function deleteDocument(documentId: string): Promise<StandardResponse<{ document_id: string }>> {
  return apiClient.delete<StandardResponse<{ document_id: string }>>(`/documents/${documentId}`);
}
