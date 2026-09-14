import React from "react";
import { N8nAgentResult } from "../../types";
import { formatAgentEvidenceChips } from "../../lib/evidenceFormatter";
import {
  Bot,
  FileSearch,
  Cpu,
  Layers,
  Info,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
} from "lucide-react";

export interface AgentResultsProps {
  agentResults: N8nAgentResult[];
}

export const AgentResults: React.FC<AgentResultsProps> = ({ agentResults }) => {
  const getAgentStatusBadge = (status: string) => {
    const s = (status || "").toUpperCase();
    switch (s) {
      case "PASS":
      case "VERIFIED":
      case "QUALIFIED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            PASS
          </span>
        );
      case "FAIL":
      case "FAILED":
      case "ERROR":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300 dark:bg-rose-950/40 dark:text-rose-300">
            <XCircle className="h-3.5 w-3.5 text-rose-600" />
            FAIL
          </span>
        );
      case "PARTIAL":
      case "WARNING":
      case "REVIEW":
      case "MANUAL_REVIEW":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-500 dark:bg-amber-950/50 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-700" />
            REVIEW REQUIRED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300">
            <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
            {status || "UNKNOWN"}
          </span>
        );
    }
  };

  const getAgentIcon = (name: string) => {
    const n = name.toUpperCase();
    if (n.includes("GST") || n.includes("PAN") || n.includes("UDYAM")) {
      return <FileSearch className="h-5 w-5 text-primary" />;
    }
    if (n.includes("FORENSIC") || n.includes("DOCUMENT")) {
      return <Layers className="h-5 w-5 text-primary" />;
    }
    if (n.includes("FINANCIAL") || n.includes("EXPERIENCE")) {
      return <Cpu className="h-5 w-5 text-primary" />;
    }
    return <Bot className="h-5 w-5 text-primary" />;
  };

  const formatAgentName = (name: string) => {
    if (!name) return "Autonomous Agent";
    return name
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-outline-variant/20">
        <div>
          <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <span>Specialized Verification Agent Matrix</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
              {agentResults?.length || 0} active agents
            </span>
          </h3>
          <p className="text-xs text-on-surface-variant mt-1">
            Autonomous multi-agent execution telemetry evaluating statutory registries, financials, forensics, and eligibility
          </p>
        </div>
      </div>

      {!agentResults || agentResults.length === 0 ? (
        <div className="text-center py-12 bg-surface-container-low/40 rounded-xl p-6 space-y-2 border border-dashed border-outline-variant/40">
          <Info className="h-10 w-10 text-outline mx-auto" />
          <p className="text-sm font-medium text-on-surface">No agent telemetry recorded</p>
          <p className="text-xs text-on-surface-variant">
            No specialized agent telemetry returned for this execution.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agentResults.map((agent, idx) => {
            const rawName = agent.agent || agent.agent_name || "Agent";
            const displayName = formatAgentName(rawName);

            return (
              <div
                key={idx}
                className="p-5 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-3 hover:border-primary/40 transition-colors shadow-xs"
              >
                {/* Card Header */}
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 truncate">
                    <div className="p-2 rounded-lg bg-surface-container border border-outline-variant/25">
                      {getAgentIcon(rawName)}
                    </div>
                    <div className="truncate">
                      <h4 className="text-sm font-bold text-on-surface truncate">
                        {displayName}
                      </h4>
                      <span className="font-mono text-[11px] text-on-surface-variant">
                        {rawName}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {agent.confidence !== undefined && agent.confidence !== null && (
                      <span className="text-xs font-semibold text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">
                        {Math.round(agent.confidence * 100)}% conf
                      </span>
                    )}
                    {getAgentStatusBadge(agent.status)}
                  </div>
                </div>

                {/* Primary Reason */}
                {agent.reason && (
                  <p className="text-sm text-on-surface leading-relaxed pt-1">
                    {agent.reason}
                  </p>
                )}

                {/* Issues / Findings list */}
                {agent.issues && agent.issues.length > 0 && (
                  <div className="p-3 bg-rose-50/60 dark:bg-rose-950/20 rounded-lg border border-rose-200/50 space-y-1.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-rose-800 dark:text-rose-300">
                      Discrepancies &amp; Findings:
                    </span>
                    <ul className="space-y-1 text-xs text-rose-900 dark:text-rose-200 pl-2">
                      {agent.issues.map((issue, i) => (
                        <li key={i} className="flex items-start gap-1.5 leading-snug">
                          <span className="text-rose-600 font-bold">&bull;</span>
                          <span>{issue}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Verified Evidence Key-Values */}
                {(() => {
                  const chips = formatAgentEvidenceChips(agent.evidence);
                  if (!chips || chips.length === 0) return null;

                  const complexChips = chips.filter(
                    (c) => c.rawDetails && typeof c.rawDetails === "object" && Object.keys(c.rawDetails).length > 1
                  );

                  return (
                    <div className="pt-2 border-t border-outline-variant/20 space-y-1.5">
                      <div className="flex flex-wrap gap-1.5">
                        {chips.slice(0, 5).map((chip) => (
                          <span
                            key={chip.id}
                            className="inline-flex items-center gap-1.5 text-xs font-mono px-2.5 py-1 rounded bg-surface-container text-on-surface border border-outline-variant/30 max-w-full truncate"
                            title={`${chip.label}: ${chip.value}`}
                          >
                            <span className="text-on-surface-variant font-medium shrink-0">{chip.label}:</span>
                            <span className="font-bold text-primary truncate">{chip.value}</span>
                          </span>
                        ))}
                      </div>

                      {complexChips.length > 0 && (
                        <details className="pt-1">
                          <summary className="text-[10px] text-primary hover:underline cursor-pointer font-mono select-none">
                            View Technical Details
                          </summary>
                          <pre className="p-2 bg-black/5 dark:bg-white/5 rounded font-mono text-[9px] overflow-x-auto mt-1 max-h-36 text-on-surface-variant whitespace-pre-wrap">
                            {JSON.stringify(agent.evidence, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  );
                })()}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
