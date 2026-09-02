/**
 * Core Domain TypeScript Types (Synchronized with FastAPI backend schemas)
 */

export type UserRole = "PROCUREMENT_OFFICER" | "ADMIN" | "REVIEWER" | "BUYER" | "BIDDER";

export type TenderStatus = "DRAFT" | "OPEN" | "PUBLISHED" | "EVALUATING" | "CLOSED" | "CANCELLED" | "ARCHIVED";

export type BidderStatus = "ACTIVE" | "INACTIVE" | "SUSPENDED";

export type VerificationStatus =
  | "QUEUED"
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "UNVERIFIED"
  | "PENDING"
  | "PROCESSING"
  | "ERROR";

export type VerificationDecision =
  | "QUALIFIED"
  | "NOT_QUALIFIED"
  | "CONDITIONALLY_QUALIFIED"
  | "MANUAL_REVIEW";

export type OverallCompliance =
  | "COMPLIANT"
  | "NON_COMPLIANT"
  | "PARTIALLY_COMPLIANT"
  | "UNVERIFIED"
  | "INCONCLUSIVE";

export type RequirementCompliance =
  | "COMPLIANT"
  | "NON_COMPLIANT"
  | "PARTIALLY_COMPLIANT"
  | "UNVERIFIED";

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | "UNKNOWN";

export type AgentStatus =
  | "PASS"
  | "FAIL"
  | "PARTIAL"
  | "UNKNOWN"
  | "ERROR"
  | "VERIFIED"
  | "NOT_VERIFIED"
  | "REVIEW"
  | "WARNING"
  | "INCONCLUSIVE"
  | "SKIPPED"
  | "NOT_EXECUTED"
  | "FAILED"
  | "QUALIFIED";

export type DocumentType =
  | "TENDER_NOTICE"
  | "TECHNICAL_SPECIFICATION"
  | "GST_CERTIFICATE"
  | "PAN_CARD"
  | "UDYAM_CERTIFICATE"
  | "FINANCIAL_STATEMENT"
  | "PAST_EXPERIENCE"
  | "AFFIDAVIT"
  | "OTHER";

export type DocumentStatus = "ACTIVE" | "ARCHIVED" | "DELETED";

