import React, { useState } from "react";
import { VerificationResponse } from "../../types";
import { Badge, Progress } from "../ui";
import { DecisionFactors } from "./DecisionFactors";
import { CrossVerification } from "./CrossVerification";
import {
  ShieldCheck,
  AlertTriangle,
  XCircle,
  Hash,
  Copy,
  Check,
  Clock,
  Search,
  FileText,
  Building2,
  CheckCircle2,
  HelpCircle,
  FileSearch,
  AlertOctagon,
  CopyCheck,
} from "lucide-react";
import { formatDate } from "../../lib/utils";
import { extractHumanReadableValue } from "../../lib/evidenceFormatter";

export interface VerificationSummaryProps {
  verification: VerificationResponse;
  tenderReference?: string;
  tenderTitle?: string;
}

export const VerificationSummary: React.FC<VerificationSummaryProps> = ({
  verification,
  tenderReference,
  tenderTitle,
}) => {
  const [isCopiedHash, setIsCopiedHash] = useState(false);
  const [isCopiedId, setIsCopiedId] = useState(false);

  if (!verification) {
    return (
      <div className="text-center py-12 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-8 space-y-3 shadow-subtle">
        <div className="inline-flex p-3 rounded-full bg-surface-container text-on-surface-variant">
          <HelpCircle className="h-8 w-8 text-outline" />
        </div>
        <h3 className="text-base font-bold text-on-surface">Verification Record Unavailable</h3>
        <p className="text-xs text-on-surface-variant font-sans max-w-md mx-auto">
          No verification execution record was provided to render the result overview.
        </p>
      </div>
    );
  }

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
          icon: <ShieldCheck className="h-9 w-9 text-emerald-400" />,
          badge: <Badge variant="success" size="md">QUALIFIED</Badge>,
          title: "QUALIFIED FOR AWARD",
          subtitle: "All mandatory statutory, technical, and financial criteria confirmed.",
        };
      case "NOT_QUALIFIED":
        return {
          bg: "bg-error text-white border-error/40",
          iconBg: "bg-white/20 text-white",
          icon: <XCircle className="h-9 w-9 text-red-200" />,
          badge: <Badge variant="danger" size="md">NOT QUALIFIED</Badge>,
          title: "BIDDER DISQUALIFIED",
          subtitle: "One or more mandatory tender requirements failed verification.",
        };
      case "MANUAL_REVIEW":
      case "CONDITIONALLY_QUALIFIED":
        return {
          bg: "bg-amber-900 text-white border-amber-700",
          iconBg: "bg-amber-500/20 text-amber-300",
          icon: <AlertTriangle className="h-9 w-9 text-amber-300" />,
          badge: <Badge variant="warning" size="md">MANUAL REVIEW REQUIRED</Badge>,
          title: "MANUAL PROCUREMENT REVIEW REQUIRED",
          subtitle: "Automated checks completed; human officer review required for subjective clauses or anomalies.",
        };
      default:
        return {
          bg: "bg-surface-inverse text-white border-outline/30",
          iconBg: "bg-white/10 text-white",
          icon: <ShieldCheck className="h-9 w-9 text-primary-fixed" />,
          badge: <Badge variant="neutral" size="md">{verification.decision || "PENDING"}</Badge>,
          title: `DECISION: ${verification.decision || "PENDING"}`,
          subtitle: `Verification pipeline status: ${verification.status || "PROCESSING"}`,
        };
    }
  };

  const banner = getBannerStyles();

  // Resolved tender reference string
  const displayTenderRef = tenderReference || verification.tender_number;
  const displayTenderTitle = tenderTitle || verification.tender_title;

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

  // Safe Metric Counts using actual response data
  const totalRequirements =
    verification.summary?.total_requirements ??
    (verification.requirements ? verification.requirements.length : undefined);

  const passedRequirementsCount =
    verification.passed_requirements?.length ??
    verification.summary?.compliant ??
    (verification.requirements
      ? verification.requirements.filter(
          (r) => (r.decision || "").toUpperCase() === "COMPLIANT" || (r.status || "").toUpperCase() === "PASS"
        ).length
      : 0);

  const failedRequirementsCount =
    verification.failed_requirements?.length ??
    verification.summary?.non_compliant ??
    (verification.requirements
      ? verification.requirements.filter(
          (r) => (r.decision || "").toUpperCase() === "NON_COMPLIANT" || (r.status || "").toUpperCase() === "FAIL"
        ).length
      : 0);

  const reviewRequirementsCount =
    verification.review_requirements?.length ??
    ((verification.summary?.partially_compliant || 0) + unresolvedItems.length + inconclusiveChecks.length);

  const hasConfidence =
    verification.overall_confidence !== undefined && verification.overall_confidence !== null;
  const confidencePercent = hasConfidence ? Math.round(verification.overall_confidence! * 100) : null;

  return (
    <div className="space-y-6">
      {/* 1. VERIFICATION OUTCOME HERO (Stitch 10-Second Target) */}
      <section className={`rounded-xl p-6 md:p-7 shadow-elevated border relative overflow-hidden transition-all ${banner.bg}`}>
        <div className="absolute top-0 right-0 w-96 h-full bg-gradient-to-l from-white/10 via-white/5 to-transparent pointer-events-none" />

        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 relative z-10">
          <div className="flex items-start gap-4 max-w-3xl">
            <div className={`p-3.5 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${banner.iconBg}`}>
              {banner.icon}
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white font-sans">
                  {banner.title}
                </h2>
                {banner.badge}
              </div>

              <p className="text-sm md:text-base text-white/90 leading-relaxed font-sans font-normal">
                {banner.subtitle}
              </p>

              {/* Context Metadata Line */}
              <div className="pt-2 text-xs md:text-sm text-white/95 flex items-center gap-x-4 gap-y-2 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-4 w-4 text-white/75 shrink-0" />
                  <span>
                    Bidder: <strong className="text-white font-semibold">{verification.bidder_name || "—"}</strong>
                  </span>
                </span>

                {(displayTenderRef || displayTenderTitle) ? (
                  <>
                    <span className="text-white/40">•</span>
                    <span className="flex items-center gap-1.5 max-w-md truncate" title={`${displayTenderRef || ""} ${displayTenderTitle || ""}`}>
                      <FileText className="h-4 w-4 text-white/75 shrink-0" />
                      <span>
                        Tender: <strong className="text-white font-semibold">{displayTenderRef || "—"}</strong>
                        {displayTenderTitle && (
                          <span className="text-white/80 font-normal"> ({displayTenderTitle})</span>
                        )}
                      </span>
                    </span>
                  </>
                ) : verification.tender_id ? (
                  <>
                    <span className="text-white/40">•</span>
                    <span className="flex items-center gap-1.5">
                      <FileText className="h-4 w-4 text-white/75 shrink-0" />
                      <span>
                        Tender ID: <span className="font-mono text-xs text-white/90">{verification.tender_id}</span>
                      </span>
                    </span>
                  </>
                ) : null}

                {(verification.completed_at || verification.created_at) && (
                  <>
                    <span className="text-white/40">•</span>
                    <span className="flex items-center gap-1.5">
                      <Clock className="h-4 w-4 text-white/75 shrink-0" />
                      <span>{formatDate(verification.completed_at || verification.created_at)}</span>
                    </span>
                  </>
                )}
              </div>

              {/* Quick Confidence & Risk Badges in Hero */}
              <div className="pt-2 flex items-center gap-2.5 flex-wrap">
                {hasConfidence && (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/15 text-xs font-semibold text-white backdrop-blur-md border border-white/25 shadow-sm">
                    <span className="text-white/80">Confidence:</span>
                    <span className="font-mono font-bold text-white">{confidencePercent}%</span>
                  </span>
                )}

                {verification.risk_level && (
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold backdrop-blur-md border shadow-sm ${
                      verification.risk_level.toUpperCase() === "LOW"
                        ? "bg-emerald-500/25 text-emerald-100 border-emerald-300/40"
                        : verification.risk_level.toUpperCase() === "MEDIUM"
                        ? "bg-amber-500/25 text-amber-100 border-amber-300/40"
                        : "bg-red-500/30 text-red-100 border-red-300/40"
                    }`}
                  >
                    <span>Risk:</span>
                    <span className="font-mono font-bold uppercase">{verification.risk_level}</span>
                    {verification.risk_score !== undefined && (
                      <span className="font-mono text-[11px] opacity-85">({Math.round(verification.risk_score)}/100)</span>
                    )}
                  </span>
                )}

                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/20 text-xs font-mono text-white/85 border border-white/10">
                  Status: {verification.status || "COMPLETED"}
                </span>
              </div>
            </div>
          </div>

          {/* Verification ID & SHA-256 Digest Box */}
          <div className="bg-black/35 backdrop-blur-md rounded-xl p-4 border border-white/20 w-full lg:w-80 shrink-0 space-y-3 shadow-inner">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-mono uppercase tracking-wider text-white/70">Verification ID</span>
              <div className="flex items-center gap-1.5 font-mono text-xs font-bold text-white">
                <span className="truncate max-w-[160px]" title={verification.verification_id}>
                  {verification.verification_id}
                </span>
                <button
                  onClick={handleCopyId}
                  className="p-1 rounded hover:bg-white/15 text-white/80 hover:text-white transition-colors"
                  title="Copy Verification ID"
                >
                  {isCopiedId ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            {verification.result_hash ? (
              <div className="pt-2.5 border-t border-white/15 space-y-1">
                <span className="text-[11px] font-mono uppercase tracking-wider text-white/70 flex items-center gap-1">
                  <Hash className="h-3 w-3" />
                  <span>Canonical Result SHA-256</span>
                </span>
                <div className="flex items-center justify-between gap-2 font-mono text-xs text-white/90">
                  <span className="truncate max-w-[200px]" title={verification.result_hash}>
                    {verification.result_hash}
                  </span>
                  <button
                    onClick={handleCopyHash}
                    className="p-1 rounded hover:bg-white/15 text-white/80 hover:text-white transition-colors shrink-0"
                    title="Copy Canonical Hash"
                  >
                    {isCopiedHash ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>
            ) : (
              <div className="pt-2.5 border-t border-white/15 text-[11px] font-mono text-white/60 italic">
                Hash unavailable
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 2. DECISION EXPLANATION SECTION (Directly below Hero) */}
      <section className="bg-surface-container-lowest rounded-xl p-5 md:p-6 shadow-subtle border border-outline-variant/30 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-on-surface flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <span>Decision Explanation</span>
          </h3>
          <span className="text-[11px] font-mono text-on-surface-variant px-2 py-0.5 rounded bg-surface-container">
            Deterministic Audit Record
          </span>
        </div>

        {verification.decision_explanation ? (
          <div
            className={`p-4 rounded-lg border-l-4 bg-surface-container-low/40 ${
              decisionUpper === "QUALIFIED"
                ? "border-emerald-600 text-on-surface"
                : decisionUpper === "NOT_QUALIFIED"
                ? "border-error text-on-surface"
                : "border-amber-500 text-on-surface"
            }`}
          >
            <p className="text-sm md:text-base leading-relaxed font-sans font-medium text-on-surface">
              {verification.decision_explanation}
            </p>
          </div>
        ) : (
          <div className="p-4 rounded-lg bg-surface-container-low/50 border border-outline-variant/20 text-on-surface-variant text-sm font-sans italic">
            A detailed explanation is not available for this verification.
          </div>
        )}
      </section>

      {/* 3. SUMMARY METRICS (Executive KPI Grid) */}
      <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
        {/* Metric 1: Verdict */}
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-subtle border border-outline-variant/30 flex flex-col justify-between">
          <span className="text-[11px] font-sans font-semibold text-on-surface-variant uppercase tracking-wider block">
            Final Outcome
          </span>
          <div className="my-2">
            <span
              className={`text-sm font-bold font-sans px-2.5 py-1 rounded-md inline-block ${
                decisionUpper === "QUALIFIED"
                  ? "bg-emerald-100 text-emerald-800"
                  : decisionUpper === "NOT_QUALIFIED"
                  ? "bg-rose-100 text-rose-800"
                  : "bg-amber-100 text-amber-900"
              }`}
            >
              {verification.decision || "PENDING"}
            </span>
          </div>
          <span className="text-[11px] text-on-surface-variant font-mono truncate">
            {verification.status || "—"}
          </span>
        </div>

        {/* Metric 2: Confidence */}
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-subtle border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Confidence
            </span>
            {hasConfidence && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800">
                {confidencePercent! >= 80 ? "High" : confidencePercent! >= 50 ? "Moderate" : "Low"}
              </span>
            )}
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-sans text-primary">
              {hasConfidence ? `${confidencePercent}%` : "—"}
            </div>
            {hasConfidence && (
              <div className="mt-1.5">
                <Progress value={confidencePercent!} variant="primary" size="sm" />
              </div>
            )}
          </div>
          <span className="text-[11px] text-on-surface-variant font-sans">
            AI verification certainty
          </span>
        </div>

        {/* Metric 3: Risk Level */}
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-subtle border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Risk Level
            </span>
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
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
          <div className="my-2">
            <div className="flex items-baseline gap-1 font-sans">
              <span className="text-2xl font-bold text-on-surface">
                {verification.risk_score !== undefined ? Math.round(verification.risk_score) : "—"}
              </span>
              <span className="text-xs text-on-surface-variant font-medium">/ 100</span>
            </div>
            {verification.risk_score !== undefined && (
              <div className="mt-1.5">
                <Progress
                  value={verification.risk_score}
                  variant={verification.risk_score > 60 ? "error" : verification.risk_score > 30 ? "warning" : "success"}
                  size="sm"
                />
              </div>
            )}
          </div>
          <span className="text-[11px] text-on-surface-variant font-sans truncate">
            {verification.risk_score <= 25
              ? "Negligible risk"
              : verification.risk_score <= 60
              ? "Moderate review"
              : "High risk signals"}
          </span>
        </div>

        {/* Metric 4: Total Requirements */}
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-subtle border border-outline-variant/30 flex flex-col justify-between">
          <span className="text-[11px] font-sans font-semibold text-on-surface-variant uppercase tracking-wider block">
            Total Clauses
          </span>
          <div className="my-2">
            <div className="text-2xl font-bold font-sans text-on-surface">
              {totalRequirements !== undefined ? totalRequirements : "—"}
            </div>
          </div>
          <span className="text-[11px] text-on-surface-variant font-sans">
            Tender criteria evaluated
          </span>
        </div>

        {/* Metric 5: Passed Requirements */}
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-subtle border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-sans font-semibold text-emerald-700 uppercase tracking-wider">
              Passed
            </span>
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          </div>
          <div className="my-2">
            <div className="text-2xl font-bold font-sans text-emerald-700">
              {passedRequirementsCount}
            </div>
          </div>
          <span className="text-[11px] text-emerald-600 font-sans">
            Mandatory criteria satisfied
          </span>
        </div>

        {/* Metric 6: Failed & Review */}
        <div className="bg-surface-container-lowest rounded-xl p-4 shadow-subtle border border-outline-variant/30 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-sans font-semibold text-on-surface-variant uppercase tracking-wider">
              Failed / Review
            </span>
            {failedRequirementsCount > 0 ? (
              <XCircle className="h-3.5 w-3.5 text-error" />
            ) : (
              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
            )}
          </div>
          <div className="my-2 flex items-baseline gap-2">
            <span className={`text-2xl font-bold font-sans ${failedRequirementsCount > 0 ? "text-error" : "text-on-surface"}`}>
              {failedRequirementsCount}
            </span>
            <span className="text-xs text-amber-800 font-semibold">
              / {reviewRequirementsCount} rev
            </span>
          </div>
          <span className="text-[11px] text-on-surface-variant font-sans truncate">
            {failedRequirementsCount > 0 ? "Criteria breached" : reviewRequirementsCount > 0 ? "Review items pending" : "Zero blockers"}
          </span>
        </div>
      </section>

      {/* 4. DECISION FACTORS */}
      <DecisionFactors
        factors={verification.decision_factors}
        fallbackReasons={verification.reasons}
      />

      {/* 5. CROSS-VERIFICATION (Multi-document consistency check) */}
      <CrossVerification crossVerification={verification.cross_verification} />

      {/* 6. COMPACT DOCUMENT FORENSICS OVERVIEW (High-level integrity status) */}
      {verification.document_forensics && (
        <section className="bg-surface-container-lowest rounded-xl p-5 shadow-subtle border border-outline-variant/30 space-y-3 font-sans">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <FileSearch className="h-4 w-4 text-primary shrink-0" aria-hidden="true" />
              <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-on-surface">
                Document Forensics Summary
              </h3>
              <span className="text-[11px] font-mono text-on-surface-variant px-2 py-0.5 rounded bg-surface-container">
                {verification.document_forensics.documents?.length || 0} evaluated
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                  verification.document_forensics.overall_status === "CLEAN"
                    ? "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300"
                    : verification.document_forensics.overall_status === "ANOMALY" ||
                      verification.document_forensics.overall_status === "SUSPICIOUS"
                    ? "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300"
                    : "bg-amber-100 text-amber-900 border-amber-400"
                }`}
              >
                {verification.document_forensics.overall_status === "CLEAN" ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-600" aria-hidden="true" />
                ) : verification.document_forensics.overall_status === "ANOMALY" ? (
                  <AlertOctagon className="h-3 w-3 text-rose-600" aria-hidden="true" />
                ) : (
                  <AlertTriangle className="h-3 w-3 text-amber-600" aria-hidden="true" />
                )}
                <span>{verification.document_forensics.overall_status || "UNRESOLVED"}</span>
              </span>
              <span className="text-[11px] font-mono text-on-surface-variant">
                Risk: {verification.document_forensics.overall_risk || "LOW"}
              </span>
            </div>
          </div>

          <p className="text-xs text-on-surface-variant leading-relaxed">
            {verification.document_forensics.summary ||
              (verification.document_forensics.overall_status === "CLEAN"
                ? "Document structure, PDF streams, metadata timestamps, and hashes verified with zero reported anomalies."
                : "Automated analysis identified document structure or formatting items. View the Document Forensics tab for full technical audit.")}
          </p>
        </section>
      )}

      {/* 7. COMPACT DOCUMENT SIMILARITY OVERVIEW */}
      {verification.document_similarity && (
        <section className="bg-surface-container-lowest rounded-xl p-5 shadow-subtle border border-outline-variant/30 space-y-3 font-sans">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <CopyCheck className="h-4 w-4 text-primary shrink-0" aria-hidden="true" />
              <h3 className="text-xs font-bold uppercase tracking-wider font-mono text-on-surface">
                Document Similarity Summary
              </h3>
              <span className="text-[11px] font-mono text-on-surface-variant px-2 py-0.5 rounded bg-surface-container">
                {verification.document_similarity.comparisons?.length || 0} comparisons
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                  verification.document_similarity.overall_status === "EXACT_DUPLICATE"
                    ? "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300"
                    : verification.document_similarity.overall_status === "HIGH_SIMILARITY" ||
                      verification.document_similarity.overall_status === "SIMILARITY_FOUND"
                    ? "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-950/40 dark:text-amber-200"
                    : verification.document_similarity.overall_status === "INSUFFICIENT_REFERENCE_CORPUS"
                    ? "bg-amber-50 text-amber-800 border-amber-300"
                    : "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300"
                }`}
              >
                {verification.document_similarity.overall_status === "EXACT_DUPLICATE" ? (
                  <AlertOctagon className="h-3 w-3 text-rose-600" aria-hidden="true" />
                ) : verification.document_similarity.overall_status === "HIGH_SIMILARITY" ||
                  verification.document_similarity.overall_status === "SIMILARITY_FOUND" ? (
                  <AlertTriangle className="h-3 w-3 text-amber-600" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="h-3 w-3 text-emerald-600" aria-hidden="true" />
                )}
                <span>{verification.document_similarity.overall_status || "LOW_SIMILARITY"}</span>
              </span>
            </div>
          </div>

          <p className="text-xs text-on-surface-variant leading-relaxed">
            {verification.document_similarity.reason ||
              (verification.document_similarity.overall_status === "EXACT_DUPLICATE"
                ? "Cryptographically identical document digests (SHA-256) were identified across submitted files. View the Document Similarity tab for full details."
                : verification.document_similarity.overall_status === "INSUFFICIENT_REFERENCE_CORPUS"
                ? "Insufficient document artifacts were available to conduct pairwise similarity comparisons."
                : "Cryptographic hashes and normalized token overlap analyzed across submitted artifacts.")}
          </p>
        </section>
      )}

      {/* 8. STRUCTURED FAILED REQUIREMENTS (Detailed view for failed criteria) */}
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
                  className="bg-surface-container-lowest rounded-xl p-6 shadow-card border border-red-200 dark:border-red-900/50 relative overflow-hidden space-y-4"
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
                      <div className="text-sm font-semibold text-on-surface font-sans break-words">
                        {extractHumanReadableValue(requiredVal, req.rule || req.description)}
                      </div>
                    </div>
                    <div>
                      <span className="text-xs font-sans text-on-surface-variant block mb-1">System Detected</span>
                      <div className="text-sm font-semibold text-error font-sans break-words">
                        {extractHumanReadableValue(detectedVal, req.rule || req.description)}
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
                          {typeof req.source_text === "object"
                            ? extractHumanReadableValue(req.source_text)
                            : (req.source_text || (req.evidence_ids && req.evidence_ids.length > 0 ? req.evidence_ids.join(", ") : "No supporting evidence provided"))}
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

      {/* 6. HIGH-CONTRAST MANUAL REVIEW / WARNING SECTION */}
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

      {/* 7. WARNINGS & OPERATIONAL OBSERVATIONS */}
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

export default VerificationSummary;
