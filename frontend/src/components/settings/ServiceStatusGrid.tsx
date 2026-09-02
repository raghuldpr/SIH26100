import React from "react";
import { SystemHealthReport } from "../../api/health";
import { SystemHealthCard } from "./SystemHealthCard";
import { Badge, Skeleton } from "../ui";
import { Activity } from "lucide-react";

export interface ServiceStatusGridProps {
  report: SystemHealthReport | null;
  isLoading: boolean;
}

export const ServiceStatusGrid: React.FC<ServiceStatusGridProps> = ({ report, isLoading }) => {
  if (isLoading && !report) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-3">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-1/2" />
              <Skeleton className="h-5 w-16" />
            </div>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-3 w-1/3" />
          </div>
        ))}
      </div>
    );
  }

  if (!report) {
    return (
      <div className="text-center py-8 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-6 text-xs text-on-surface-variant font-mono">
        No service health telemetry available. Click Refresh to probe the system.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Top Banner with overall summary */}
      <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shadow-subtle">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold font-mono uppercase tracking-wider text-on-surface">
                Platform Architecture State
              </span>
              <Badge
                variant={
                  report.overallStatus === "ONLINE"
                    ? "success"
                    : report.overallStatus === "DEGRADED"
                    ? "warning"
                    : "danger"
                }
                size="sm"
                dot
              >
                {report.overallStatus}
              </Badge>
            </div>
            <p className="text-[11px] text-on-surface-variant font-mono">
              Live deterministic status of FastAPI, PostgreSQL, n8n Orchestrator, and Verification Engine
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono">
          <span className="text-emerald-700 font-bold">
            {report.summary.onlineCount} Online
          </span>
          {report.summary.degradedCount > 0 && (
            <span className="text-amber-700 font-bold">
              {report.summary.degradedCount} Degraded
            </span>
          )}
          {report.summary.offlineCount > 0 && (
            <span className="text-rose-700 font-bold">
              {report.summary.offlineCount} Offline
            </span>
          )}
          <span className="text-on-surface-variant">
            ({report.summary.total} Total Services)
          </span>
        </div>
      </div>

      {/* Services Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {report.services.map((service) => (
          <SystemHealthCard key={service.id} service={service} />
        ))}
      </div>
    </div>
  );
};
