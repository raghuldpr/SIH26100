import React, { useState } from "react";
import { SystemHealthReport, probeSystemHealth } from "../../api/health";
import { Button, Badge } from "../ui";
import {
  Terminal,
  Play,
  Copy,
  Check,
  Cpu,
  Lock,
  Network,
} from "lucide-react";

export interface ConnectionDiagnosticsProps {
  report: SystemHealthReport | null;
  onRefresh: () => void;
}

export const ConnectionDiagnostics: React.FC<ConnectionDiagnosticsProps> = ({
  report,
  onRefresh,
}) => {
  const [isProbing, setIsProbing] = useState(false);
  const [probeLog, setProbeLog] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const runDiagnosticProbe = async () => {
    setIsProbing(true);
    setProbeLog([`[${new Date().toISOString()}] Initiating System Diagnostics Probe...`]);

    try {
      setProbeLog((prev) => [...prev, "[1/3] Probing FastAPI Core Health (/api/v1/health)..."]);
      const health = await probeSystemHealth();

      setProbeLog((prev) => [
        ...prev,
        `[2/3] Probing Database Connection (/api/v1/health/db)...`,
        `[3/3] Probing n8n Webhook Port & Verification Orchestrator (/api/v1/verification/health)...`,
        `[SUCCESS] Diagnostics Completed. Overall Status: ${health.overallStatus} (${health.summary.onlineCount}/${health.summary.total} Operational).`,
      ]);

      onRefresh();
    } catch (err: any) {
      setProbeLog((prev) => [
        ...prev,
        `[ERROR] Diagnostics probe encountered an error: ${err?.message || "Unknown error"}`,
      ]);
    } finally {
      setIsProbing(false);
    }
  };

  const copyDiagnosticOutput = () => {
    if (report) {
      navigator.clipboard.writeText(JSON.stringify(report, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Diagnostics Actions Bar */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <Network className="h-4 w-4 text-primary" />
              <span>Real-Time Subsystem Connection Diagnostics</span>
            </h3>
            <p className="text-xs text-on-surface-variant font-mono mt-0.5">
              Probe live API gateways, verify HMAC authorization handshakes, and test database latency
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={copyDiagnosticOutput}
              disabled={!report}
              leftIcon={copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}
            >
              {copied ? "Copied JSON" : "Copy Diagnostic Snapshot"}
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={runDiagnosticProbe}
              isLoading={isProbing}
              leftIcon={<Play className="h-4 w-4" />}
            >
              {isProbing ? "Probing Subsystems..." : "Run Diagnostic Probe"}
            </Button>
          </div>
        </div>

        {/* Live Diagnostics Terminal */}
        {probeLog.length > 0 && (
          <div className="p-4 rounded-xl bg-surface-container text-xs font-mono space-y-1.5 border border-outline-variant/30">
            <div className="flex items-center gap-2 text-[11px] font-bold text-primary pb-1 border-b border-outline-variant/20">
              <Terminal className="h-3.5 w-3.5" />
              <span>Live Diagnostic Log Stream</span>
            </div>
            <div className="space-y-1 text-on-surface-variant text-[11px]">
              {probeLog.map((log, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <span className="text-primary font-bold">&gt;</span>
                  <span>{log}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Technical Specifications Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-2 shadow-subtle">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-on-surface flex items-center gap-1.5">
              <Cpu className="h-4 w-4 text-primary" />
              <span>Multi-Agent Protocols</span>
            </span>
            <Badge variant="primary" size="sm">11 Workflows</Badge>
          </div>
          <p className="text-[11px] text-on-surface-variant font-mono">
            Orchestrated via n8n Master Orchestrator on webhook port 5678 with deterministic state machines.
          </p>
        </div>

        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-2 shadow-subtle">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-on-surface flex items-center gap-1.5">
              <Lock className="h-4 w-4 text-primary" />
              <span>Cryptographic Security</span>
            </span>
            <Badge variant="success" size="sm">Enforced</Badge>
          </div>
          <p className="text-[11px] text-on-surface-variant font-mono">
            HMAC SHA-256 webhook signatures, bcrypt password hashing, and SHA-256 evidence digests.
          </p>
        </div>

        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-2 shadow-subtle">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono text-on-surface flex items-center gap-1.5">
              <Terminal className="h-4 w-4 text-primary" />
              <span>AI Minimal Architecture</span>
            </span>
            <Badge variant="neutral" size="sm">Groq LLaMA-3.3</Badge>
          </div>
          <p className="text-[11px] text-on-surface-variant font-mono">
            Deterministic rules evaluated first. Groq AI Gateway invoked strictly for ambiguous clauses.
          </p>
        </div>
      </div>
    </div>
  );
};
