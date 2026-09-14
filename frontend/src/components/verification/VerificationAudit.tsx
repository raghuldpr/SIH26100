import React, { useState } from "react";
import { VerificationResponse, N8nAgentResult } from "../../types";
import {
  Activity,
  Clock,
  Copy,
  Check,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Play,
  RefreshCw,
  MinusCircle,
  HelpCircle,
  Hash,
  ChevronDown,
  ChevronUp,
  FileText,
  Building2,
  ShieldCheck,
  Info,
  Terminal,
} from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface VerificationAuditProps {
  verification?: VerificationResponse | null;
  verificationId?: string;
  tenderReference?: string;
  tenderTitle?: string;
}

type NormalizedEventStatus =
  | "started"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "unresolved"
  | "unknown";

interface AuditTimelineItem {
  id: string;
  eventType: string;
  eventTitle: string;
  agentName?: string;
  agentId?: string;
  status: NormalizedEventStatus;
  rawStatus?: string;
  timestamp?: string;
  durationMs?: number;
  durationFormatted?: string;
  summary?: string;
  details?: Record<string, any>;
  resultHash?: string;
  errors?: string[];
  issues?: string[];
}

/**
 * Redacts any sensitive keys from technical metadata dictionaries
 */
function sanitizeTechnicalDetails(details: Record<string, any>): Record<string, any> {
  const sensitivePattern = /(token|password|secret|key|auth|credential|authorization|cookie)/i;
  const sanitized: Record<string, any> = {};

  for (const [k, v] of Object.entries(details)) {
    if (sensitivePattern.test(k)) {
      sanitized[k] = "[REDACTED]";
    } else if (v && typeof v === "object" && !Array.isArray(v)) {
      sanitized[k] = sanitizeTechnicalDetails(v);
    } else {
      sanitized[k] = v;
    }
  }
  return sanitized;
}

/**
 * Formats duration milliseconds into a readable string
 */
