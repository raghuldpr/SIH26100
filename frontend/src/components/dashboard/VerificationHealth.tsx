import React from "react";
import { Badge, StatusIndicator, Skeleton } from "../ui";
import { ShieldCheck, Cpu, CheckCircle2 } from "lucide-react";

export interface VerificationHealthProps {
  totalBidders: number;
  totalTenders: number;
  isLoading: boolean;
}

export const VerificationHealth: React.FC<VerificationHealthProps> = ({
  totalBidders,
  totalTenders,
  isLoading,
}) => {
  return (
    <div className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 flex flex-col justify-between space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
        <div>
          <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span>Multi-Agent Engine Posture</span>
          </h2>
          <p className="text-xs text-on-surface-variant font-mono">
            10-Agent n8n Master Orchestrator state
          </p>
        </div>
        <StatusIndicator status="online" label="Active" ping />
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-6 space-y-3">
          <Skeleton className="h-32 w-32 rounded-full" />
          <Skeleton className="h-4 w-24" />
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-2 space-y-4">
          {/* Circular Verification Representation matching Stitch */}
          <div className="relative flex items-center justify-center">
            <svg className="w-32 h-32 transform -rotate-90">
              <circle
                cx="64"
                cy="64"
                r="52"
                stroke="currentColor"
                strokeWidth="12"
                className="text-surface-container-high"
                fill="transparent"
              />
              <circle
                cx="64"
                cy="64"
                r="52"
                stroke="currentColor"
                strokeWidth="12"
                strokeDasharray="326.7"
                strokeDashoffset={totalBidders > 0 ? "32.6" : "326.7"}
                strokeLinecap="round"
                className="text-primary transition-all duration-1000 ease-out"
                fill="transparent"
              />
            </svg>
            <div className="absolute flex flex-col items-center justify-center text-center">
              <span className="font-mono text-2xl font-bold text-on-surface">10/10</span>
              <span className="text-[10px] text-on-surface-variant uppercase font-semibold">
                Agents Live
              </span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 w-full text-center">
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/20">
              <span className="text-[11px] text-on-surface-variant block font-medium">Bidders Registered</span>
              <span className="font-mono text-base font-bold text-on-surface">{totalBidders}</span>
            </div>
            <div className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/20">
              <span className="text-[11px] text-on-surface-variant block font-medium">Active Tenders</span>
              <span className="font-mono text-base font-bold text-primary">{totalTenders}</span>
            </div>
          </div>
        </div>
      )}

      <div className="pt-3 border-t border-outline-variant/20 space-y-2">
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1.5 text-on-surface-variant">
            <Cpu className="h-3.5 w-3.5 text-primary" />
            <span>Deterministic Rules</span>
          </span>
          <Badge variant="success" size="sm" dot>
            ENFORCED
          </Badge>
        </div>
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-1.5 text-on-surface-variant">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span>HMAC Webhook Callback</span>
          </span>
          <Badge variant="neutral" size="sm">
            SHA-256
          </Badge>
        </div>
      </div>
    </div>
  );
};
