import { apiClient } from "./client";
import { GeMLookupResponse, TenderResponse } from "../types";

/**
 * Looks up a GeM Bid ID via GET /api/v1/gem/lookup/{bid_id}
 */
export async function lookupGemTender(bidId: string): Promise<GeMLookupResponse> {
  const cleanId = encodeURIComponent(bidId.trim());
  return apiClient.get<GeMLookupResponse>(`/gem/lookup/${cleanId}`);
}

/**
 * Imports a GeM tender into persistent PostgreSQL database via POST /api/v1/gem/import
 */
export async function importGemTender(formData: FormData): Promise<TenderResponse> {
  return apiClient.post<TenderResponse>("/gem/import", formData);
}