function formatDuration(ms?: number): string | undefined {
  if (ms === undefined || ms === null || isNaN(ms)) return undefined;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/**
 * Normalizes agent or step status into controlled status categories
 * Does NOT assume success when status is missing.
 */
function normalizeStatus(
  status?: string,
  normalizedStatus?: string,
  decision?: string
): NormalizedEventStatus {
  const s = (normalizedStatus || status || "").trim().toUpperCase();
  const d = (decision || "").trim().toUpperCase();

  if (s === "FAILED" || s === "ERROR" || s === "CRITICAL_ERROR" || d === "FAIL" || d === "FAILED") {
    return "failed";
  }
  if (s === "SKIPPED" || s === "NOT_APPLICABLE") {
    return "skipped";
  }
  if (s === "UNRESOLVED" || s === "MANUAL_REVIEW" || s === "INCONCLUSIVE" || d === "MANUAL_REVIEW") {
    return "unresolved";
  }
  if (s === "RUNNING" || s === "IN_PROGRESS" || s === "PROCESSING") {
    return "running";
  }
  if (s === "STARTED" || s === "DISPATCHED" || s === "INITIALIZING") {
    return "started";
  }
  if (s === "COMPLETED" || s === "VERIFIED" || s === "SUCCESS" || d === "PASS" || d === "QUALIFIED") {
    return "completed";
  }
  if (!s && !d) {
    return "unknown";
  }
  return "unresolved";
}

export const VerificationAudit: React.FC<VerificationAuditProps> = ({
  verification,
  verificationId,
  tenderReference,
  tenderTitle,
}) => {
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [expandedEvents, setExpandedEvents] = useState<Record<string, boolean>>({});

  const handleCopy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const toggleExpand = (id: string) => {
    setExpandedEvents((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  // Missing-data behavior (Requirement 9)
  if (!verification) {
    return (
      <section
        aria-labelledby="audit-trail-heading"
        className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4 font-sans"
      >
        <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20">
          <Activity className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
          <div>
            <h2 id="audit-trail-heading" className="text-base font-bold text-on-surface">
              Audit Trail
            </h2>
            <p className="text-xs text-on-surface-variant">
              The audit trail records verification processing events and technical integrity information for traceability.
            </p>
          </div>
        </div>

        <div className="text-center py-12 bg-surface-container-low/40 rounded-xl p-6 space-y-2 border border-dashed border-outline-variant/30">
          <HelpCircle className="h-8 w-8 text-outline mx-auto" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-on-surface">
            Audit Data Unavailable
          </h3>
          <p className="text-xs text-on-surface-variant max-w-md mx-auto">
            No verification record was provided to reconstruct the audit trail. Missing audit data must not be interpreted as successful verification.
          </p>
          {verificationId && (
            <div className="font-mono text-xs text-on-surface-variant pt-1">
              Referenced ID: <span className="font-bold text-on-surface">{verificationId}</span>
            </div>
          )}
        </div>
      </section>
    );
  }

  // Derive Verification Identity Values (Requirement 3)
  const resolvedVerificationId = verification.verification_id || verification.id || verificationId || "—";
  const resolvedTenderRef = tenderReference || verification.tender_number;
  const resolvedTenderTitle = tenderTitle || verification.tender_title;
  const resolvedBidderName = verification.bidder_name;
  const executedTimestamp = verification.completed_at || verification.started_at || verification.created_at;
  const finalDecision = verification.decision || "PENDING";
  const resultHash = verification.result_hash;

  // Build Chronological Timeline Events (Requirements 5, 6, 7)
  const timelineItems: AuditTimelineItem[] = [];

  // 1. Lifecycle Initiation Event (if timestamps or request details exist)
  if (verification.created_at || verification.started_at) {
    const initTs = verification.started_at || verification.created_at;
    timelineItems.push({
      id: `init-${resolvedVerificationId}`,
      eventType: "VERIFICATION_INITIATED",
      eventTitle: "Verification Pipeline Dispatched",
      status: "started",
      timestamp: initTs,
      summary: `Verification request ${verification.request_id || resolvedVerificationId} received and dispatched to autonomous multi-agent pipeline.`,
      details: sanitizeTechnicalDetails({
        verification_id: resolvedVerificationId,
        request_id: verification.request_id,
        tender_id: verification.tender_id,
        bidder_id: verification.bidder_id,
        created_at: verification.created_at,
        started_at: verification.started_at,
      }),
    });
  }

  // 2. Sequential Agent Execution Events
  const rawAgents: N8nAgentResult[] = verification.agent_results || [];
  rawAgents.forEach((ag, idx) => {
    const agentIdentifier = ag.agent_name || ag.agent || ag.agent_id || `Agent #${idx + 1}`;
    const agentStatus = normalizeStatus(ag.status, ag.normalized_status, ag.decision);
    const duration = ag.execution_metadata?.duration_ms ?? ag.execution_metadata?.duration;
    const errorsList = ag.errors && ag.errors.length > 0 ? ag.errors : undefined;
    const issuesList = ag.issues && ag.issues.length > 0 ? ag.issues : undefined;

    const technicalData: Record<string, any> = {
      agent_key: ag.agent,
      agent_id: ag.agent_id,
      decision: ag.decision,
      risk_level: ag.risk_level,
      confidence: ag.confidence !== undefined ? ag.confidence : undefined,
    };
    if (ag.execution_metadata && Object.keys(ag.execution_metadata).length > 0) {
      technicalData.execution_metadata = ag.execution_metadata;
    }
    if (errorsList) technicalData.errors = errorsList;
    if (issuesList) technicalData.issues = issuesList;
    if (ag.findings && ag.findings.length > 0) technicalData.findings = ag.findings;

    timelineItems.push({
      id: ag.execution_metadata?.event_id || `${resolvedVerificationId}-${ag.agent || idx}`,
      eventType: "AGENT_EXECUTION",
      eventTitle: `${agentIdentifier.replace(/_/g, " ")} Evaluated`,
      agentName: ag.agent_name || ag.agent,
      agentId: ag.agent_id,
      status: agentStatus,
      rawStatus: ag.normalized_status || ag.status,
      timestamp: ag.timestamp || ag.execution_metadata?.timestamp,
      durationMs: typeof duration === "number" ? duration : undefined,
      durationFormatted: formatDuration(typeof duration === "number" ? duration : undefined),
      summary:
        ag.summary ||
        ag.reason ||
        (ag.findings && ag.findings[0]) ||
        (ag.issues && ag.issues[0]) ||
        "Execution completed for this verification component.",
      details: sanitizeTechnicalDetails(technicalData),
      errors: errorsList,
      issues: issuesList,
    });
  });

  // 3. Lifecycle Finalization Event (if terminal status or completed_at recorded)
  if (verification.completed_at || verification.status === "COMPLETED" || verification.status === "FAILED") {
    const isFailed =
      verification.status === "FAILED" ||
      finalDecision.toUpperCase() === "NOT_QUALIFIED" ||
      Boolean(verification.error);

    const finalStatus: NormalizedEventStatus =
      verification.status === "COMPLETED"
        ? "completed"
        : isFailed
        ? "failed"
        : "unresolved";

    timelineItems.push({
      id: `sealed-${resolvedVerificationId}`,
      eventType: "VERIFICATION_SEALED",
      eventTitle: "Evaluation Sealed & Result Digest Recorded",
      status: finalStatus,
      timestamp: verification.completed_at,
      summary: `Verification finalized with verdict: ${finalDecision}. Risk assessed at ${verification.risk_level || "UNKNOWN"} (${verification.risk_score !== undefined ? Math.round(verification.risk_score) : "—"}/100).`,
      resultHash: resultHash,
      details: sanitizeTechnicalDetails({
        verification_id: resolvedVerificationId,
        decision: finalDecision,
        status: verification.status,
        risk_level: verification.risk_level,
        risk_score: verification.risk_score,
        result_hash: resultHash,
        completed_at: verification.completed_at,
        error: verification.error,
      }),
      errors: verification.error ? [JSON.stringify(verification.error)] : undefined,
    });
  }

  // Check if any timestamps exist across events (Requirement 7)
  const anyTimestampsAvailable = timelineItems.some((item) => Boolean(item.timestamp));

  // Render Status Badge with Text and Icon (Requirement 6 & 12)
  const renderStatusBadge = (status: NormalizedEventStatus, raw?: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />
            <span>COMPLETED</span>
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300 dark:bg-rose-950/40 dark:text-rose-300">
            <XCircle className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400 shrink-0" aria-hidden="true" />
            <span>FAILED</span>
          </span>
        );
      case "running":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-sky-50 text-sky-800 border border-sky-300 dark:bg-sky-950/40 dark:text-sky-300">
            <RefreshCw className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400 animate-spin shrink-0" aria-hidden="true" />
            <span>RUNNING</span>
          </span>
        );
      case "started":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-primary/10 text-primary border border-primary/20">
            <Play className="h-3 w-3 text-primary shrink-0" aria-hidden="true" />
            <span>STARTED</span>
          </span>
        );
      case "skipped":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300">
            <MinusCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" aria-hidden="true" />
            <span>SKIPPED</span>
          </span>
        );
      case "unresolved":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-400 dark:bg-amber-950/50 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400 shrink-0" aria-hidden="true" />
            <span>UNRESOLVED</span>
          </span>
        );
      case "unknown":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-surface-container text-on-surface-variant border border-outline-variant/30">
            <HelpCircle className="h-3.5 w-3.5 text-outline shrink-0" aria-hidden="true" />
            <span>{raw || "STATUS UNKNOWN"}</span>
          </span>
        );
    }
  };

  const getDecisionBadge = (decision: string) => {
    switch (decision.toUpperCase()) {
      case "QUALIFIED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <CheckCircle2 className="h-3 w-3 text-emerald-600" aria-hidden="true" />
            QUALIFIED
          </span>
        );
      case "NOT_QUALIFIED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300">
            <XCircle className="h-3 w-3 text-rose-600" aria-hidden="true" />
            NOT QUALIFIED
          </span>
        );
      case "MANUAL_REVIEW":
      case "CONDITIONALLY_QUALIFIED":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-400">
            <AlertTriangle className="h-3 w-3 text-amber-600" aria-hidden="true" />
            MANUAL REVIEW
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-surface-container text-on-surface-variant border border-outline-variant/30 font-mono">
            {decision}
          </span>
        );
    }
  };

  return (
    <section
      aria-labelledby="audit-trail-heading"
      className="p-5 md:p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-6 font-sans"
    >
      {/* 1. Header & Neutral Description (Requirements 1 & 2) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-outline-variant/20">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
            <h2 id="audit-trail-heading" className="text-base font-bold text-on-surface">
              Audit Trail
            </h2>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono">
              {timelineItems.length} {timelineItems.length === 1 ? "event" : "events"}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            The audit trail records verification processing events, execution milestones, and technical integrity information for administrative traceability.
          </p>
        </div>

        {/* Informational Isolation Tag (Requirement 10) */}
        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-surface-container text-[11px] font-medium text-on-surface-variant border border-outline-variant/30 self-start sm:self-auto shrink-0">
          <Info className="h-3.5 w-3.5 text-outline shrink-0" aria-hidden="true" />
          <span>Operational Traceability</span>
        </span>
      </div>

      {/* Informational Isolation Notice (Requirement 10) */}
      <div className="p-3 rounded-lg bg-surface-container-low/60 border border-outline-variant/25 text-xs text-on-surface-variant flex items-start gap-2.5">
        <ShieldCheck className="h-4 w-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
        <p className="leading-relaxed">
          <strong className="text-on-surface font-semibold">Informational Traceability Notice:</strong> This audit trail logs sequential pipeline processing events and cryptographic digests. Traceability logs reflect technical execution events and do not alter or substitute for the substantive procurement qualification decision.
        </p>
      </div>

      {/* 2. Verification Identity Summary (Requirement 3) */}
      <div className="bg-surface-container-low/40 rounded-xl p-4 md:p-5 border border-outline-variant/25 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider font-mono text-on-surface flex items-center gap-1.5">
            <Terminal className="h-4 w-4 text-primary" aria-hidden="true" />
            <span>Verification Identity Summary</span>
          </span>
          {getDecisionBadge(finalDecision)}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
          {/* Verification ID */}
          <div className="space-y-1">
            <span className="text-on-surface-variant font-medium block">Verification ID</span>
            <div className="flex items-center gap-1.5 font-mono text-on-surface font-bold break-all">
              <span>{resolvedVerificationId}</span>
              <button
                type="button"
                onClick={() => handleCopy(resolvedVerificationId, "verification_id")}
                className="p-1 rounded text-on-surface-variant hover:text-primary transition-colors shrink-0"
                title="Copy Verification ID"
                aria-label="Copy Verification ID"
              >
                {copiedText === "verification_id" ? (
                  <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
                ) : (
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>

          {/* Tender Reference / Title */}
          <div className="space-y-1">
            <span className="text-on-surface-variant font-medium block">Tender Reference</span>
            <div className="font-sans text-on-surface font-semibold truncate" title={`${resolvedTenderRef || ""} ${resolvedTenderTitle || ""}`}>
              <span className="flex items-center gap-1">
                <FileText className="h-3.5 w-3.5 text-primary shrink-0" aria-hidden="true" />
                <span className="truncate">{resolvedTenderRef || "Not specified"}</span>
              </span>
              {resolvedTenderTitle && (
                <span className="block text-[11px] font-normal text-on-surface-variant truncate">
                  {resolvedTenderTitle}
                </span>
              )}
            </div>
          </div>

          {/* Bidder Name */}
          <div className="space-y-1">
            <span className="text-on-surface-variant font-medium block">Bidder Organization</span>
            <div className="font-sans text-on-surface font-semibold truncate flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5 text-primary shrink-0" aria-hidden="true" />
              <span className="truncate">{resolvedBidderName || "Not specified"}</span>
            </div>
          </div>

          {/* Execution Timestamp */}
          <div className="space-y-1">
            <span className="text-on-surface-variant font-medium block">Executed / Finalized</span>
            <div className="font-mono text-on-surface flex items-center gap-1.5">
              <Clock className="h-3.5 w-3.5 text-outline shrink-0" aria-hidden="true" />
              <span>{executedTimestamp ? formatDate(executedTimestamp) : "Timestamp unavailable"}</span>
            </div>
          </div>

          {/* Pipeline Status */}
          <div className="space-y-1">
            <span className="text-on-surface-variant font-medium block">Lifecycle Status</span>
            <div className="font-mono font-semibold text-on-surface">
              {verification.status || "COMPLETED"}
            </div>
          </div>

          {/* Risk Level */}
          <div className="space-y-1">
            <span className="text-on-surface-variant font-medium block">Assessed Risk</span>
            <div className="font-mono font-semibold text-on-surface uppercase">
              {verification.risk_level || "LOW"}{" "}
              {verification.risk_score !== undefined && (
                <span className="text-on-surface-variant font-normal">
                  ({Math.round(verification.risk_score)}/100)
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Cryptographic Integrity Digest Card (Requirement 4) */}
      <div className="p-4 md:p-5 rounded-xl bg-surface-container-low/70 border border-outline-variant/30 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Hash className="h-4 w-4 text-primary shrink-0" aria-hidden="true" />
            <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-on-surface">
              Recorded Result Hash
            </h3>
          </div>
          <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">
            SHA-256 Digest
          </span>
        </div>

        {resultHash ? (
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-surface-container-lowest rounded-lg border border-outline-variant/25">
            <div className="min-w-0 flex-1">
              <span className="text-[11px] font-mono text-on-surface-variant block mb-0.5">
                Result Integrity Digest
              </span>
              <code className="font-mono text-xs font-bold text-primary break-all block select-all">
                {resultHash}
              </code>
            </div>
            <button
              type="button"
              onClick={() => handleCopy(resultHash, "result_hash")}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-outline-variant/40 bg-surface-container-lowest hover:bg-surface-container text-on-surface transition-colors shrink-0 self-start sm:self-center"
              aria-label="Copy Result Integrity Digest"
            >
              {copiedText === "result_hash" ? (
                <>
                  <Check className="h-3.5 w-3.5 text-emerald-600" aria-hidden="true" />
                  <span className="text-emerald-700 font-semibold">Copied</span>
                </>
              ) : (
                <>
                  <Copy className="h-3.5 w-3.5 text-outline" aria-hidden="true" />
                  <span>Copy Hash</span>
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="p-3 bg-surface-container-lowest rounded-lg border border-dashed border-outline-variant/30 text-xs text-on-surface-variant font-mono italic">
            Result integrity digest not recorded for this execution.
          </div>
        )}

        <p className="text-[11px] text-on-surface-variant leading-relaxed">
          The result integrity digest is a deterministic cryptographic hash computed over the finalized verification outcome. It verifies the technical immutability of the recorded decision and does not certify the external truthfulness or authenticity of vendor-provided document contents.
        </p>
      </div>

      {/* 4. Timeline (Requirements 5, 6, 7, 8) */}
      <div className="space-y-4 pt-2">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <span>Execution Timeline</span>
            <span className="text-xs font-mono font-normal text-on-surface-variant">
              ({timelineItems.length} {timelineItems.length === 1 ? "step" : "steps"})
            </span>
          </h3>

          {!anyTimestampsAvailable && timelineItems.length > 0 && (
            <span className="text-[11px] font-mono text-on-surface-variant italic">
              Exact event timestamps unavailable; preserving backend execution order.
            </span>
          )}
        </div>

        {timelineItems.length === 0 ? (
          <div className="text-center py-10 bg-surface-container-low/40 rounded-xl text-xs text-on-surface-variant border border-dashed border-outline-variant/30 p-6 space-y-2">
            <HelpCircle className="h-7 w-7 text-outline mx-auto" aria-hidden="true" />
            <div className="font-semibold text-on-surface">No Audit Events Recorded</div>
            <p className="max-w-md mx-auto">
              No processing timeline events or agent execution traces were captured for this verification run. Missing audit data must not be interpreted as successful verification.
            </p>
          </div>
        ) : (
          <ol
            role="list"
            aria-label="Verification execution audit events"
            className="relative pl-6 md:pl-8 border-l-2 border-primary/20 space-y-5"
          >
            {timelineItems.map((evt, idx) => {
              const isExpanded = Boolean(expandedEvents[evt.id]);
              const hasDetails = evt.details && Object.keys(evt.details).length > 0;

              // Node bullet styling based on status
              const bulletBg =
                evt.status === "completed"
                  ? "bg-emerald-600 ring-emerald-100"
                  : evt.status === "failed"
                  ? "bg-error ring-red-100"
                  : evt.status === "running"
                  ? "bg-sky-500 ring-sky-100"
                  : evt.status === "started"
                  ? "bg-primary ring-emerald-100"
                  : evt.status === "skipped"
                  ? "bg-slate-400 ring-slate-100"
                  : "bg-amber-500 ring-amber-100";

              return (
                <li key={evt.id || idx} role="listitem" className="relative group">
                  {/* Timeline Bullet Node */}
                  <div
                    className={`absolute -left-[31px] md:-left-[39px] top-3.5 w-3.5 h-3.5 rounded-full ${bulletBg} ring-4 shadow-xs`}
                    aria-hidden="true"
                  />

                  <article
                    aria-label={`${evt.eventTitle} event`}
                    className="p-4 md:p-5 bg-surface-container-low/50 rounded-xl border border-outline-variant/25 hover:border-primary/30 transition-all space-y-3"
                  >
                    {/* Event Header */}
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2.5">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="font-bold text-sm text-on-surface">
                            {evt.eventTitle}
                          </h4>
                          {renderStatusBadge(evt.status, evt.rawStatus)}
                        </div>

                        {/* Event Sub-metadata */}
                        <div className="flex items-center gap-3 text-xs text-on-surface-variant flex-wrap font-mono">
                          <span className="bg-surface-container px-2 py-0.5 rounded text-[11px]">
                            {evt.eventType}
                          </span>

                          {evt.agentId && (
                            <span>
                              ID: <strong className="text-on-surface">{evt.agentId}</strong>
                            </span>
                          )}

                          {evt.durationFormatted && (
                            <span className="text-on-surface font-semibold">
                              Duration: {evt.durationFormatted}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Timestamp (Requirement 7: Do not invent missing timestamps) */}
                      <div className="text-xs text-on-surface-variant flex items-center gap-1.5 font-mono shrink-0">
                        <Clock className="h-3.5 w-3.5 text-outline" aria-hidden="true" />
                        {evt.timestamp ? (
                          <time dateTime={evt.timestamp}>{formatDate(evt.timestamp)}</time>
                        ) : (
                          <span className="italic opacity-80">Timestamp not recorded</span>
                        )}
                      </div>
                    </div>

                    {/* Summary / Message */}
                    {evt.summary && (
                      <p className="text-xs text-on-surface leading-relaxed">
                        {evt.summary}
                      </p>
                    )}

                    {/* Error information if present */}
                    {evt.errors && evt.errors.length > 0 && (
                      <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-xs text-rose-900 space-y-1 dark:bg-rose-950/30 dark:border-rose-900 dark:text-rose-200">
                        <div className="font-bold flex items-center gap-1 text-error">
                          <XCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                          <span>Error Details Recorded:</span>
                        </div>
                        <ul className="list-disc pl-4 space-y-0.5 font-mono text-[11px] break-all">
                          {evt.errors.map((err, errIdx) => (
                            <li key={errIdx}>{err}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Event Hash if attached */}
                    {evt.resultHash && (
                      <div className="flex items-center justify-between text-xs font-mono p-2.5 bg-surface-container/70 rounded-lg border border-outline-variant/20 gap-2">
                        <div className="truncate">
                          <span className="text-on-surface-variant font-medium mr-1.5">Event Hash:</span>
                          <span className="font-bold text-on-surface break-all">{evt.resultHash}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleCopy(evt.resultHash!, evt.id)}
                          className="p-1 rounded text-on-surface-variant hover:text-primary transition-colors shrink-0"
                          title="Copy Hash"
                          aria-label="Copy Event Hash"
                        >
                          {copiedText === evt.id ? (
                            <Check className="h-4 w-4 text-emerald-600" aria-hidden="true" />
                          ) : (
                            <Copy className="h-4 w-4" aria-hidden="true" />
                          )}
                        </button>
                      </div>
                    )}

                    {/* Expandable Technical Details (Requirement 8) */}
                    {hasDetails && (
                      <div className="pt-1">
                        <button
                          type="button"
                          onClick={() => toggleExpand(evt.id)}
                          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors focus:outline-hidden"
                          aria-expanded={isExpanded}
                          aria-controls={`details-${evt.id}`}
                        >
                          {isExpanded ? (
                            <>
                              <ChevronUp className="h-3.5 w-3.5" aria-hidden="true" />
                              <span>Hide Technical Details</span>
                            </>
                          ) : (
                            <>
                              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
                              <span>View Technical Details</span>
                            </>
                          )}
                        </button>

                        {isExpanded && (
                          <div
                            id={`details-${evt.id}`}
                            className="mt-2 text-xs font-mono text-on-surface bg-surface-container/50 p-3 rounded-lg border border-outline-variant/20 overflow-x-auto custom-scrollbar break-all space-y-1"
                          >
                            <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed">
                              {JSON.stringify(evt.details, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </article>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </section>
  );
};

export default VerificationAudit;
