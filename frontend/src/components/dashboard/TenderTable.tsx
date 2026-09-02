import React from "react";
import { Link } from "react-router-dom";
import { TenderResponse } from "../../api/tenders";
import { Badge, Button, Skeleton } from "../ui";
import { FileText, ArrowRight, AlertCircle, RefreshCw, Calendar, Building } from "lucide-react";
import { formatCurrencyINR, formatDate } from "../../lib/utils";
import { TenderStatus } from "../../types";

export interface TenderTableProps {
  tenders: TenderResponse[];
  isLoading: boolean;
  error?: string | null;
  onRetry?: () => void;
  maxDisplay?: number;
}

export const TenderTable: React.FC<TenderTableProps> = ({
  tenders,
  isLoading,
  error,
  onRetry,
  maxDisplay = 5,
}) => {
  const getStatusBadge = (status: TenderStatus) => {
    switch (status) {
      case "PUBLISHED":
      case "OPEN":
        return <Badge variant="success" dot size="sm">ACTIVE</Badge>;
      case "EVALUATING":
        return <Badge variant="primary" dot size="sm">EVALUATING</Badge>;
      case "DRAFT":
        return <Badge variant="neutral" dot size="sm">DRAFT</Badge>;
      case "CLOSED":
        return <Badge variant="secondary" size="sm">CLOSED</Badge>;
      case "CANCELLED":
      case "ARCHIVED":
        return <Badge variant="danger" size="sm">{status}</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  const displayedTenders = tenders.slice(0, maxDisplay);

  return (
    <div className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-3 border-b border-outline-variant/20 gap-2">
        <div>
          <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <span>Recent GeM Procurement Tenders</span>
          </h2>
          <p className="text-xs text-on-surface-variant font-mono">
            Active tenders registered for compliance verification
          </p>
        </div>
        <Link
          to="/tenders"
          className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-hover hover:underline"
        >
          <span>View All Tenders ({tenders.length})</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {/* Error State */}
      {error && (
        <div className="p-4 rounded-lg bg-error-container text-error text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-error" />
            <span>{error}</span>
          </div>
          {onRetry && (
            <Button variant="outline" size="sm" onClick={onRetry} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
              Retry
            </Button>
          )}
        </div>
      )}

      {/* Loading Skeleton State */}
      {isLoading && (
        <div className="space-y-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center justify-between p-3 border-b border-outline-variant/20">
              <div className="space-y-1.5 w-1/3">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-6 w-16 rounded-full" />
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && displayedTenders.length === 0 && (
        <div className="text-center py-10 space-y-3 bg-surface-container-low/50 rounded-lg p-6">
          <div className="inline-flex p-3 rounded-full bg-surface-container text-on-surface-variant">
            <FileText className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-on-surface">No procurement tenders found</h3>
            <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
              No tenders have been registered under this organization yet. Create a new tender to begin clause verification.
            </p>
          </div>
          <div className="pt-2">
            <Link to="/tenders">
              <Button variant="primary" size="sm">
                Create First Tender
              </Button>
            </Link>
          </div>
        </div>
      )}

      {/* Data Table */}
      {!isLoading && !error && displayedTenders.length > 0 && (
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-outline-variant/30 text-[11px] font-mono uppercase tracking-wider text-on-surface-variant bg-surface-container-low/40">
                <th className="py-2.5 px-3 rounded-l-md">Tender Reference</th>
                <th className="py-2.5 px-3">Title & Category</th>
                <th className="py-2.5 px-3">Procuring Organization</th>
                <th className="py-2.5 px-3">Est. Value</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3 rounded-r-md">Deadline</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/20">
              {displayedTenders.map((tender) => (
                <tr
                  key={tender.id}
                  className="hover:bg-surface-container-low transition-colors group cursor-pointer"
                >
                  <td className="py-3 px-3 font-mono font-semibold text-primary">
                    <span className="bg-primary/5 px-2 py-1 rounded border border-primary/15 group-hover:border-primary/30 transition-colors">
                      {tender.tender_number}
                    </span>
                  </td>
                  <td className="py-3 px-3 max-w-xs truncate">
                    <div className="font-semibold text-on-surface truncate" title={tender.title}>
                      {tender.title}
                    </div>
                    <div className="text-[11px] text-on-surface-variant font-mono truncate">
                      {tender.category || "General Procurement"}
                      {tender.department ? ` • ${tender.department}` : ""}
                    </div>
                  </td>
                  <td className="py-3 px-3 text-on-surface-variant max-w-[160px] truncate">
                    <div className="flex items-center gap-1.5 truncate" title={tender.organization}>
                      <Building className="h-3.5 w-3.5 text-outline shrink-0" />
                      <span className="truncate">{tender.organization}</span>
                    </div>
                  </td>
                  <td className="py-3 px-3 font-mono font-medium text-on-surface whitespace-nowrap">
                    {formatCurrencyINR(tender.estimated_value)}
                  </td>
                  <td className="py-3 px-3 whitespace-nowrap">
                    {getStatusBadge(tender.status)}
                  </td>
                  <td className="py-3 px-3 text-on-surface-variant font-mono whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      <Calendar className="h-3.5 w-3.5 text-outline shrink-0" />
                      <span>{formatDate(tender.bid_end_date)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
