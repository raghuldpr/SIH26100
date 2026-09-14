import React, { useState } from "react";
import { VerificationCrossVerification, CrossVerificationCheckItem, CrossVerificationValueItem } from "../../types";
import {
  GitCompare,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  FileText,
  Layers,
  ArrowRight,
} from "lucide-react";

import { extractHumanReadableValue, extractEvidenceProvenance } from "../../lib/evidenceFormatter";

export interface CrossVerificationProps {
  crossVerification?: VerificationCrossVerification | null;
}

export const CrossVerification: React.FC<CrossVerificationProps> = ({
  crossVerification,
}) => {
  const [filter, setFilter] = useState<"all" | "CONSISTENT" | "INCONSISTENT" | "UNRESOLVED">("all");

  // Missing-data behavior: absent or null
  if (!crossVerification) {
    return (
      <section
        aria-labelledby="cross-verification-heading"
        className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 space-y-3"
      >
        <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20">
          <GitCompare className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
          <div>
            <h3 id="cross-verification-heading" className="text-base font-bold text-on-surface font-sans">
              Cross-Verification
            </h3>
            <p className="text-xs text-on-surface-variant font-sans">
              Compares extracted bidder information and credentials across all submitted qualification documents.
            </p>
          </div>
        </div>
        <div className="py-8 text-center bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <HelpCircle className="h-8 w-8 text-outline mx-auto" aria-hidden="true" />
          <h4 className="text-sm font-semibold text-on-surface font-sans">Cross-Verification Unavailable</h4>
          <p className="text-xs text-on-surface-variant font-sans max-w-md mx-auto">
            Cross-verification data is not available for this verification run.
          </p>
        </div>
      </section>
    );
  }

  const overallStatus = (crossVerification.overall_status || "UNRESOLVED").toUpperCase();
  const checks = crossVerification.checks || [];

  const consistentCount = checks.filter((c) => (c.status || "").toUpperCase() === "CONSISTENT").length;
  const inconsistentCount = checks.filter((c) => (c.status || "").toUpperCase() === "INCONSISTENT").length;
  const unresolvedCount = checks.filter((c) => (c.status || "").toUpperCase() === "UNRESOLVED").length;

  const filteredChecks = checks.filter((c) => {
    if (filter === "all") return true;
    return (c.status || "").toUpperCase() === filter;
  });

  const getStatusBadge = (status: string) => {
    const s = (status || "").toUpperCase();
    switch (s) {
      case "CONSISTENT":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            <span>CONSISTENT</span>
          </span>
        );
      case "INCONSISTENT":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300 dark:bg-rose-950/40 dark:text-rose-300">
            <XCircle className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
            <span>INCONSISTENT</span>
          </span>
        );
      case "UNRESOLVED":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-400 dark:bg-amber-950/50 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>UNRESOLVED</span>
          </span>
        );
    }
  };

  const getOverallBanner = () => {
    switch (overallStatus) {
      case "CONSISTENT":
        return {
          bg: "bg-emerald-50 border-emerald-300 text-emerald-950 dark:bg-emerald-950/30 dark:border-emerald-800 dark:text-emerald-200",
          icon: <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />,
          title: "All Cross-Checked Fields Consistent",
          description: "All evaluated identifier credentials, financial figures, and entity details match across the submitted document package.",
        };
      case "INCONSISTENT":
        return {
          bg: "bg-rose-50 border-rose-300 text-rose-950 dark:bg-rose-950/30 dark:border-rose-800 dark:text-rose-200",
          icon: <XCircle className="h-6 w-6 text-rose-600 dark:text-rose-400 shrink-0" aria-hidden="true" />,
          title: "Discrepancies Identified Across Submitted Documents",
          description: "One or more cross-verified fields show conflicting values across separate submitted files, requiring procurement officer verification.",
        };
      case "UNRESOLVED":
      default:
        return {
          bg: "bg-amber-50 border-amber-300 text-amber-950 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-200",
          icon: <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400 shrink-0" aria-hidden="true" />,
          title: "Insufficient Corroborating Evidence",
          description: "Insufficient multi-source document evidence was available across the submitted package to conclusively compare all identifier fields.",
        };
    }
  };

  const banner = getOverallBanner();

  const formatFieldName = (field: string) => {
    const fLower = (field || "").toLowerCase();
    if (fLower === "gstin") return "GSTIN Identifier";
    if (fLower === "pan") return "Permanent Account Number (PAN)";
    if (fLower === "udyam_registration") return "Udyam Registration Number";
    if (fLower === "bidder_name") return "Legal Bidder Entity Name";
    if (fLower === "annual_turnover") return "Annual Turnover (INR)";
    if (fLower === "years_of_experience") return "Years of Technical Experience";
    return field.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const formatDisplayValue = (val: any, field: string): string => {
    return extractHumanReadableValue(val, field);
  };

  const isMonospaceField = (field: string): boolean => {
    const f = (field || "").toLowerCase();
    return f === "gstin" || f === "pan" || f === "udyam_registration" || f.includes("id") || f.includes("code");
  };

  return (
    <section
      aria-labelledby="cross-verification-heading"
      className="bg-surface-container-lowest rounded-xl p-5 md:p-6 shadow-subtle border border-outline-variant/30 space-y-5 font-sans"
    >
      {/* 1. Header & Description */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-outline-variant/20">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <GitCompare className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
            <h3 id="cross-verification-heading" className="text-base font-bold text-on-surface">
              Cross-Verification
            </h3>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono">
              {checks.length} {checks.length === 1 ? "check" : "checks"}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            Compares extracted bidder information, registration credentials, and financial metrics across available documents to verify data consistency across sources.
          </p>
        </div>

        {/* Filter Controls */}
        {checks.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setFilter("all")}
              aria-label={`Filter all ${checks.length} checks`}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                filter === "all"
                  ? "bg-primary text-white"
                  : "bg-surface-container text-on-surface-variant hover:text-on-surface"
              }`}
            >
              All ({checks.length})
            </button>
            {inconsistentCount > 0 && (
              <button
                onClick={() => setFilter("INCONSISTENT")}
                aria-label={`Filter ${inconsistentCount} inconsistent checks`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "INCONSISTENT"
                    ? "bg-error text-white"
                    : "bg-rose-50 text-rose-800 hover:bg-rose-100 border border-rose-200"
                }`}
              >
                Inconsistent ({inconsistentCount})
              </button>
            )}
            {unresolvedCount > 0 && (
              <button
                onClick={() => setFilter("UNRESOLVED")}
                aria-label={`Filter ${unresolvedCount} unresolved checks`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "UNRESOLVED"
                    ? "bg-amber-700 text-white"
                    : "bg-amber-50 text-amber-900 hover:bg-amber-100 border border-amber-300"
                }`}
              >
                Unresolved ({unresolvedCount})
              </button>
            )}
            {consistentCount > 0 && (
              <button
                onClick={() => setFilter("CONSISTENT")}
                aria-label={`Filter ${consistentCount} consistent checks`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "CONSISTENT"
                    ? "bg-emerald-700 text-white"
                    : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200"
                }`}
              >
                Consistent ({consistentCount})
              </button>
            )}
          </div>
        )}
      </div>

      {/* 2. Overall Status Banner */}
      <div className={`p-4 rounded-xl border flex items-start gap-3.5 transition-all ${banner.bg}`}>
        {banner.icon}
        <div className="space-y-1 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h4 className="text-sm font-bold font-sans tracking-tight">
              {banner.title}
            </h4>
            {getStatusBadge(overallStatus)}
          </div>
          <p className="text-xs leading-relaxed opacity-95">
            {banner.description}
          </p>
        </div>
      </div>

      {/* 3. Checks List */}
      {checks.length === 0 ? (
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4 font-sans">
          No cross-verification checks were recorded for this verification run.
        </div>
      ) : filteredChecks.length === 0 ? (
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4 font-sans">
          No cross-verification checks match filter &quot;{filter}&quot;.
        </div>
      ) : (
        <div className="space-y-4">
          {filteredChecks.map((check: CrossVerificationCheckItem, idx: number) => {
            const checkStatus = (check.status || "UNRESOLVED").toUpperCase();
            const values = check.values || [];
            const isMono = isMonospaceField(check.field);

            // Determine border and accent styling for the check card
            const borderClass =
              checkStatus === "CONSISTENT"
                ? "border-emerald-200 dark:border-emerald-800/60"
                : checkStatus === "INCONSISTENT"
                ? "border-red-300 dark:border-red-800/70"
                : "border-amber-300 dark:border-amber-700/60";

            const barBg =
              checkStatus === "CONSISTENT"
                ? "bg-emerald-600"
                : checkStatus === "INCONSISTENT"
                ? "bg-error"
                : "bg-amber-500";

            return (
              <article
                key={check.check_id || idx}
                aria-label={`${formatFieldName(check.field)} verification check`}
                className={`bg-surface-container-lowest rounded-xl p-5 border ${borderClass} shadow-subtle relative overflow-hidden space-y-3.5 transition-all`}
              >
                {/* Left status accent strip */}
                <div className={`absolute top-0 left-0 w-1.5 h-full ${barBg}`} aria-hidden="true" />

                {/* Check Header Line */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-sm text-on-surface font-sans">
                      {formatFieldName(check.field)}
                    </span>
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-surface-container text-on-surface-variant border border-outline-variant/30">
                      {check.check_id}
                    </span>
                  </div>
                  {getStatusBadge(checkStatus)}
                </div>

                {/* Concise neutral backend explanation */}
                {check.reason && (
                  <p className="text-xs text-on-surface-variant font-sans leading-relaxed">
                    {check.reason}
                  </p>
                )}

                {/* Value Comparison Cards Grid */}
                <div className="pt-2 border-t border-outline-variant/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-mono uppercase tracking-wider text-on-surface-variant flex items-center gap-1">
                      <Layers className="h-3 w-3 text-primary" aria-hidden="true" />
                      <span>Gathered Values ({values.length} document {values.length === 1 ? "source" : "sources"})</span>
                    </span>

                    {checkStatus === "CONSISTENT" && values.length > 1 && (
                      <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-400 flex items-center gap-1 font-sans">
                        <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                        <span>Matching across sources</span>
                      </span>
                    )}

                    {checkStatus === "INCONSISTENT" && (
                      <span className="text-[11px] font-semibold text-error flex items-center gap-1 font-sans">
                        <XCircle className="h-3 w-3" aria-hidden="true" />
                        <span>Conflicting values detected</span>
                      </span>
                    )}
                  </div>

                  {values.length === 0 ? (
                    <div className="text-xs text-on-surface-variant italic py-2 bg-surface-container-low/40 rounded p-3">
                      No explicit document value records attached to this check.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {values.map((vItem: CrossVerificationValueItem, vIdx: number) => {
                        const provenance = extractEvidenceProvenance(vItem, vItem.value);
                        const sourceDoc = vItem.source_document || provenance.sourceDocument || "Document Evidence";
                        const pageNum = vItem.page_number ?? provenance.pageNumber;
                        const hasPage = pageNum !== null && pageNum !== undefined && pageNum !== "";
                        const displayVal = formatDisplayValue(vItem.value, check.field);
                        const normVal =
                          vItem.normalized_value !== undefined && vItem.normalized_value !== null
                            ? extractHumanReadableValue(vItem.normalized_value, check.field)
                            : undefined;
                        const showNorm = Boolean(normVal && normVal !== displayVal && normVal !== "—");
                        const rawObj = provenance.rawObject || (typeof vItem.value === "object" ? vItem.value : null);
                        const isComplex = Boolean(rawObj && typeof rawObj === "object" && Object.keys(rawObj).length > 1);

                        return (
                          <div
                            key={vIdx}
                            className={`rounded-lg p-3 border text-xs space-y-1.5 transition-colors ${
                              checkStatus === "CONSISTENT"
                                ? "bg-emerald-50/40 border-emerald-200 dark:bg-emerald-950/20 dark:border-emerald-800/40"
                                : checkStatus === "INCONSISTENT"
                                ? "bg-rose-50/40 border-rose-200 dark:bg-rose-950/20 dark:border-rose-800/40"
                                : "bg-surface-container-low/60 border-outline-variant/30"
                            }`}
                          >
                            {/* Source document line */}
                            <div className="flex items-center gap-1.5 text-on-surface-variant font-mono truncate">
                              <FileText className="h-3.5 w-3.5 text-primary shrink-0" aria-hidden="true" />
                              <span
                                className="truncate font-semibold text-on-surface"
                                title={sourceDoc}
                              >
                                {sourceDoc}
                              </span>
                              {hasPage && (
                                <span className="text-on-surface-variant font-normal shrink-0">
                                  (Page {pageNum})
                                </span>
                              )}
                            </div>

                            {/* Value Display */}
                            <div className="pt-1">
                              <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
                                Extracted Value
                              </span>
                              <div
                                className={`text-sm font-bold break-all pt-0.5 ${
                                  isMono ? "font-mono" : "font-sans"
                                } ${
                                  checkStatus === "INCONSISTENT"
                                    ? "text-error"
                                    : "text-on-surface"
                                }`}
                              >
                                {displayVal}
                              </div>
                            </div>

                            {/* Normalized value if available & distinct */}
                            {showNorm && (
                              <div className="text-[11px] text-on-surface-variant pt-0.5 flex items-center gap-1">
                                <ArrowRight className="h-2.5 w-2.5 text-outline" aria-hidden="true" />
                                <span>Norm:</span>
                                <span className={`font-semibold ${isMono ? "font-mono" : "font-sans"}`}>
                                  {normVal}
                                </span>
                              </div>
                            )}

                            {/* Technical Details for structured objects */}
                            {isComplex && (
                              <details className="pt-1.5 border-t border-outline-variant/20 mt-1">
                                <summary className="text-[10px] text-primary hover:underline cursor-pointer font-mono select-none">
                                  View Technical Details
                                </summary>
                                <pre className="p-1.5 bg-black/5 dark:bg-white/5 rounded font-mono text-[9px] overflow-x-auto mt-1 max-h-36 text-on-surface-variant whitespace-pre-wrap">
                                  {JSON.stringify(rawObj, null, 2)}
                                </pre>
                              </details>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default CrossVerification;
