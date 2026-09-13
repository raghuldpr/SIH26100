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
  field?: string;
  operator?: string;
  required_value?: any;
  resolution_method?: string;
  status?: string;
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

export interface StructuredEvidenceItem {
  source_document?: string | null;
  page_number?: number | null;
  field?: string | null;
  section?: string | null;
  detected_value?: any;
  normalized_value?: any;
  expected_value?: any;
  requirement?: string | null;
  evidence_text?: string | null;
  reference?: string | null;
  confidence?: number | null;
  evidence_id?: string | null;
  document_id?: string | null;
}

export interface N8nAgentResult {
  agent: string;
  agent_name?: string;
  agent_id?: string;
  status: AgentStatus | string;
  normalized_status?: "VERIFIED" | "FAILED" | "UNRESOLVED" | "ERROR" | "NOT_APPLICABLE" | string;
  verification_id?: string;
  tender_id?: string;
  bidder_id?: string;
  decision?: string;
  result?: string;
  confidence?: number;
  evidence?: StructuredEvidenceItem[] | Record<string, any>;
  evidence_ids?: string[];
  requirement_ids?: string[];
  source_documents?: string[];
  findings?: string[];
  issues?: string[];
  errors?: string[];
  reason?: string;
  summary?: string;
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
  status?: "PASS" | "FAIL" | "UNRESOLVED" | string;
  confidence?: number;
  agent?: string;
  evidence?: StructuredEvidenceItem[];
  evidence_ids?: string[];
  document_ids?: string[];
  source_page?: number | null;
  source_section?: string | null;
  source_text?: string | null;
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

export interface AgentConfidenceItem {
  agent_id: string;
  confidence: number | null;
  status: string;
}

export interface RequirementConfidenceItem {
  requirement_id: string;
  rule?: string;
  confidence: number | null;
  status: string;
}

export interface UnresolvedConfidenceItem {
  type: "AGENT" | "REQUIREMENT" | string;
  requirement_id?: string;
  rule?: string;
  agent_id?: string;
  status: string;
  confidence?: number | null;
  reason?: string;
}

export interface VerificationConfidenceBreakdown {
  overall_confidence: number | null;
  method: string;
  formula?: string;
  inputs: number[];
  calculated_confidence: number | null;
  agent_confidence: AgentConfidenceItem[];
  requirement_confidence: RequirementConfidenceItem[];
  unresolved_items: UnresolvedConfidenceItem[];
}

export interface CrossVerificationValueItem {
  source_document?: string | null;
  page_number?: number | null;
  value: any;
  evidence_id?: string | null;
}

export interface CrossVerificationCheckItem {
  check_id: string;
  field: string;
  status: "CONSISTENT" | "INCONSISTENT" | "UNRESOLVED" | string;
  values: CrossVerificationValueItem[];
  reason: string;
}

export interface VerificationCrossVerification {
  overall_status: "CONSISTENT" | "INCONSISTENT" | "UNRESOLVED" | string;
  checks: CrossVerificationCheckItem[];
}

export interface ForensicAnomalyItem {
  anomaly_id: string;
  anomaly_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | string;
  confidence?: number | null;
  description: string;
  source_document?: string | null;
  document_id?: string | null;
  page_number?: number | null;
  affected_field?: string | null;
  evidence?: Record<string, any>;
}

export interface ForensicDocumentResult {
  document_id?: string | null;
  source_document: string;
  status: "CLEAN" | "SUSPICIOUS" | "ANOMALY" | "UNRESOLVED" | string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" | string;
  confidence?: number | null;
  sha256?: string | null;
  anomalies: ForensicAnomalyItem[];
}

export interface VerificationDocumentForensics {
  overall_status: "CLEAN" | "SUSPICIOUS" | "ANOMALY" | "UNRESOLVED" | string;
  overall_risk: "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN" | string;
  documents: ForensicDocumentResult[];
  summary?: string | null;
}

export interface DocumentReference {
  document_id?: string | null;
  source_document?: string | null;
  page_number?: number | null;
}

export interface DocumentSimilarityComparison {
  comparison_id: string;
  document_a: DocumentReference;
  document_b: DocumentReference;
  document_a_page?: number | null;
  document_b_page?: number | null;
  comparison_type: "EXACT_DUPLICATE" | "CONTENT_SIMILARITY" | string;
  similarity_score: number;
  threshold: number;
  status: "EXACT_DUPLICATE" | "HIGH_SIMILARITY" | "MODERATE_SIMILARITY" | "LOW_SIMILARITY" | string;
  reason: string;
}

export interface VerificationDocumentSimilarity {
  overall_status: "NO_COMPARISON" | "SIMILARITY_FOUND" | "EXACT_DUPLICATE" | "INSUFFICIENT_REFERENCE_CORPUS" | string;
  comparisons: DocumentSimilarityComparison[];
  reason?: string | null;
}

export interface AppliedPolicyRule {
  rule_id: string;
  trigger: string;
  action: "QUALIFIED" | "NOT_QUALIFIED" | "MANUAL_REVIEW" | string;
  reason: string;
}

export interface PolicyFindingItem {
  finding_id: string;
  finding_type:
    | "MANDATORY_REQUIREMENT_FAILURE"
    | "MANDATORY_REQUIREMENT_UNRESOLVED"
    | "CRITICAL_AGENT_FAILURE"
    | "FORENSIC_ANOMALY"
    | "CROSS_VERIFICATION_INCONSISTENCY"
    | "COMPLIANCE_CHECK_FAILURE"
    | "WARNING"
    | string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | string;
  source: string;
  description: string;
}

export interface VerificationCompliancePolicy {
  final_status: "QUALIFIED" | "NOT_QUALIFIED" | "MANUAL_REVIEW" | string;
  blocking_findings: PolicyFindingItem[];
  review_findings: PolicyFindingItem[];
  warnings: string[];
  applied_rules: AppliedPolicyRule[];
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
  confidence_breakdown?: VerificationConfidenceBreakdown;
  cross_verification?: VerificationCrossVerification;
  document_forensics?: VerificationDocumentForensics;
  document_similarity?: VerificationDocumentSimilarity;
  compliance_policy?: VerificationCompliancePolicy;
  result_hash?: string;
  reasons: string[];
  decision_explanation?: string;
  decision_factors?: Array<{
    type: string;
    requirement_id?: string;
    rule?: string;
    mandatory?: boolean;
    status?: string;
    reason?: string;
    evidence?: StructuredEvidenceItem[];
    agent_id?: string;
  }>;
  passed_agents?: string[];
  failed_agents?: string[];
  review_agents?: string[];
  passed_requirements?: string[];
  failed_requirements: string[];
  review_requirements?: string[];
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
  tender_id?: string;
  tender_number?: string;
  bidder_id?: string;
  bidder_name?: string;
  status: string;
  decision?: VerificationDecision | string;
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

export interface GeMTenderMetadata {
  bid_id: string;
  title: string;
  organization: string;
  department?: string;
  category?: string;
  tender_type?: string;
  published_date?: string;
  bid_end_date?: string;
  estimated_value?: number;
  location?: string;
  status?: string;
  source: string;
  document_available: boolean;
  document_url?: string;
  document_name?: string;
  raw_details?: Record<string, any>;
}

export interface GeMLookupResponse {
  status: "found" | "already_imported" | "unavailable" | "invalid_bid_id";
  bid_id: string;
  already_imported: boolean;
  existing_tender_id?: string;
  existing_tender?: TenderResponse;
  gem_data?: GeMTenderMetadata;
  message?: string;
  can_manual_upload: boolean;
}

