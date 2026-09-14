import React, { useState } from "react";
import { DecisionFactorItem } from "../../types";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  AlertCircle,
  FileText,
  Scale,
  Search,
} from "lucide-react";
import { extractHumanReadableValue } from "../../lib/evidenceFormatter";

export interface DecisionFactorsProps {
  factors?: DecisionFactorItem[];
  fallbackReasons?: string[];
}

export const DecisionFactors: React.FC<DecisionFactorsProps> = ({
  factors = [],
  fallbackReasons = [],
}) => {
  const [filter, setFilter] = useState<"all" | "passed" | "failed" | "unresolved" | "warning">("all");

  const getFactorCategory = (
    factor: DecisionFactorItem
  ): "passed" | "failed" | "unresolved" | "warning" => {
    const statusUpper = (factor.status || "").toUpperCase();
    const typeUpper = (factor.type || "").toUpperCase();

    if (
      statusUpper === "PASS" ||
      statusUpper === "PASSED" ||
      statusUpper === "COMPLIANT" ||
      statusUpper === "VERIFIED" ||
      statusUpper === "QUALIFIED" ||
      typeUpper === "PASSED_REQUIREMENT"
    ) {
      return "passed";
    }

    if (
      statusUpper === "FAIL" ||
      statusUpper === "FAILED" ||
      statusUpper === "NON_COMPLIANT" ||
      statusUpper === "ERROR" ||
      statusUpper === "BLOCKED" ||
      typeUpper === "FAILED_REQUIREMENT" ||
      typeUpper === "CRITICAL_AGENT_CONDITION"
    ) {
      return "failed";
    }

    if (
      statusUpper === "UNRESOLVED" ||
      statusUpper === "MANUAL_REVIEW" ||
      statusUpper === "INCONCLUSIVE" ||
      statusUpper === "UNVERIFIED" ||
      statusUpper === "PARTIAL" ||
      statusUpper === "PARTIALLY_COMPLIANT" ||
      typeUpper === "UNRESOLVED_REQUIREMENT" ||
      typeUpper === "UNRESOLVED_AGENT_CONDITION"
    ) {
      return "unresolved";
    }

    return "warning";
  };

  const getCategoryConfig = (category: "passed" | "failed" | "unresolved" | "warning", rawStatus?: string) => {
    switch (category) {
      case "passed":
        return {
          border: "border-emerald-200 dark:border-emerald-800/60",
          barBg: "bg-emerald-600",
          badgeBg: "bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300",
          icon: <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />,
          statusLabel: rawStatus || "PASSED",
        };
      case "failed":
        return {
          border: "border-red-200 dark:border-red-800/60",
          barBg: "bg-error",
          badgeBg: "bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300",
          icon: <XCircle className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />,
          statusLabel: rawStatus || "FAILED",
        };
      case "unresolved":
        return {
          border: "border-amber-300 dark:border-amber-700/60",
          barBg: "bg-amber-600",
          badgeBg: "bg-amber-100 text-amber-900 border-amber-500 shadow-sm dark:bg-amber-950/60 dark:text-amber-200",
          icon: <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />,
          statusLabel: rawStatus || "MANUAL REVIEW",
        };
      case "warning":
      default:
        return {
          border: "border-amber-200 dark:border-amber-800/50",
          barBg: "bg-amber-500",
          badgeBg: "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/30 dark:text-amber-300",
          icon: <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />,
          statusLabel: rawStatus || "WARNING",
        };
    }
  };

  const hasFactors = factors && factors.length > 0;
  const categorizedFactors = (factors || []).map((factor) => ({
    factor,
    category: getFactorCategory(factor),
  }));

  const passedCount = categorizedFactors.filter((f) => f.category === "passed").length;
  const failedCount = categorizedFactors.filter((f) => f.category === "failed").length;
  const unresolvedCount = categorizedFactors.filter((f) => f.category === "unresolved").length;
  const warningCount = categorizedFactors.filter((f) => f.category === "warning").length;

  const filteredFactors = categorizedFactors.filter(({ category }) => {
    if (filter === "all") return true;
    return category === filter;
  });

  return (
    <section className="bg-surface-container-lowest rounded-xl p-5 md:p-6 shadow-subtle border border-outline-variant/30 space-y-4">
      {/* Header and Filter Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-outline-variant/20">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Scale className="h-5 w-5 text-primary shrink-0" />
            <h3 className="text-base font-bold text-on-surface font-sans">
              Decision Factors
            </h3>
            {hasFactors && (
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono">
                {factors.length} {factors.length === 1 ? "factor" : "factors"}
              </span>
            )}
          </div>
          <p className="text-xs text-on-surface-variant font-sans">
            Critical statutory, financial, forensic, and technical criteria directly driving the final qualification verdict.
          </p>
        </div>

        {hasFactors && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setFilter("all")}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                filter === "all"
                  ? "bg-primary text-white"
                  : "bg-surface-container text-on-surface-variant hover:text-on-surface"
              }`}
            >
              All ({factors.length})
            </button>
            {failedCount > 0 && (
              <button
                onClick={() => setFilter("failed")}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "failed"
                    ? "bg-error text-white"
                    : "bg-rose-50 text-rose-800 hover:bg-rose-100 border border-rose-200"
                }`}
              >
                Failed ({failedCount})
              </button>
            )}
            {unresolvedCount > 0 && (
              <button
                onClick={() => setFilter("unresolved")}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "unresolved"
                    ? "bg-amber-700 text-white"
                    : "bg-amber-50 text-amber-900 hover:bg-amber-100 border border-amber-300"
                }`}
              >
                Review ({unresolvedCount})
              </button>
            )}
            {passedCount > 0 && (
              <button
                onClick={() => setFilter("passed")}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "passed"
                    ? "bg-emerald-700 text-white"
                    : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200"
                }`}
              >
                Passed ({passedCount})
              </button>
            )}
            {warningCount > 0 && (
              <button
                onClick={() => setFilter("warning")}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "warning"
                    ? "bg-amber-600 text-white"
                    : "bg-amber-50 text-amber-800 hover:bg-amber-100 border border-amber-200"
                }`}
              >
                Warning ({warningCount})
              </button>
            )}
          </div>
        )}
      </div>

      {/* Factors List */}
      {hasFactors ? (
        filteredFactors.length === 0 ? (
          <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/50 rounded-lg font-sans">
            No factors matching filter &quot;{filter}&quot;.
          </div>
        ) : (
          <div className="space-y-3">
            {filteredFactors.map(({ factor, category }, idx) => {
              const cfg = getCategoryConfig(category, factor.status);
              const titleLabel =
                factor.rule ||
                factor.requirement_id ||
                factor.agent_id ||
                (factor.field ? `${factor.field.replace(/_/g, " ").toUpperCase()} CONSISTENCY` : "CRITERION");

              return (
                <div
                  key={idx}
                  className={`bg-surface-container-lowest rounded-xl p-4 md:p-5 border ${cfg.border} shadow-subtle relative overflow-hidden space-y-3 transition-all`}
                >
                  {/* Left accent bar */}
                  <div className={`absolute top-0 left-0 w-1.5 h-full ${cfg.barBg}`} />

                  {/* Header: Rule/ID, Badges */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-on-surface px-2 py-0.5 rounded bg-surface-container border border-outline-variant/30">
                        {titleLabel}
                      </span>
                      {factor.mandatory && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider bg-surface-container-high text-on-surface">
                          MANDATORY
                        </span>
                      )}
                      {factor.agent_id && factor.agent_id !== titleLabel && (
                        <span className="text-[11px] font-mono text-on-surface-variant">
                          Agent: <strong className="text-on-surface font-semibold">{factor.agent_id}</strong>
                        </span>
                      )}
                    </div>

                    <span
                      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold border shrink-0 ${cfg.badgeBg}`}
                    >
                      {cfg.icon}
                      <span>{cfg.statusLabel}</span>
                    </span>
                  </div>

                  {/* Reason Narrative */}
                  {factor.reason ? (
                    <p className="text-sm font-sans text-on-surface leading-relaxed">
                      {factor.reason}
                    </p>
                  ) : (
                    <p className="text-xs font-sans text-on-surface-variant italic">
                      Criteria evaluated in verification pipeline.
                    </p>
                  )}

                  {/* Evidence Citation Details */}
                  {factor.evidence && factor.evidence.length > 0 && (
                    <div className="space-y-2 pt-1 border-t border-outline-variant/20">
                      <span className="text-[11px] font-mono uppercase tracking-wider text-on-surface-variant flex items-center gap-1">
                        <Search className="h-3 w-3" />
                        <span>Supporting Evidence Citations</span>
                      </span>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {factor.evidence.map((ev, evIdx) => (
                          <div
                            key={evIdx}
                            className="bg-surface-container-low/60 rounded-lg p-2.5 border border-outline-variant/20 text-xs font-sans space-y-1"
                          >
                            {ev.source_document && (
                              <div className="flex items-center gap-1.5 font-mono text-on-surface truncate">
                                <FileText className="h-3.5 w-3.5 text-primary shrink-0" />
                                <span className="truncate" title={ev.source_document}>
                                  {ev.source_document}
                                </span>
                                {ev.page_number !== null && ev.page_number !== undefined && (
                                  <span className="text-on-surface-variant shrink-0 font-normal">
                                    (Page {ev.page_number})
                                  </span>
                                )}
                              </div>
                            )}

                            {(ev.detected_value !== undefined || ev.expected_value !== undefined) && (
                              <div className="flex items-baseline gap-2 text-[11px] pt-0.5 flex-wrap">
                                {ev.expected_value !== undefined && (
                                  <span className="text-on-surface-variant">
                                    Req: <strong className="font-mono text-on-surface">{extractHumanReadableValue(ev.expected_value, factor.rule || factor.type)}</strong>
                                  </span>
                                )}
                                {ev.detected_value !== undefined && (
                                  <span className="text-on-surface-variant">
                                    Detected:{" "}
                                    <strong
                                      className={`font-mono ${
                                        category === "failed" ? "text-error" : "text-emerald-700 dark:text-emerald-400"
                                      }`}
                                    >
                                      {extractHumanReadableValue(ev.detected_value, factor.rule || factor.type)}
                                    </strong>
                                  </span>
                                )}
                              </div>
                            )}

                            {ev.detected_value && typeof ev.detected_value === "object" && Object.keys(ev.detected_value).length > 1 && (
                              <details className="mt-1">
                                <summary className="text-[10px] text-primary hover:underline cursor-pointer font-mono select-none">
                                  View Details
                                </summary>
                                <pre className="p-1 bg-black/5 dark:bg-white/5 rounded font-mono text-[9px] overflow-x-auto mt-1 max-h-24 text-on-surface-variant whitespace-pre-wrap">
                                  {JSON.stringify(ev.detected_value, null, 2)}
                                </pre>
                              </details>
                            )}

                            {ev.evidence_text && (
                              <p
                                className="text-[11px] text-on-surface-variant italic truncate"
                                title={typeof ev.evidence_text === "object" ? extractHumanReadableValue(ev.evidence_text) : String(ev.evidence_text)}
                              >
                                &quot;{typeof ev.evidence_text === "object" ? extractHumanReadableValue(ev.evidence_text) : String(ev.evidence_text)}&quot;
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )
      ) : fallbackReasons && fallbackReasons.length > 0 ? (
        /* Fallback to reasons array if decision_factors not populated */
        <div className="space-y-2 pt-1">
          <span className="text-xs font-mono uppercase tracking-wider text-on-surface-variant block">
            Verification Driver Observations
          </span>
          <ul className="space-y-2 text-sm text-on-surface font-sans">
            {fallbackReasons.map((reason, idx) => (
              <li
                key={idx}
                className="flex items-start gap-2.5 p-3 rounded-lg bg-surface-container-low/50 border border-outline-variant/20"
              >
                <span className="text-primary font-bold text-base leading-none mt-0.5">•</span>
                <span className="leading-relaxed">{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        /* Neutral empty state */
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4 font-sans">
          No specific individual decision factors were recorded for this verification run.
        </div>
      )}
    </section>
  );
};

export default DecisionFactors;
