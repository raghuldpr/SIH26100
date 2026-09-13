import React, { useState, useEffect, useCallback } from "react";
import { listTenderBidders, assignBidderToTender, TenderBidderItem } from "../../api/tenders";
import { listBidders, BidderResponse } from "../../api/bidders";
import { Button, Skeleton, Modal } from "../ui";
import { Building2, Play, UserPlus, AlertCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { formatDate } from "../../lib/utils";

export interface TenderBiddersProps {
  tenderId: string;
}

export const TenderBidders: React.FC<TenderBiddersProps> = ({ tenderId }) => {
  const [bidders, setBidders] = useState<TenderBidderItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAssignModalOpen, setIsAssignModalOpen] = useState(false);
  const [availableBidders, setAvailableBidders] = useState<BidderResponse[]>([]);
  const [selectedBidderId, setSelectedBidderId] = useState<string>("");
  const [isAssigning, setIsAssigning] = useState(false);
  const [assignError, setAssignError] = useState<string | null>(null);

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

  const handleOpenAssignModal = async () => {
    setAssignError(null);
    setIsAssignModalOpen(true);
    try {
      const res = await listBidders({ page: 1, page_size: 50 });
      const items = res.items || res.data || [];
      // Filter out bidders already assigned
      const assignedIds = new Set(bidders.map((b) => b.bidder_id));
      const unassigned = items.filter((b) => !assignedIds.has(b.id));
      setAvailableBidders(unassigned);
      if (unassigned.length > 0) {
        setSelectedBidderId(unassigned[0].id);
      } else {
        setSelectedBidderId("");
      }
    } catch (err: any) {
      setAssignError("Failed to fetch available bidders from directory.");
    }
  };

  const handleAssignBidder = async () => {
    if (!selectedBidderId) return;
    setIsAssigning(true);
    setAssignError(null);
    try {
      await assignBidderToTender(tenderId, selectedBidderId);
      setIsAssignModalOpen(false);
      fetchBidders();
    } catch (err: any) {
      setAssignError(err.response?.data?.detail || "Failed to assign bidder to tender.");
    } finally {
      setIsAssigning(false);
    }
  };

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
        <Button
          variant="secondary"
          size="sm"
          leftIcon={<UserPlus className="h-3.5 w-3.5" />}
          onClick={handleOpenAssignModal}
        >
          Assign Bidder
        </Button>
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
          No bidders assigned to this tender yet. Click &quot;Assign Bidder&quot; above to enroll a bidder.
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

      {/* Assign Bidder Modal */}
      <Modal
        isOpen={isAssignModalOpen}
        onClose={() => setIsAssignModalOpen(false)}
        title="Assign Bidder to Tender"
        description="Select a registered bidder organization to enroll in this tender for compliance verification."
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <Button variant="ghost" size="sm" onClick={() => setIsAssignModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={!selectedBidderId || isAssigning}
              isLoading={isAssigning}
              onClick={handleAssignBidder}
            >
              Enroll Bidder
            </Button>
          </div>
        }
      >
        <div className="space-y-4">
          {assignError && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-2 text-xs text-red-400">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{assignError}</span>
            </div>
          )}

          {availableBidders.length === 0 ? (
            <div className="p-4 text-center text-xs text-on-surface-variant bg-surface-container-low rounded-lg space-y-2">
              <p>No unassigned bidders available in directory.</p>
              <Link to="/bidders">
                <Button variant="secondary" size="sm" className="mt-2">
                  Go to Bidders Directory
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              <label className="text-xs font-semibold text-on-surface">
                Select Bidder Organization
              </label>
              <select
                className="w-full bg-surface-container border border-outline-variant/40 rounded-lg px-3 py-2 text-xs text-on-surface focus:outline-none focus:border-primary"
                value={selectedBidderId}
                onChange={(e) => setSelectedBidderId(e.target.value)}
              >
                {availableBidders.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.company_name} (GST: {b.gst_number || "N/A"})
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-on-surface-variant">
                The selected bidder will be linked to this tender, allowing their submitted documents to be verified against the tender compliance profile.
              </p>
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
};
