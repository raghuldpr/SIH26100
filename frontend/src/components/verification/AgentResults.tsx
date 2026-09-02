import React from "react";
import { N8nAgentResult } from "../../types";
import { Badge } from "../ui";
import {
  Bot,
  FileSearch,
  Cpu,
  Layers,
  Info,
} from "lucide-react";

export interface AgentResultsProps {
  agentResults: N8nAgentResult[];
}

export const AgentResults: React.FC<AgentResultsProps> = ({ agentResults }) => {
  const getAgentStatusBadge = (status: string) => {
    const s = status ? status.toUpperCase() : "UNKNOWN";
    switch (s) {
      case "PASS":
      case "VERIFIED":
      case "QUALIFIED":
        return <Badge variant="success" size="sm" dot>PASS</Badge>;
      case "FAIL":
      case "FAILED":
      case "ERROR":
        return <Badge variant="danger" size="sm" dot>FAIL</Badge>;
      case "PARTIAL":
      case "WARNING":
      case "REVIEW":
        return <Badge variant="warning" size="sm" dot>REVIEW / WARNING</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{s}</Badge>;
    }
  };

  const getAgentIcon = (name: string) => {
    switch (name.toUpperCase()) {
      case "GST_AGENT":
      case "PAN_AGENT":
      case "UDYAM_AGENT":
        return <FileSearch className="h-4 w-4 text-primary" />;
      case "DOCUMENT_FORENSICS_AGENT":
        return <Layers className="h-4 w-4 text-primary" />;
      case "FINANCIAL_AGENT":
      case "EXPERIENCE_AGENT":
        return <Cpu className="h-4 w-4 text-primary" />;
      default:
        return <Bot className="h-4 w-4 text-primary" />;
    }
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
      <div>
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <Bot className="h-4 w-4 text-primary" />
          <span>Specialized Verification Agent Matrix ({agentResults?.length || 0})</span>
        </h3>
        <p className="text-xs text-on-surface-variant font-mono mt-0.5">
          Autonomous verification agents reporting statutory, financial, forensic, and eligibility results
        </p>
      </div>

      {!agentResults || agentResults.length === 0 ? (
        <div className="text-center py-8 bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <Info className="h-8 w-8 text-outline mx-auto" />
          <p className="text-xs text-on-surface-variant">
            No agent telemetry returned for this execution.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {agentResults.map((agent, idx) => (
            <div
              key={idx}
              className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-3 hover:border-primary/40 transition-colors"
            >
              {/* Card Header */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 truncate">
                  {getAgentIcon(agent.agent || agent.agent_name || "")}
                  <span className="font-mono text-xs font-bold text-on-surface truncate">
                    {agent.agent || agent.agent_name || "Agent"}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {agent.confidence !== undefined && agent.confidence !== null && (
                    <span className="text-[11px] font-mono text-on-surface-variant">
                      {Math.round(agent.confidence * 100)}%
                    </span>
                  )}
                  {getAgentStatusBadge(agent.status)}
                </div>
              </div>

              {/* Primary Reason */}
              {agent.reason && (
                <p className="text-xs text-on-surface leading-relaxed">
                  {agent.reason}
                </p>
              )}

              {/* Issues / Findings list */}
              {agent.issues && agent.issues.length > 0 && (
                <div className="space-y-1">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant font-semibold">
                    Findings &amp; Discrepancies:
                  </span>
                  <ul className="space-y-0.5 text-xs text-on-surface pl-2 font-mono">
                    {agent.issues.map((issue, i) => (
                      <li key={i} className="flex items-start gap-1.5 text-[11px]">
                        <span className="text-primary font-bold">•</span>
                        <span>{issue}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Verified Evidence Key-Values */}
              {agent.evidence && Object.keys(agent.evidence).length > 0 && (
                <div className="pt-2 border-t border-outline-variant/20 flex flex-wrap gap-1.5">
                  {Object.entries(agent.evidence)
                    .filter(([k]) => !["extracted_text", "raw_data"].includes(k))
                    .slice(0, 4)
                    .map(([key, val]) => (
                      <span
                        key={key}
                        className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-surface-container text-on-surface border border-outline-variant/40"
                      >
                        <span className="text-on-surface-variant font-medium">{key}:</span>
                        <span className="font-bold text-primary">
                          {typeof val === "object" ? JSON.stringify(val).slice(0, 20) : String(val)}
                        </span>
                      </span>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