export type ProcessingStatus = "NOT_PROCESSED" | "PROCESSING" | "PROCESSED" | "FAILED";

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface UserCreate {
  email: string;
  name: string;
  password: string;
  role?: UserRole;
  is_active?: boolean;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface AuthResponse {
  user: UserResponse;
  token: Token;
}

export interface ApiErrorResponse {
  message?: string;
  detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
  code?: string;
  status_code?: number;
}

export interface StandardResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface TenderBase {
  tender_number: string;
  title: string;
  organization: string;
  department?: string;
  category?: string;
  description?: string;
  bid_start_date?: string;
  bid_end_date?: string;
  status?: TenderStatus;
}

export interface TenderCreate extends TenderBase {}

export interface TenderUpdate {
  tender_number?: string;
  title?: string;
  organization?: string;
  department?: string;
  category?: string;
  description?: string;
  bid_start_date?: string;
  bid_end_date?: string;
  status?: TenderStatus;
}

export interface TenderResponse {
  id: string;
  tender_number: string;
  title: string;
  organization: string;
  department?: string;
  category?: string;
  description?: string;
  bid_start_date?: string;
  bid_end_date?: string;
  status: TenderStatus;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  estimated_value?: number;
}

export interface BidderBase {
  company_name: string;
  registration_number?: string;
  gst_number?: string;
  pan_number?: string;
  udyam_number?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address?: string;
  status?: BidderStatus;
}

export interface BidderCreate extends BidderBase {}

export interface BidderUpdate {
  company_name?: string;
  registration_number?: string;
  gst_number?: string;
  pan_number?: string;
  udyam_number?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address?: string;
  status?: BidderStatus;
}

export interface BidderResponse {
  id: string;
  company_name: string;
  registration_number?: string;
  gst_number?: string;
  pan_number?: string;
  udyam_number?: string;
  contact_person?: string;
  email?: string;
  phone?: string;
  address?: string;
  status: BidderStatus;
  created_at?: string;
  updated_at?: string;
}

export interface BidderTenderResponse {
  id: string;
  tender_number: string;
  title: string;
  organization: string;
  department?: string;
  category?: string;
  status: TenderStatus;
  bid_start_date?: string;
  bid_end_date?: string;
  assignment_timestamp?: string;
}

export interface DocumentResponse {
  id: string;
  tender_id?: string;
  bidder_id?: string;
  original_filename: string;
  document_type: DocumentType | string;
  mime_type?: string;
  file_size?: number;
  sha256?: string;
  storage_path: string;
  status: DocumentStatus | string;
  processing_status: ProcessingStatus | string;
  processing_error?: string;
  extracted_data?: Record<string, any>;
  uploaded_at?: string;
  created_at?: string;
  updated_at?: string;
  download_url?: string;
}

export interface TenderRequirementResponse {
  id: string;
  tender_id: string;
  requirement_type: string;
  rule: string;
  description: string;
  parameters: Record<string, any>;
  mandatory: boolean;
  confidence: number;
  source_page?: number;
  source_section?: string;
  source_text?: string;
  created_at: string;
  updated_at: string;
}

export interface TenderComplianceProfileResponse {
  tender_id: string;
  tender_number: string;
  status: string;
  requirement_count: number;
  deterministic_count: number;
  ai_escalations: number;
  unresolved_count: number;
  deterministic_requirements: TenderRequirementResponse[];
  ai_assisted_requirements: TenderRequirementResponse[];
  unresolved_requirements: any[];
  requirements: TenderRequirementResponse[];
  analyzed_at: string;
}

// ---------------------------------------------------------------------------
// Verification Integration Schemas (Phase 10 & 12.8 Backend Synchronized)
// ---------------------------------------------------------------------------

export interface VerificationTriggerRequest {
  tender_id: string;
  bidder_id: string;
  required_agents?: string[];
  financial_overrides?: Record<string, any>;
  experience_overrides?: Record<string, any>;
  compliance_policy?: Record<string, any>;
  metadata?: Record<string, any>;
}

export interface N8nAgentResult {
  agent: string;
  agent_name?: string;
  status: AgentStatus | string;
  verification_id?: string;
  tender_id?: string;
  bidder_id?: string;
  decision?: string;
  confidence?: number;
  evidence?: Record<string, any>;
  evidence_ids?: string[];
  requirement_ids?: string[];
  source_documents?: string[];
  findings?: string[];
  issues?: string[];
  errors?: string[];
  reason?: string;
  risk_level: RiskLevel | string;
  execution_metadata?: Record<string, any>;
  timestamp?: string;
}

export interface RequirementEvaluation {
  requirement_id: string;
  rule?: string;
  description?: string;
  mandatory: boolean;
  decision: RequirementCompliance | string;
  confidence?: number;
  agent?: string;
  evidence_ids?: string[];
  document_ids?: string[];
  source_page?: number;
  source_section?: string;
  source_text?: string;
  reason?: string;
  findings?: string[];
}

export interface VerificationRiskAssessment {
  level: RiskLevel | string;
  score: number;
  reasons: string[];
  signals?: Record<string, any>;
  critical_flags?: string[];
}

export interface VerificationComplianceSummary {
  total_requirements: number;
  compliant: number;
  non_compliant: number;
  partially_compliant: number;
  unverified: number;
}

export interface VerificationResponse {
  id?: string;
  verification_id: string;
  request_id: string;
  tender_id: string;
  bidder_id: string;
  bidder_name: string;
  status: VerificationStatus | string;
  decision: VerificationDecision | string;
  overall_compliance?: OverallCompliance | string;
  risk_score: number;
  risk_level: RiskLevel | string;
  overall_confidence?: number;
  result_hash?: string;
  reasons: string[];
  failed_requirements: string[];
  warnings: string[];
  inconclusive_checks?: string[];
  missing_documents?: string[];
  agent_results: N8nAgentResult[];
  requirements: RequirementEvaluation[];
  risk?: VerificationRiskAssessment;
  summary?: VerificationComplianceSummary;
  evidence_snapshot?: Array<Record<string, any>>;
  document_hashes?: Record<string, string>;
  error?: Record<string, any>;
  raw_response?: Record<string, any>;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
}

export type VerificationExecutionSummary = VerificationResponse;

export interface VerificationHistoryItem {
  verification_id: string;
  status: string;
  overall_compliance?: OverallCompliance | string;
  risk_level?: RiskLevel | string;
  created_at: string;
  completed_at?: string;
  result_hash?: string;
}

export interface VerificationAuditEventResponse {
  id: string;
  verification_id: string;
  tender_id: string;
  bidder_id: string;
  event_type: string;
  result_hash?: string;
  details: Record<string, any>;
  created_at: string;
}

export interface N8nVerificationPayload {
  request_id: string;
  verification_id?: string;
  tender_id: string;
  tender_number?: string;
  tender_title?: string;
  bidder_id: string;
  bidder_name: string;
  required_agents: string[];
  gstin?: string;
  pan?: string;
  udyam?: string;
  cin?: string;
  documents?: any[];
  tender_requirements?: any[];
  bidder_evidence?: any[];
  metadata?: Record<string, any>;
  timestamp?: string;
}
