import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { listBidderTenders } from "../../api/bidders";
import { BidderTenderResponse } from "../../types";
import { Badge, Button, Skeleton } from "../ui";
import { FileText, Building, Calendar, ArrowRight, Play, Layers } from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface BidderTendersProps {
  bidderId: string;
}

export const BidderTenders: React.FC<BidderTendersProps> = ({ bidderId }) => {
  const [tenders, setTenders] = useState<BidderTenderResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchTenders = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listBidderTenders(bidderId);
      setTenders(data);
    } catch (err: any) {
      console.error("Failed to fetch bidder tenders:", err);
    } finally {
      setIsLoading(false);
    }
  }, [bidderId]);

  useEffect(() => {
    fetchTenders();
  }, [fetchTenders]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "PUBLISHED":
      case "OPEN":
        return <Badge variant="success" size="sm" dot>ACTIVE</Badge>;
      case "EVALUATING":
        return <Badge variant="primary" size="sm" dot>EVALUATING</Badge>;
      case "DRAFT":
        return <Badge variant="neutral" size="sm" dot>DRAFT</Badge>;
      case "CLOSED":
        return <Badge variant="secondary" size="sm">CLOSED</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
      <div>
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <Layers className="h-4 w-4 text-primary" />
          <span>Associated Procurement Tenders ({tenders.length})</span>
        </h3>
        <p className="text-xs text-on-surface-variant font-mono mt-0.5">
          Tenders in which this bidder has enrolled or submitted bids
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="p-4 border border-outline-variant/20 rounded-lg space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-4 w-2/3" />
            </div>
          ))}
        </div>
      ) : tenders.length === 0 ? (
        <div className="text-center py-8 bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <FileText className="h-8 w-8 text-outline mx-auto" />
          <p className="text-xs text-on-surface-variant">
            No active tender associations found for this bidder organization.
          </p>
        </div>
      ) : (
        <div className="divide-y divide-outline-variant/20">
          {tenders.map((tender) => (
            <div
              key={tender.id}
              className="py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-surface-container-low px-3 rounded-lg transition-colors"
            >
              <div className="space-y-1 truncate pr-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                    {tender.tender_number}
                  </span>
                  {getStatusBadge(tender.status)}
                  <span className="text-[11px] font-mono bg-surface-container px-2 py-0.5 rounded text-on-surface">
                    {tender.category || "Works"}
                  </span>
                </div>

                <div className="text-xs font-semibold text-on-surface truncate">
                  {tender.title}
                </div>

                <div className="flex items-center gap-3 text-[11px] text-on-surface-variant font-mono">
                  <span className="flex items-center gap-1">
                    <Building className="h-3 w-3 text-outline" />
                    <span>{tender.organization} ({tender.department || "General"})</span>
                  </span>
                  {tender.bid_end_date && (
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3 text-outline" />
                      <span>Deadline: {formatDate(tender.bid_end_date)}</span>
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Link to={`/verification?tender_id=${tender.id}&bidder_id=${bidderId}`}>
                  <Button variant="primary" size="sm" leftIcon={<Play className="h-3.5 w-3.5" />}>
                    Verify Bid
                  </Button>
                </Link>

                <Link to={`/tenders/${tender.id}`}>
                  <Button variant="outline" size="sm" rightIcon={<ArrowRight className="h-3.5 w-3.5" />}>
                    Tender Details
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
