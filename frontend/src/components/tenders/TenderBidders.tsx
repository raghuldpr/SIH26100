import React, { useState, useEffect, useCallback } from "react";
import { listTenderBidders, TenderBidderItem } from "../../api/tenders";
import { Button, Skeleton } from "../ui";
import { Building2, Play } from "lucide-react";
import { Link } from "react-router-dom";
import { formatDate } from "../../lib/utils";

export interface TenderBiddersProps {
  tenderId: string;
}

export const TenderBidders: React.FC<TenderBiddersProps> = ({ tenderId }) => {
  const [bidders, setBidders] = useState<TenderBidderItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchBidders = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listTenderBidders(tenderId);
      setBidders(data);
    } catch (err: any) {
      console.error("Failed to list tender bidders:", err);
    } finally {
      setIsLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    fetchBidders();
  }, [fetchBidders]);

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
        <div>
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <Building2 className="h-4 w-4 text-primary" />
            <span>Assigned Bidders ({bidders.length})</span>
          </h3>
          <p className="text-xs text-on-surface-variant font-mono">
            Bidder organizations enrolled in this tender for compliance verification
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="flex items-center justify-between p-3 border-b border-outline-variant/20">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-6 w-24" />
            </div>
          ))}
        </div>
      ) : bidders.length === 0 ? (
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4">
          No bidders assigned to this tender yet.
        </div>
      ) : (
        <div className="divide-y divide-outline-variant/20">
          {bidders.map((item) => (
            <div
              key={item.id}
              className="py-3 flex items-center justify-between hover:bg-surface-container-low px-2 rounded-lg transition-colors"
            >
              <div className="space-y-0.5 truncate pr-4">
                <div className="text-xs font-semibold text-on-surface flex items-center gap-2 truncate">
                  <Building2 className="h-4 w-4 text-primary shrink-0" />
                  <span className="truncate">{item.company_name || (item as any).bidder?.company_name || "Enrolled Bidder"}</span>
                </div>
                <div className="text-[11px] text-on-surface-variant font-mono flex items-center gap-3">
                  <span>GSTIN: {item.gst_number || (item as any).bidder?.gst_number || "—"}</span>
                  {(item.pan_number || (item as any).bidder?.pan_number) && (
                    <span>• PAN: {item.pan_number || (item as any).bidder?.pan_number}</span>
                  )}
                  <span>• Assigned: {formatDate(item.assignment_timestamp || (item as any).assigned_at)}</span>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Link to={`/verification?tender_id=${tenderId}&bidder_id=${item.bidder_id}`}>
                  <Button variant="primary" size="sm" leftIcon={<Play className="h-3.5 w-3.5" />}>
                    Verify Bid
                  </Button>
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
