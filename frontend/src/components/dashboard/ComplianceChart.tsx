import React from "react";
import { TenderResponse } from "../../api/tenders";
import { Skeleton } from "../ui";
import { BarChart3 } from "lucide-react";

export interface ComplianceChartProps {
  tenders: TenderResponse[];
  isLoading: boolean;
}

export const ComplianceChart: React.FC<ComplianceChartProps> = ({ tenders, isLoading }) => {
  // Compute deterministic status distribution from real tenders
  const total = tenders.length;

  const statusCounts = {
    active: tenders.filter((t) => t.status === "OPEN" || t.status === "PUBLISHED").length,
    evaluating: tenders.filter((t) => t.status === "EVALUATING").length,
    draft: tenders.filter((t) => t.status === "DRAFT").length,
    closed: tenders.filter((t) => t.status === "CLOSED" || t.status === "ARCHIVED" || t.status === "CANCELLED").length,
  };

  const chartData = [
    { label: "Active / Published", count: statusCounts.active, color: "bg-primary" },
    { label: "Under Evaluation", count: statusCounts.evaluating, color: "bg-primary-container" },
    { label: "Draft Preparation", count: statusCounts.draft, color: "bg-secondary" },
    { label: "Closed / Archived", count: statusCounts.closed, color: "bg-outline" },
  ];

  return (
    <div className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 flex flex-col justify-between space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
        <div>
          <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            <span>Tender Lifecycle Distribution</span>
          </h2>
          <p className="text-xs text-on-surface-variant font-mono">
            Deterministic status breakdown across {total} registered tenders
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-4 py-4">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
        </div>
      ) : total === 0 ? (
        <div className="text-center py-8 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4">
          No tender lifecycle data available to display.
        </div>
      ) : (
        <div className="space-y-4 py-2">
          {chartData.map((item, idx) => {
            const percentage = total > 0 ? Math.round((item.count / total) * 100) : 0;
            return (
              <div key={idx} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-on-surface">{item.label}</span>
                  <div className="flex items-center gap-2 font-mono">
                    <span className="font-semibold text-on-surface">{item.count}</span>
                    <span className="text-[11px] text-on-surface-variant">({percentage}%)</span>
                  </div>
                </div>
                <div className="h-3 w-full bg-surface-container-high rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500 ease-out ${item.color}`}
                    style={{ width: `${Math.max(percentage, item.count > 0 ? 5 : 0)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div className="pt-3 border-t border-outline-variant/20 flex items-center justify-between text-[11px] font-mono text-on-surface-variant">
        <span>Verified via FastAPI /tenders</span>
        <span className="font-semibold text-primary">{statusCounts.active} Active Procurement Streams</span>
      </div>
    </div>
  );
};
