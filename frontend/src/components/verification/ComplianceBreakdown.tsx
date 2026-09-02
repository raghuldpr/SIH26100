import React from "react";
import { RequirementEvaluation } from "../../types";
import { Badge } from "../ui";
import { FileCheck, Layers } from "lucide-react";

export interface ComplianceBreakdownProps {
  requirements: RequirementEvaluation[];
}

export const ComplianceBreakdown: React.FC<ComplianceBreakdownProps> = ({ requirements }) => {
  const getDecisionBadge = (decision: string) => {
    switch (decision?.toUpperCase()) {
      case "COMPLIANT":
        return <Badge variant="success" size="sm" dot>COMPLIANT</Badge>;
      case "NON_COMPLIANT":
        return <Badge variant="danger" size="sm" dot>NON-COMPLIANT</Badge>;
      case "PARTIALLY_COMPLIANT":
        return <Badge variant="warning" size="sm" dot>PARTIAL</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{decision || "UNVERIFIED"}</Badge>;
    }
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
      <div>
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <FileCheck className="h-4 w-4 text-primary" />
          <span>Clause-Level Compliance Evaluations ({requirements?.length || 0})</span>
        </h3>
        <p className="text-xs text-on-surface-variant font-mono mt-0.5">
          Granular deterministic and AI-verified evaluations for each tender requirement
        </p>
      </div>

      {!requirements || requirements.length === 0 ? (
        <div className="text-center py-8 bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <Layers className="h-8 w-8 text-outline mx-auto" />
          <p className="text-xs text-on-surface-variant">
            No requirement-level evaluations recorded for this verification.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {requirements.map((req, idx) => (
            <div
              key={idx}
              className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2 hover:border-primary/40 transition-colors"
            >
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                    {req.rule || req.requirement_id}
                  </span>
                  <Badge variant={req.mandatory ? "danger" : "neutral"} size="sm">
                    {req.mandatory ? "MANDATORY" : "OPTIONAL"}
                  </Badge>
                  {getDecisionBadge(req.decision)}
                </div>

                <div className="flex items-center gap-2 text-[11px] font-mono text-on-surface-variant">
                  {req.agent && <span>Agent: {req.agent}</span>}
                  {req.confidence !== undefined && req.confidence !== null && (
                    <Badge variant="success" size="sm">
                      {Math.round(req.confidence * 100)}% Conf
                    </Badge>
                  )}
                  {req.source_section && (
                    <span className="bg-surface-container px-2 py-0.5 rounded">
                      Section: {req.source_section}
                    </span>
                  )}
                  {req.source_page && (
                    <span className="bg-surface-container px-2 py-0.5 rounded">
                      Page {req.source_page}
                    </span>
                  )}
                </div>
              </div>

              {req.description && (
                <p className="text-xs text-on-surface leading-relaxed">
                  {req.description}
                </p>
              )}

              {req.reason && (
                <div className="p-2.5 rounded-lg bg-surface-container text-xs text-on-surface font-mono">
                  <span className="text-on-surface-variant font-semibold">Evaluation: </span>
                  <span>{req.reason}</span>
                </div>
              )}

              {req.source_text && (
                <div className="p-2 rounded bg-surface-container-lowest border border-outline-variant/20 text-[11px] text-on-surface-variant font-mono italic">
                  &ldquo;{req.source_text}&rdquo;
                </div>
              )}

              {req.findings && req.findings.length > 0 && (
                <ul className="space-y-0.5 text-[11px] text-on-surface font-mono pl-2">
                  {req.findings.map((f, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="text-primary font-bold">•</span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
