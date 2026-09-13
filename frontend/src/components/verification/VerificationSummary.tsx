import React, { useState } from "react";
import { VerificationResponse } from "../../types";
import { Badge, Progress } from "../ui";
import {
  ShieldCheck,
  AlertTriangle,
  XCircle,
  CheckCircle2,
  Hash,
  Copy,
  Check,
  Clock,
  Search,
} from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface VerificationSummaryProps {
  verification: VerificationResponse;
}

export const VerificationSummary: React.FC<VerificationSummaryProps> = ({ verification }) => {
  const [isCopiedHash, setIsCopiedHash] = useState(false);
  const [isCopiedId, setIsCopiedId] = useState(false);

  const handleCopyHash = () => {
    if (verification.result_hash) {
      navigator.clipboard.writeText(verification.result_hash);
      setIsCopiedHash(true);
      setTimeout(() => setIsCopiedHash(false), 2000);
    }
  };

  const handleCopyId = () => {
    if (verification.verification_id) {
      navigator.clipboard.writeText(verification.verification_id);
      setIsCopiedId(true);
      setTimeout(() => setIsCopiedId(false), 2000);
    }
  };

  const decisionUpper = (verification.decision || "").toUpperCase();

  // Banner color state based on Stitch design specifications
  const getBannerStyles = () => {
    switch (decisionUpper) {
      case "QUALIFIED":
        return {
          bg: "bg-primary text-white border-primary-container",
          iconBg: "bg-emerald-500/20 text-emerald-300",
          icon: <ShieldCheck className="h-8 w-8 text-emerald-400" />,
          badge: <Badge variant="success" size="md">QUALIFIED</Badge>,
          title: "QUALIFIED FOR AWARD",
          subtitle: "All mandatory statutory, technical, and financial criteria confirmed.",
        };
      case "NOT_QUALIFIED":
        return {
          bg: "bg-error text-white border-error/40",
          iconBg: "bg-white/20 text-white",
          icon: <XCircle className="h-8 w-8 text-red-200" />,
          badge: <Badge variant="danger" size="md">NOT QUALIFIED</Badge>,
          title: "BIDDER DISQUALIFIED",
          subtitle: "One or more mandatory tender requirements failed verification.",
        };
      case "MANUAL_REVIEW":
      case "CONDITIONALLY_QUALIFIED":
        return {
          bg: "bg-amber-900 text-white border-amber-700",
          iconBg: "bg-amber-500/20 text-amber-300",
          icon: <AlertTriangle className="h-8 w-8 text-amber-300" />,
          badge: <Badge variant="warning" size="md">MANUAL REVIEW REQUIRED</Badge>,
          title: "MANUAL PROCUREMENT REVIEW REQUIRED",
          subtitle: "Automated checks completed; human officer review required for subjective clauses.",
        };
      default:
        return {
          bg: "bg-surface-inverse text-white border-outline/30",
          iconBg: "bg-white/10 text-white",
          icon: <ShieldCheck className="h-8 w-8 text-primary-fixed" />,
          badge: <Badge variant="neutral" size="md">{verification.decision || "PENDING"}</Badge>,
          title: `DECISION: ${verification.decision || "PENDING"}`,
          subtitle: `Verification pipeline status: ${verification.status || "PROCESSING"}`,
        };
    }
  };

  const banner = getBannerStyles();

  // Unresolved requirements and manual review items
  const unresolvedItems = (verification.requirements || []).filter((r) => {
    const d = (r.decision || "").toUpperCase();
    return d === "UNRESOLVED" || d === "MANUAL_REVIEW" || d === "INCONCLUSIVE" || d === "UNVERIFIED";
  });
  const inconclusiveChecks = verification.inconclusive_checks || [];

  // Deduplicated failed requirements
  const rawFailed = verification.failed_requirements || [];
  const dedupedFailedStrings = Array.from(
    new Set(rawFailed.map((item) => (typeof item === "string" ? item : JSON.stringify(item))))
  );

  // Requirements mapped to failed list for structured cards
  const failedRequirementObjects = (verification.requirements || []).filter((r) => {
    const d = (r.decision || "").toUpperCase();
    return d === "NON_COMPLIANT" || d === "FAIL" || d === "FAILED";
  });

  return (
    <div className="space-y-6">
      {/* 1. OVERALL DECISION BANNER (Stitch 10-Second Target) */}
      <section className={`rounded-xl p-6 shadow-elevated border relative overflow-hidden transition-all ${banner.bg}`}>
        <div className="absolute top-0 right-0 w-96 h-full bg-gradient-to-l from-white/10 via-white/5 to-transparent pointer-events-none" />

        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 relative z-10">
          <div className="flex items-start gap-4">
            <div className={`p-3 rounded-xl flex items-center justify-center shrink-0 ${banner.iconBg}`}>
              {banner.icon}
            </div>
            <div className="space-y-1">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-2xl font-bold tracking-tight text-white font-sans">
                  {banner.title}
                </h2>
                {banner.badge}
              </div>
              <p className="text-sm text-white/85 leading-relaxed font-sans">
                {banner.subtitle}
              </p>
              <div className="pt-2 text-sm text-white/90 flex items-center gap-4 flex-wrap">
                <span>
                  Bidder: <strong className="text-white font-semibold">{verification.bidder_name}</strong>
                </span>
                <span>•</span>
                <span>
                  Status: <strong className="text-white font-semibold">{verification.status}</strong>
                </span>
                <span>•</span>
                <span>
                  Date: {formatDate(verification.completed_at || verification.created_at)}
                </span>
              </div>
            </div>
          </div>

          {/* Verification ID & SHA-256 Digest Card */}
          <div className="bg-black/30 backdrop-blur-md rounded-xl p-4 border border-white/15 w-full lg:w-auto shrink-0 space-y-3">
            <div className="flex items-center justify-between gap-4">
              <span className="text-xs font-mono uppercase tracking-wider text-white/70">Verification ID</span>
              <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-white">
                <span>{verification.verification_id}</span>
                <button
                  onClick={handleCopyId}
                  className="p-1 rounded hover:bg-white/10 text-white/75 hover:text-white transition-colors"
                  title="Copy Verification ID"
                >
                  {isCopiedId ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            {verification.result_hash && (
              <div className="pt-2.5 border-t border-white/15 space-y-1">
                <span className="text-[11px] font-mono uppercase tracking-wider text-white/70 flex items-center gap-1">
                  <Hash className="h-3 w-3" />
                  <span>Canonical Result SHA-256</span>
                </span>
                <div className="flex items-center justify-between gap-2 font-mono text-xs text-white/90">
                  <span className="truncate max-w-[210px]" title={verification.result_hash}>
                    {verification.result_hash}
                  </span>
                  <button
                    onClick={handleCopyHash}
                    className="p-1 rounded hover:bg-white/10 text-white/75 hover:text-white transition-colors shrink-0"
                    title="Copy Canonical Hash"
                  >
                    {isCopiedHash ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 2. EXECUTIVE METRIC TILES (4 Cards in a responsive grid) */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Risk Score */}
        <div className="bg-surface-container-lowest rounded-xl p-5 shadow-card border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Risk Score
            </span>
            <span
              className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                verification.risk_score > 60
                  ? "bg-red-100 text-red-800"
                  : verification.risk_score > 30
                  ? "bg-amber-100 text-amber-800"
                  : "bg-emerald-100 text-emerald-800"
              }`}
            >
              {verification.risk_level || "LOW"}
            </span>
          </div>
          <div className="my-3">
            <div className="flex items-baseline gap-1.5 font-sans">
              <span className="text-3xl font-bold text-on-surface">
                {Math.round(verification.risk_score)}
              </span>
              <span className="text-sm font-medium text-on-surface-variant">/ 100</span>
            </div>
            <div className="mt-2">
              <Progress
                value={verification.risk_score}
                variant={verification.risk_score > 60 ? "error" : verification.risk_score > 30 ? "warning" : "success"}
                size="sm"
              />
            </div>
          </div>
          <span className="text-xs text-on-surface-variant font-sans">
            {verification.risk_score <= 25
              ? "Negligible risk detected"
              : verification.risk_score <= 60
              ? "Moderate review items"
              : "High-risk signals detected"}
          </span>
        </div>

        {/* Overall Confidence */}
        <div className="bg-surface-container-lowest rounded-xl p-5 shadow-card border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Overall Confidence
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
              High
            </span>
          </div>
          <div className="my-3">
            <div className="text-3xl font-bold font-sans text-primary">
              {verification.overall_confidence !== undefined && verification.overall_confidence !== null
                ? `${Math.round(verification.overall_confidence * 100)}%`
                : "100%"}
            </div>
            <div className="mt-2">
              <Progress
                value={(verification.overall_confidence ?? 1.0) * 100}
                variant="primary"
                size="sm"
              />
            </div>
          </div>
          <span className="text-xs text-on-surface-variant font-sans">
            AI verification certainty
          </span>
        </div>

        {/* Compliance Summary */}
        <div className="bg-surface-container-lowest rounded-xl p-5 shadow-card border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Compliance Summary
            </span>
          </div>
          <div className="my-3 space-y-1 font-sans">
            <div className="text-lg font-bold text-emerald-700 flex items-center justify-between">
              <span>Compliant</span>
              <span>{verification.summary?.compliant ?? (verification.requirements?.filter((r) => r.decision === "COMPLIANT").length || 0)}</span>
            </div>
            <div className="text-sm font-semibold text-red-700 flex items-center justify-between">
              <span>Non-compliant</span>
              <span>{verification.summary?.non_compliant ?? (verification.failed_requirements?.length || 0)}</span>
            </div>
          </div>
          <span className="text-xs text-on-surface-variant font-sans">
            {verification.summary?.partially_compliant || 0} Partial /{" "}
            {unresolvedItems.length + inconclusiveChecks.length} Manual
          </span>
        </div>

        {/* Requirements Total */}
        <div className="bg-surface-container-lowest rounded-xl p-5 shadow-card border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Requirements
            </span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
              Tender
            </span>
          </div>
          <div className="my-3">
            <div className="text-3xl font-bold font-sans text-on-surface">
              {verification.requirements?.length || 0}
            </div>
          </div>
          <span className="text-xs text-on-surface-variant font-sans">
            {unresolvedItems.length + inconclusiveChecks.length > 0
              ? `${unresolvedItems.length + inconclusiveChecks.length} requiring officer check`
              : "All evaluated deterministically"}
          </span>
        </div>
      </section>

      {/* 3. KEY DECISION DRIVERS */}
      {verification.reasons && verification.reasons.length > 0 && (
        <section className="bg-surface-container-lowest rounded-xl p-6 shadow-card border border-outline-variant/30 space-y-3">
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2 font-sans">
            <CheckCircle2 className="h-4 w-4 text-primary" />
            <span>Key Decision Drivers</span>
          </h3>
          <ul className="space-y-2.5 text-sm text-on-surface font-sans">
            {verification.reasons.map((reason, idx) => (
              <li key={idx} className="flex items-start gap-2.5">
                <span className="text-primary font-bold text-base leading-none mt-0.5">•</span>
                <span className="leading-relaxed">{reason}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* 4. STRUCTURED FAILED REQUIREMENTS (Stitch Structured Card Design) */}
      {(failedRequirementObjects.length > 0 || dedupedFailedStrings.length > 0) && (
        <section className="space-y-4">
          <h3 className="text-base font-bold text-on-surface font-sans flex items-center gap-2 border-b border-outline-variant/30 pb-2">
            <XCircle className="h-5 w-5 text-error" />
            <span>Failed Requirements ({failedRequirementObjects.length || dedupedFailedStrings.length})</span>
          </h3>

          {failedRequirementObjects.length > 0 ? (
            failedRequirementObjects.map((req, idx) => {
              const reqAny = req as any;
              const requiredVal =
                reqAny.required_value ||
                reqAny.parameters?.required_value ||
                reqAny.parameters?.threshold ||
                req.rule ||
                "Mandatory requirement";
              const detectedVal =
                reqAny.actual_value ||
                reqAny.bidder_value ||
                "No qualifying evidence found";

              return (
                <div
                  key={idx}
                  className="bg-surface-container-lowest rounded-xl p-6 shadow-card border border-red-200 relative overflow-hidden space-y-4"
                >
                  <div className="absolute top-0 left-0 w-1.5 h-full bg-error" />

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="space-y-1">
                      <h4 className="text-base font-bold text-on-surface font-sans">
                        {req.description || req.rule || req.requirement_id}
                      </h4>
                      <div className="text-xs font-mono text-on-surface-variant">
                        Verified by: <span className="font-bold text-on-surface">{req.agent || "COMPLIANCE_AGENT"}</span>
                      </div>
                    </div>
                    <Badge variant="danger" size="md">
                      NOT COMPLIANT
                    </Badge>
                  </div>

                  {/* Comparison Grid: Required vs Detected */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-surface-container-low/70 p-4 rounded-lg border border-outline-variant/25">
                    <div>
                      <span className="text-xs font-sans text-on-surface-variant block mb-1">Required Threshold</span>
                      <div className="text-sm font-semibold text-on-surface font-sans">
                        {typeof requiredVal === "object" ? JSON.stringify(requiredVal) : String(requiredVal)}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs font-sans text-on-surface-variant block mb-1">System Detected</span>
                      <div className="text-sm font-semibold text-error font-sans">
                        {typeof detectedVal === "object" ? JSON.stringify(detectedVal) : String(detectedVal)}
                      </div>
                    </div>
                  </div>

                  {/* Detailed Evidence & Reason */}
                  <div className="space-y-2 text-sm font-sans">
                    <div className="flex items-start gap-2">
                      <Search className="h-4 w-4 text-on-surface-variant shrink-0 mt-0.5" />
                      <div>
                        <span className="text-xs font-semibold text-on-surface-variant block">Evidence Found:</span>
                        <span className="text-on-surface">
                          {req.source_text || (req.evidence_ids && req.evidence_ids.length > 0 ? req.evidence_ids.join(", ") : "No supporting evidence provided")}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-start gap-2">
                      <AlertTriangle className="h-4 w-4 text-error shrink-0 mt-0.5" />
                      <div>
                        <span className="text-xs font-semibold text-error block">Reason for Failure:</span>
                        <span className="text-error font-medium">
                          {req.reason || "Requirement criteria violated during evaluation"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })
          ) : (
            // Fallback for deduplicated failure strings if no structured requirement object attached
            <div className="bg-red-50 text-red-900 rounded-xl p-5 border border-red-300 space-y-3">
              <p className="text-sm font-medium">The following mandatory criteria failed automated verification:</p>
              <ul className="space-y-2 text-sm pl-2">
                {dedupedFailedStrings.map((msg, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <span className="text-red-700 font-bold">•</span>
                    <span>{msg}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* 5. HIGH-CONTRAST MANUAL REVIEW / WARNING SECTION (Stitch High-Contrast Design) */}
      {(unresolvedItems.length > 0 || inconclusiveChecks.length > 0) && (
        <section className="bg-amber-100 border-2 border-amber-600 rounded-xl p-6 shadow-card space-y-4 text-amber-950">
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-6 w-6 text-amber-800 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="text-base font-bold text-amber-950 font-sans tracking-tight">
                  MANUAL REVIEW REQUIRED ({unresolvedItems.length + inconclusiveChecks.length})
                </h3>
                <span className="text-xs font-sans font-bold px-2 py-0.5 bg-amber-200 border border-amber-400 rounded text-amber-900">
                  Procurement Officer Action Required
                </span>
              </div>
              <p className="text-sm text-amber-900 font-sans leading-relaxed">
                Some requirements could not be safely verified automatically and require human procurement officer review before award finalization.
              </p>
            </div>
          </div>

          {/* Nested Requirement Cards */}
          <div className="space-y-3 pt-2">
            {unresolvedItems.map((item, idx) => (
              <div
                key={idx}
                className="bg-white rounded-lg p-4 border border-amber-300 shadow-sm relative overflow-hidden space-y-2"
              >
                <div className="absolute top-0 left-0 w-1.5 h-full bg-amber-600" />
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-bold text-on-surface font-sans">
                    {item.rule || item.requirement_id}: {item.description || "Unresolved Tender Requirement"}
                  </h4>
                  <span className="text-xs font-semibold px-2 py-0.5 bg-amber-100 text-amber-900 rounded border border-amber-300">
                    Pending Officer Verification
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant font-sans leading-relaxed">
                  {item.reason || "Physical document inspection required to validate certificate authenticity."}
                </p>
                {item.source_section && (
                  <div className="text-xs font-mono text-primary pt-1">
                    Tender Reference: Section {item.source_section} {item.source_page ? `(Page ${item.source_page})` : ""}
                  </div>
                )}
              </div>
            ))}

            {inconclusiveChecks.map((check, idx) => (
              <div
                key={`inconclusive-${idx}`}
                className="bg-white rounded-lg p-4 border border-amber-300 shadow-sm relative overflow-hidden space-y-1"
              >
                <div className="absolute top-0 left-0 w-1.5 h-full bg-amber-600" />
                <span className="text-xs font-bold text-amber-900 uppercase tracking-wider block">
                  Inconclusive Check #{idx + 1}
                </span>
                <p className="text-sm text-on-surface font-sans">{check}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 6. WARNINGS & OPERATIONAL OBSERVATIONS */}
      {verification.warnings && verification.warnings.length > 0 && (
        <section className="bg-surface-container-lowest rounded-xl p-5 shadow-card border border-outline-variant/30 space-y-2.5">
          <h4 className="text-xs font-bold font-sans uppercase tracking-wider flex items-center gap-2 text-on-surface-variant">
            <Clock className="h-4 w-4 text-primary" />
            <span>Operational Observations &amp; Warnings ({verification.warnings.length})</span>
          </h4>
          <ul className="space-y-1.5 text-sm text-on-surface font-sans pl-2">
            {verification.warnings.map((w, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-on-surface-variant font-bold">•</span>
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};
