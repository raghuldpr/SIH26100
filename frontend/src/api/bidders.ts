import { apiClient } from "./client";
import {
  BidderCreate,
  BidderResponse,
  BidderStatus,
  BidderTenderResponse,
  BidderUpdate,
  DocumentResponse,
  VerificationHistoryItem,
} from "../types";

export type { BidderResponse, BidderTenderResponse };

export interface PaginatedBiddersResponse {
  success?: boolean;
  data?: BidderResponse[];
  items?: BidderResponse[];
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

export interface ListBiddersParams {
  page?: number;
  page_size?: number;
  status?: BidderStatus;
  search?: string;
}

export interface PaginatedBidderTendersResponse {
  success?: boolean;
  data?: BidderTenderResponse[];
  items?: BidderTenderResponse[];
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

/**
 * Lists registered bidders with pagination and filtering via GET /api/v1/bidders
 */
export async function listBidders(params: ListBiddersParams = {}): Promise<PaginatedBiddersResponse> {
  return apiClient.get<PaginatedBiddersResponse>("/bidders", {
    params: {
      page: params.page ?? 1,
      page_size: params.page_size ?? 10,
      status: params.status,
      search: params.search,
    },
  });
}

/**
 * Fetches a single bidder profile by ID via GET /api/v1/bidders/{id}
 */
export async function getBidder(bidderId: string): Promise<BidderResponse> {
  return apiClient.get<BidderResponse>(`/bidders/${bidderId}`);
}

/**
 * Registers a new bidder entity via POST /api/v1/bidders
 */
export async function createBidder(bidderIn: BidderCreate): Promise<BidderResponse> {
  return apiClient.post<BidderResponse>("/bidders", bidderIn);
}

/**
 * Updates an existing bidder via PUT /api/v1/bidders/{id}
 */
export async function updateBidder(bidderId: string, bidderIn: BidderUpdate): Promise<BidderResponse> {
  return apiClient.put<BidderResponse>(`/bidders/${bidderId}`, bidderIn);
}

/**
 * Partially updates an existing bidder via PATCH /api/v1/bidders/{id}
 */
export async function patchBidder(bidderId: string, bidderIn: BidderUpdate): Promise<BidderResponse> {
  return apiClient.patch<BidderResponse>(`/bidders/${bidderId}`, bidderIn);
}

/**
 * Updates a bidder's operational eligibility status via PATCH /api/v1/bidders/{id}/status
 */
export async function updateBidderStatus(bidderId: string, status: BidderStatus): Promise<BidderResponse> {
  return apiClient.patch<BidderResponse>(`/bidders/${bidderId}/status`, { status });
}

/**
 * Lists all tenders associated with a bidder via GET /api/v1/bidders/{id}/tenders
 */
export async function listBidderTenders(
  bidderId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<BidderTenderResponse[]> {
  const response = await apiClient.get<any>(`/bidders/${bidderId}/tenders`, {
    params: { page, page_size: pageSize },
  });
  if (Array.isArray(response)) return response;
  return response?.data || response?.items || [];
}

/**
 * Uploads compliance documents for a bidder via POST /api/v1/bidders/{id}/documents
 */
export async function uploadBidderDocument(
  bidderId: string,
  file: File,
  documentType: string = "OTHER",
  tenderId?: string
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("document_type", documentType);
  if (tenderId) {
    formData.append("tender_id", tenderId);
  }

  return apiClient.post<DocumentResponse>(`/bidders/${bidderId}/documents`, formData);
}

/**
 * Lists compliance documents uploaded for a bidder via GET /api/v1/bidders/{id}/documents
 */
export async function listBidderDocuments(
  bidderId: string,
  page: number = 1,
  pageSize: number = 20
): Promise<DocumentResponse[]> {
  const response = await apiClient.get<any>(`/bidders/${bidderId}/documents`, {
    params: { page, page_size: pageSize },
  });
  if (Array.isArray(response)) return response;
  return response?.data || response?.items || [];
}

/**
 * Retrieves chronological verification history for a tender & bidder pair via GET /api/v1/verification/tender/{tenderId}/bidder/{bidderId}
 */
export async function getBidderVerificationHistory(
  tenderId: string,
  bidderId: string
): Promise<VerificationHistoryItem[]> {
  const response = await apiClient.get<VerificationHistoryItem[]>(
    `/verification/tender/${tenderId}/bidder/${bidderId}`
  );
  return Array.isArray(response) ? response : [];
}
