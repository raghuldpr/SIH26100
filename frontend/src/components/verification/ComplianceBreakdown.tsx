import React from "react";
import { RequirementEvaluation } from "../../types";
import { FileCheck, Layers, AlertTriangle, CheckCircle2, XCircle, HelpCircle } from "lucide-react";

export interface ComplianceBreakdownProps {
  requirements: RequirementEvaluation[];
}

export const ComplianceBreakdown: React.FC<ComplianceBreakdownProps> = ({ requirements }) => {
  const renderResultBadge = (decision: string) => {
    const d = (decision || "").toUpperCase();
    if (d === "COMPLIANT" || d === "PASS") {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400 shrink-0" />
          PASS
        </span>
      );
    }
    if (d === "NON_COMPLIANT" || d === "FAIL") {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-700">
          <XCircle className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400 shrink-0" />
          FAIL
        </span>
      );
    }
    if (d === "UNRESOLVED" || d === "MANUAL_REVIEW" || d === "INCONCLUSIVE" || d === "UNVERIFIED") {
      return (
        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-amber-100 text-amber-900 border border-amber-500 shadow-sm dark:bg-amber-950/60 dark:text-amber-200 dark:border-amber-600">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-700 dark:text-amber-400 shrink-0" />
          MANUAL REVIEW
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700">
        <HelpCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" />
        {decision || "UNRESOLVED"}
      </span>
    );
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-outline-variant/20">
        <div>
          <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
            <FileCheck className="h-5 w-5 text-primary" />
            <span>Clause-Level Compliance Breakdown</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
              {requirements?.length || 0} evaluated
            </span>
          </h3>
          <p className="text-xs text-on-surface-variant mt-1">
            Systematic criteria evaluation: Requirement &rarr; Evidence &rarr; Required Threshold &rarr; Actual Detected &rarr; Deterministic Result
          </p>
        </div>
      </div>

      {!requirements || requirements.length === 0 ? (
        <div className="text-center py-12 bg-surface-container-low/40 rounded-xl p-6 space-y-2 border border-dashed border-outline-variant/40">
          <Layers className="h-10 w-10 text-outline mx-auto" />
          <p className="text-sm font-medium text-on-surface">No evaluations recorded</p>
          <p className="text-xs text-on-surface-variant">
            No requirement-level evaluations are present for this verification execution.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-outline-variant/25">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-outline-variant/30 bg-surface-container-low/80 text-xs font-semibold text-on-surface-variant tracking-wider uppercase">
                <th className="py-3.5 px-4">Requirement &amp; Rule</th>
                <th className="py-3.5 px-4">Evidence Source</th>
                <th className="py-3.5 px-4">Required Criteria</th>
                <th className="py-3.5 px-4">Actual Detected</th>
                <th className="py-3.5 px-4 text-right">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/20 text-sm">
              {requirements.map((req, idx) => {
                const reqAny = req as any;
                const requiredVal = reqAny.required_value || reqAny.parameters?.required_value || reqAny.parameters?.threshold || (req.rule ? req.rule : "Mandatory clause");
                const actualVal = reqAny.actual_value || reqAny.bidder_value || req.reason || "Evaluated against bidder profile";
                const evidenceText = req.source_text || (req.evidence_ids && req.evidence_ids.length > 0 ? req.evidence_ids.join(", ") : (req.agent ? `Agent: ${req.agent}` : "Bidder Documents"));

                return (
                  <tr key={idx} className="hover:bg-surface-container-low/40 transition-colors">
                    {/* Requirement */}
                    <td className="py-4 px-4 align-top max-w-[260px]">
                      <div className="font-semibold text-on-surface text-sm leading-snug">
                        {req.description || req.rule || req.requirement_id}
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 mt-2">
                        <span className="font-mono text-xs text-primary bg-primary/10 px-2 py-0.5 rounded font-semibold border border-primary/20">
                          {req.rule || req.requirement_id}
                        </span>
                        {req.mandatory && (
                          <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-rose-50 text-rose-700 border border-rose-200">
                            MANDATORY
                          </span>
                        )}
                        {req.confidence !== undefined && req.confidence !== null && (
                          <span className="text-xs text-on-surface-variant font-medium">
                            {Math.round(req.confidence * 100)}% conf
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Evidence */}
                    <td className="py-4 px-4 align-top max-w-[220px]">
                      <p className="text-xs text-on-surface-variant leading-relaxed line-clamp-3" title={evidenceText}>
                        {evidenceText}
                      </p>
                      {req.source_section && (
                        <div className="text-xs text-primary font-medium mt-1">
                          Section: {req.source_section} {req.source_page ? `(p. ${req.source_page})` : ""}
                        </div>
                      )}
                    </td>

                    {/* Required */}
                    <td className="py-4 px-4 align-top max-w-[180px]">
                      <div className="p-2.5 rounded-lg bg-surface-container/70 border border-outline-variant/30 font-mono text-xs text-on-surface leading-relaxed">
                        {typeof requiredVal === "object" ? JSON.stringify(requiredVal) : String(requiredVal)}
                      </div>
                    </td>

                    {/* Actual */}
                    <td className="py-4 px-4 align-top max-w-[220px]">
                      <div className="p-2.5 rounded-lg bg-surface-container/70 border border-outline-variant/30 font-mono text-xs text-on-surface leading-relaxed">
                        {typeof actualVal === "object" ? JSON.stringify(actualVal) : String(actualVal)}
                      </div>
                      {req.findings && req.findings.length > 0 && (
                        <div className="text-xs text-on-surface-variant mt-1.5 space-y-0.5">
                          {req.findings.slice(0, 2).map((finding, fi) => (
                            <p key={fi} className="leading-tight text-xs text-rose-600 font-medium">
                              &bull; {finding}
                            </p>
                          ))}
                        </div>
                      )}
                    </td>

                    {/* Result */}
                    <td className="py-4 px-4 align-top text-right whitespace-nowrap">
                      {renderResultBadge(req.decision)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
