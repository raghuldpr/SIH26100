import { apiClient } from "./client";
import {
  DocumentResponse,
  TenderComplianceProfileResponse,
  TenderCreate,
  TenderRequirementResponse,
  TenderResponse,
  TenderStatus,
  TenderUpdate,
} from "../types";

export type { TenderResponse };

export interface PaginatedTendersResponse {
  success?: boolean;
  data?: TenderResponse[];
  items?: TenderResponse[];
  page: number;
  page_size: number;
  total: number;
  pagination?: {
    total_count: number;
    page: number;
    page_size: number;
    total_pages: number;
  };
}

export interface ListTendersParams {
  page?: number;
  page_size?: number;
  status?: TenderStatus;
  department?: string;
  category?: string;
  search?: string;
  my_tenders_only?: boolean;
  include_archived?: boolean;
}

export interface TenderBidderItem {
  id: string;
  bidder_id: string;
  company_name: string;
  registration_number?: string;
  gst_number?: string;
  pan_number?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  status?: string;
  assignment_timestamp?: string;
}

/**
 * Lists tenders with pagination and filtering from GET /api/v1/tenders
 */
export async function listTenders(params: ListTendersParams = {}): Promise<PaginatedTendersResponse> {
  return apiClient.get<PaginatedTendersResponse>("/tenders", {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 10,
      status: params.status,
      department: params.department,
      category: params.category,
      search: params.search,
      my_tenders_only: params.my_tenders_only ?? false,
      include_archived: params.include_archived ?? false,
    },
  });
}

/**
 * Fetches a single tender by ID from GET /api/v1/tenders/{id}
 */
export async function getTender(tenderId: string): Promise<TenderResponse> {
  return apiClient.get<TenderResponse>(`/tenders/${tenderId}`);
}

/**
 * Creates a new procurement tender via POST /api/v1/tenders
 */
export async function createTender(tenderIn: TenderCreate): Promise<TenderResponse> {
  return apiClient.post<TenderResponse>("/tenders", tenderIn);
}

/**
 * Updates an existing tender via PUT /api/v1/tenders/{id}
 */
export async function updateTender(tenderId: string, tenderIn: TenderUpdate): Promise<TenderResponse> {
  return apiClient.put<TenderResponse>(`/tenders/${tenderId}`, tenderIn);
}

/**
 * Partially updates an existing tender via PATCH /api/v1/tenders/{id}
 */
export async function patchTender(tenderId: string, tenderIn: TenderUpdate): Promise<TenderResponse> {
  return apiClient.patch<TenderResponse>(`/tenders/${tenderId}`, tenderIn);
}

/**
 * Archives / deletes a tender via DELETE /api/v1/tenders/{id}
 */
export async function deleteTender(tenderId: string): Promise<{ success: boolean; message: string }> {
  return apiClient.delete<{ success: boolean; message: string }>(`/tenders/${tenderId}`);
}

/**
 * Uploads a tender document (NIT, RFP, Specs) via POST /api/v1/tenders/{id}/documents
 */
export async function uploadTenderDocument(
  tenderId: string,
  file: File,
  documentType: string = "TENDER_NOTICE"
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);

  return apiClient.post<DocumentResponse>(`/tenders/${tenderId}/documents`, formData);
}

/**
 * Lists all documents attached to a tender via GET /api/v1/tenders/{id}/documents
 */
export async function listTenderDocuments(tenderId: string): Promise<DocumentResponse[]> {
  const response = await apiClient.get<any>(`/tenders/${tenderId}/documents`);
  if (Array.isArray(response)) return response;
  return response?.data || response?.items || [];
}

/**
 * Triggers Phase 11 Tender Intelligence analysis on tender documents via POST /api/v1/tenders/{id}/intelligence/analyze
 */
export async function analyzeTender(
  tenderId: string,
  forceReanalyze: boolean = false
): Promise<TenderComplianceProfileResponse> {
  try {
    return await apiClient.post<TenderComplianceProfileResponse>(`/tenders/${tenderId}/intelligence/analyze`, {
      force_reanalyze: forceReanalyze,
    });
  } catch {
    // Graceful fallback if route is mapped to direct /analyze
    return await apiClient.post<TenderComplianceProfileResponse>(`/tenders/${tenderId}/analyze`, {
      force_reanalyze: forceReanalyze,
    });
  }
}

/**
 * Retrieves the existing Tender Intelligence Compliance Profile via GET /api/v1/tenders/{id}/intelligence
 */
export async function getTenderIntelligenceProfile(tenderId: string): Promise<TenderComplianceProfileResponse> {
  return apiClient.get<TenderComplianceProfileResponse>(`/tenders/${tenderId}/intelligence`);
}

/**
 * Lists extracted compliance requirements for a tender via GET /api/v1/tenders/{id}/requirements
 */
export async function listTenderRequirements(tenderId: string): Promise<TenderRequirementResponse[]> {
  const response = await apiClient.get<any>(`/tenders/${tenderId}/requirements`);
  if (Array.isArray(response)) return response;
  return response?.data || response?.items || [];
}

/**
 * Lists participating bidders for a tender via GET /api/v1/tenders/{id}/bidders
 */
export async function listTenderBidders(tenderId: string): Promise<TenderBidderItem[]> {
  const response = await apiClient.get<any>(`/tenders/${tenderId}/bidders`);
  if (Array.isArray(response)) return response;
  return response?.data || response?.items || [];
}
