import React from "react";
import { Link } from "react-router-dom";
import { BidderResponse } from "../../api/bidders";
import { Badge, Skeleton } from "../ui";
import { Building2, ArrowRight, ShieldCheck, Calendar } from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface RecentActivityProps {
  bidders: BidderResponse[];
  isLoading: boolean;
  maxDisplay?: number;
}

export const RecentActivity: React.FC<RecentActivityProps> = ({
  bidders,
  isLoading,
  maxDisplay = 5,
}) => {
  const displayedBidders = bidders.slice(0, maxDisplay);

  return (
    <div className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
        <div>
          <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
            <Building2 className="h-4 w-4 text-primary" />
            <span>Registered Bidder Entities</span>
          </h2>
          <p className="text-xs text-on-surface-variant font-mono">
            Latest bidder organizations with statutory filings
          </p>
        </div>
        <Link
          to="/bidders"
          className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:text-primary-hover hover:underline"
        >
          <span>View All ({bidders.length})</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="flex items-center justify-between p-3 border-b border-outline-variant/20">
              <div className="space-y-1.5 w-1/2">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
          ))}
        </div>
      ) : displayedBidders.length === 0 ? (
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4">
          No bidder entities registered yet.
        </div>
      ) : (
        <div className="divide-y divide-outline-variant/20">
          {displayedBidders.map((bidder) => (
            <div
              key={bidder.id}
              className="py-3 flex items-center justify-between hover:bg-surface-container-low px-2 rounded-lg transition-colors group cursor-pointer"
            >
              <div className="space-y-0.5 truncate pr-3">
                <div className="text-xs font-semibold text-on-surface group-hover:text-primary transition-colors truncate">
                  {bidder.company_name}
                </div>
                <div className="text-[11px] text-on-surface-variant font-mono flex items-center gap-2">
                  <span>GSTIN: {bidder.gst_number || "—"}</span>
                  {bidder.pan_number && <span>• PAN: {bidder.pan_number}</span>}
                </div>
              </div>

              <div className="flex items-center gap-3 shrink-0">
                <Badge
                  variant={bidder.status === "ACTIVE" ? "success" : "neutral"}
                  size="sm"
                  dot
                >
                  {bidder.status}
                </Badge>
                <div className="hidden sm:flex items-center gap-1 text-[11px] text-on-surface-variant font-mono">
                  <Calendar className="h-3 w-3 text-outline" />
                  <span>{formatDate(bidder.created_at)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="pt-2 border-t border-outline-variant/20 text-center">
        <div className="inline-flex items-center gap-1 text-[11px] text-on-surface-variant font-mono">
          <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
          <span>Statutory Profiles Ready for Forensics &amp; Entity Resolution</span>
        </div>
      </div>
    </div>
  );
};
