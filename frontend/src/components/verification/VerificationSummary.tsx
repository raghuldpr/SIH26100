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
} from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface VerificationSummaryProps {
  verification: VerificationResponse;
}

export const VerificationSummary: React.FC<VerificationSummaryProps> = ({ verification }) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopyHash = () => {
    if (verification.result_hash) {
      navigator.clipboard.writeText(verification.result_hash);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case "QUALIFIED":
        return <Badge variant="success" size="md">QUALIFIED</Badge>;
      case "CONDITIONALLY_QUALIFIED":
        return <Badge variant="warning" size="md">CONDITIONALLY QUALIFIED</Badge>;
      case "NOT_QUALIFIED":
        return <Badge variant="danger" size="md">NOT QUALIFIED</Badge>;
      case "MANUAL_REVIEW":
        return <Badge variant="primary" size="md">MANUAL REVIEW REQUIRED</Badge>;
      default:
        return <Badge variant="neutral" size="md">{decision}</Badge>;
    }
  };

  const getComplianceBadge = (compliance?: string) => {
    switch (compliance) {
      case "COMPLIANT":
        return <Badge variant="success" size="sm" dot>FULLY COMPLIANT</Badge>;
      case "NON_COMPLIANT":
        return <Badge variant="danger" size="sm" dot>NON-COMPLIANT</Badge>;
      case "PARTIALLY_COMPLIANT":
        return <Badge variant="warning" size="sm" dot>PARTIALLY COMPLIANT</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{compliance || "UNVERIFIED"}</Badge>;
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case "LOW":
        return <Badge variant="success" size="sm">LOW RISK</Badge>;
      case "MEDIUM":
        return <Badge variant="warning" size="sm">MEDIUM RISK</Badge>;
      case "HIGH":
      case "CRITICAL":
        return <Badge variant="danger" size="sm">HIGH RISK</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{risk}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner Card */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-5">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-4 border-b border-outline-variant/20">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded border border-primary/25">
                {verification.verification_id}
              </span>
              {getDecisionBadge(verification.decision)}
              {getComplianceBadge(verification.overall_compliance)}
              {getRiskBadge(verification.risk_level)}
            </div>
            <h2 className="text-xl font-bold tracking-tight text-on-surface flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              <span>Qualification Decision: {verification.decision}</span>
            </h2>
            <div className="text-xs font-mono text-on-surface-variant flex items-center gap-4 flex-wrap pt-0.5">
              <span>Bidder: <span className="font-semibold text-on-surface">{verification.bidder_name}</span></span>
              <span>• Status: <span className="font-semibold text-primary">{verification.status}</span></span>
              <span>• Completed: {formatDate(verification.completed_at || verification.created_at)}</span>
            </div>
          </div>

          {/* Result Hash Pill */}
          {verification.result_hash && (
            <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/30 flex items-center gap-3 shrink-0">
              <div className="space-y-0.5">
                <span className="text-[10px] uppercase tracking-wider font-mono text-on-surface-variant font-bold flex items-center gap-1">
                  <Hash className="h-3 w-3 text-primary" />
                  <span>Canonical Result SHA-256</span>
                </span>
                <span className="font-mono text-xs font-bold text-on-surface block max-w-[220px] truncate" title={verification.result_hash}>
                  {verification.result_hash}
                </span>
              </div>
              <button
                onClick={handleCopyHash}
                className="p-2 rounded-md hover:bg-surface-container text-on-surface-variant hover:text-primary transition-colors"
                title="Copy Canonical Hash"
              >
                {isCopied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          )}
        </div>

        {/* 4 Score Metric Tiles */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/25 space-y-1">
            <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold">Risk Score</span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-on-surface">
                {Math.round(verification.risk_score)}
              </span>
              <span className="text-xs text-on-surface-variant font-mono">/ 100</span>
            </div>
            <Progress
              value={verification.risk_score}
              variant={verification.risk_score > 60 ? "error" : verification.risk_score > 30 ? "warning" : "success"}
              size="sm"
            />
          </div>

          <div className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/25 space-y-1">
            <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold">Overall Confidence</span>
            <div className="text-2xl font-bold font-mono text-primary">
              {verification.overall_confidence !== undefined && verification.overall_confidence !== null
                ? `${Math.round(verification.overall_confidence * 100)}%`
                : "100%"}
            </div>
            <Progress
              value={(verification.overall_confidence ?? 1.0) * 100}
              variant="primary"
              size="sm"
            />
          </div>

          <div className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/25 space-y-1">
            <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold">Agents Reporting</span>
            <div className="text-2xl font-bold font-mono text-on-surface">
              {verification.agent_results?.length || 0}
            </div>
            <span className="text-[11px] font-mono text-emerald-700">Multi-Agent Suite Active</span>
          </div>

          <div className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/25 space-y-1">
            <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold">Requirements Evaluated</span>
            <div className="text-2xl font-bold font-mono text-on-surface">
              {verification.requirements?.length || 0}
            </div>
            <span className="text-[11px] font-mono text-on-surface-variant">
              {verification.failed_requirements?.length || 0} Failed Criteria
            </span>
          </div>
        </div>

        {/* High-level Decision Reasons */}
        {verification.reasons && verification.reasons.length > 0 && (
          <div className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/30 space-y-2">
            <h4 className="text-xs font-bold font-mono uppercase tracking-wider text-on-surface flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-primary" />
              <span>Key Decision Drivers</span>
            </h4>
            <ul className="space-y-1 text-xs text-on-surface pl-2">
              {verification.reasons.map((reason, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="text-primary font-bold">•</span>
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Failed Requirements Notice if any */}
        {verification.failed_requirements && verification.failed_requirements.length > 0 && (
          <div className="p-4 bg-error-container text-error rounded-xl border border-error/20 space-y-2">
            <h4 className="text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-1.5">
              <XCircle className="h-4 w-4 shrink-0" />
              <span>Failed Requirements ({verification.failed_requirements.length})</span>
            </h4>
            <ul className="space-y-1 text-xs pl-2">
              {verification.failed_requirements.map((item, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span>•</span>
                  <span>{typeof item === "string" ? item : JSON.stringify(item)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Warnings / Inconclusive notices */}
        {verification.warnings && verification.warnings.length > 0 && (
          <div className="p-4 bg-amber-50 text-amber-900 rounded-xl border border-amber-200 space-y-2">
            <h4 className="text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-1.5 text-amber-800">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
              <span>Warnings &amp; Non-Fatal Discrepancies ({verification.warnings.length})</span>
            </h4>
            <ul className="space-y-1 text-xs pl-2">
              {verification.warnings.map((w, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span>•</span>
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};
