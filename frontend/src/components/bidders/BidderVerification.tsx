import React, { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { listBidderTenders, getBidderVerificationHistory } from "../../api/bidders";
import { BidderTenderResponse, VerificationHistoryItem } from "../../types";
import { Badge, Button, Select, Skeleton } from "../ui";
import { ShieldCheck, Play, ArrowRight } from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface BidderVerificationProps {
  bidderId: string;
}

export const BidderVerification: React.FC<BidderVerificationProps> = ({ bidderId }) => {
  const [tenders, setTenders] = useState<BidderTenderResponse[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string>("");
  const [history, setHistory] = useState<VerificationHistoryItem[]>([]);
  const [isLoadingTenders, setIsLoadingTenders] = useState(true);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  const fetchTenders = useCallback(async () => {
    setIsLoadingTenders(true);
    try {
      const data = await listBidderTenders(bidderId);
      setTenders(data);
      if (data.length > 0) {
        setSelectedTenderId(data[0].id);
      }
    } catch (err: any) {
      console.error("Failed to fetch bidder tenders:", err);
    } finally {
      setIsLoadingTenders(false);
    }
  }, [bidderId]);

  useEffect(() => {
    fetchTenders();
  }, [fetchTenders]);

  const fetchHistory = useCallback(async () => {
    if (!selectedTenderId) {
      setHistory([]);
      return;
    }

    setIsLoadingHistory(true);
    try {
      const data = await getBidderVerificationHistory(selectedTenderId, bidderId);
      setHistory(data);
    } catch (err: any) {
      console.error("Failed to fetch verification history:", err);
      setHistory([]);
    } finally {
      setIsLoadingHistory(false);
    }
  }, [selectedTenderId, bidderId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  const getComplianceBadge = (compliance?: string) => {
    switch (compliance) {
      case "COMPLIANT":
        return <Badge variant="success" size="sm" dot>COMPLIANT</Badge>;
      case "NON_COMPLIANT":
        return <Badge variant="danger" size="sm" dot>NON-COMPLIANT</Badge>;
      case "PARTIALLY_COMPLIANT":
        return <Badge variant="warning" size="sm" dot>PARTIALLY COMPLIANT</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{compliance || "PENDING"}</Badge>;
    }
  };

  const getRiskBadge = (risk?: string) => {
    switch (risk) {
      case "LOW":
        return <Badge variant="success" size="sm">LOW RISK</Badge>;
      case "MEDIUM":
        return <Badge variant="warning" size="sm">MEDIUM RISK</Badge>;
      case "HIGH":
      case "CRITICAL":
        return <Badge variant="danger" size="sm">HIGH RISK</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{risk || "—"}</Badge>;
    }
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span>Multi-Agent Verification Audit History</span>
          </h3>
          <p className="text-xs text-on-surface-variant font-mono mt-0.5">
            Cryptographically audited verification runs for participating tenders
          </p>
        </div>

        {selectedTenderId && (
          <Link to={`/verification?tender_id=${selectedTenderId}&bidder_id=${bidderId}`}>
            <Button variant="primary" size="sm" leftIcon={<Play className="h-3.5 w-3.5" />}>
              Run New Verification
            </Button>
          </Link>
        )}
      </div>

      {isLoadingTenders ? (
        <Skeleton className="h-10 w-full rounded-lg" />
      ) : tenders.length === 0 ? (
        <div className="text-center py-8 bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <p className="text-xs text-on-surface-variant">
            This bidder is not currently enrolled in any procurement tenders.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="w-full sm:w-72">
            <Select
              label="Select Associated Tender"
              value={selectedTenderId}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedTenderId(e.target.value)}
              options={tenders.map((t) => ({
                value: t.id,
                label: `${t.tender_number} - ${t.title.slice(0, 30)}...`,
              }))}
            />
          </div>

          {isLoadingHistory ? (
            <div className="space-y-3 pt-2">
              {[...Array(2)].map((_, i) => (
                <div key={i} className="p-4 border border-outline-variant/20 rounded-lg space-y-2">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ))}
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-8 bg-surface-container-low/40 rounded-lg p-6 space-y-3">
              <ShieldCheck className="h-8 w-8 text-outline mx-auto" />
              <div className="space-y-1">
                <p className="text-xs font-semibold text-on-surface">No verification records found</p>
                <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
                  No automated multi-agent verification has been executed for this bidder on the selected tender.
                </p>
              </div>
              <div className="pt-1">
                <Link to={`/verification?tender_id=${selectedTenderId}&bidder_id=${bidderId}`}>
                  <Button variant="primary" size="sm" leftIcon={<Play className="h-3.5 w-3.5" />}>
                    Launch Multi-Agent Verification
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/20">
              {history.map((item) => (
                <div
                  key={item.verification_id}
                  className="py-3.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-surface-container-low px-3 rounded-lg transition-colors"
                >
                  <div className="space-y-1 truncate pr-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2 py-0.5 rounded border border-primary/20">
                        {item.verification_id}
                      </span>
                      {getComplianceBadge(item.overall_compliance)}
                      {getRiskBadge(item.risk_level)}
                    </div>

                    <div className="text-[11px] text-on-surface-variant font-mono flex items-center gap-3 pt-0.5">
                      <span>Status: {item.status}</span>
                      <span>• Timestamp: {formatDate(item.created_at)}</span>
                      {item.result_hash && (
                        <span className="truncate max-w-[200px]" title={item.result_hash}>
                          • Hash: {item.result_hash.slice(0, 12)}...
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <Link to={`/verification?verification_id=${item.verification_id}`}>
                      <Button variant="outline" size="sm" rightIcon={<ArrowRight className="h-3.5 w-3.5" />}>
                        View Report
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
