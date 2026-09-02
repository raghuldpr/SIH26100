import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { listBidders, BidderResponse } from "../api/bidders";
import { BidderStatus } from "../types";
import { Button, Input, Select, Badge, Skeleton } from "../components/ui";
import { CreateBidderModal } from "../components/bidders";
import {
  Building2,
  Plus,
  Search,
  RefreshCw,
  AlertCircle,
  User,
  ArrowRight,
} from "lucide-react";
import { formatDate } from "../lib/utils";

export const Bidders: React.FC = () => {
  const navigate = useNavigate();

  const [bidders, setBidders] = useState<BidderResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const fetchBidders = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await listBidders({
        page,
        page_size: pageSize,
        status: statusFilter !== "ALL" ? (statusFilter as BidderStatus) : undefined,
        search: searchQuery.trim() || undefined,
      });

      const items = res.data || res.items || [];
      setBidders(items);
      setTotalCount(res.pagination?.total_count ?? res.total ?? items.length);
    } catch (err: any) {
      console.error("Failed to fetch bidders:", err);
      setError(err?.message || "Failed to load registered bidders.");
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, statusFilter, searchQuery]);

  useEffect(() => {
    fetchBidders();
  }, [fetchBidders]);

  const getStatusBadge = (status: BidderStatus) => {
    switch (status) {
      case "ACTIVE":
        return <Badge variant="success" dot size="sm">ACTIVE / ELIGIBLE</Badge>;
      case "INACTIVE":
        return <Badge variant="neutral" dot size="sm">INACTIVE</Badge>;
      case "SUSPENDED":
        return <Badge variant="danger" dot size="sm">SUSPENDED</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">
              Bidder Organization Directory
            </h1>
            <Badge variant="primary" size="sm">
              {totalCount} Total
            </Badge>
          </div>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Manage registered bidder entities, statutory tax identifiers, compliance vaults, and verification history
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchBidders}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsCreateModalOpen(true)}
            leftIcon={<Plus className="h-4 w-4" />}
          >
            Register Bidder Entity
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle flex flex-col sm:flex-row items-center gap-4">
        <div className="w-full sm:flex-1">
          <Input
            placeholder="Search company name, GSTIN, PAN, registration CIN, or email..."
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            leftIcon={<Search className="h-4 w-4" />}
          />
        </div>

        <div className="w-full sm:w-56">
          <Select
            value={statusFilter}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            options={[
              { value: "ALL", label: "All Operational States" },
              { value: "ACTIVE", label: "Active / Eligible" },
              { value: "INACTIVE", label: "Inactive" },
              { value: "SUSPENDED", label: "Suspended" },
            ]}
          />
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-error-container text-error text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchBidders}>
            Retry
          </Button>
        </div>
      )}

      {/* Bidders Table Card */}
      <div className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center justify-between p-3 border-b border-outline-variant/20">
                <div className="space-y-1.5 w-1/3">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-6 w-16 rounded-full" />
              </div>
            ))}
          </div>
        ) : bidders.length === 0 ? (
          <div className="text-center py-12 space-y-3 bg-surface-container-low/40 rounded-lg p-6">
            <div className="inline-flex p-3 rounded-full bg-surface-container text-on-surface-variant">
              <Building2 className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-on-surface">No bidder entities found</h3>
              <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
                No registered bidder entities match the search query. Register a new bidder to begin compliance audits.
              </p>
            </div>
            <div className="pt-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsCreateModalOpen(true)}
                leftIcon={<Plus className="h-4 w-4" />}
              >
                Register Bidder Entity
              </Button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-outline-variant/30 text-[11px] font-mono uppercase tracking-wider text-on-surface-variant bg-surface-container-low/40">
                  <th className="py-2.5 px-3 rounded-l-md">Bidder Organization</th>
                  <th className="py-2.5 px-3">GSTIN</th>
                  <th className="py-2.5 px-3">PAN</th>
                  <th className="py-2.5 px-3">Representative</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Registered Date</th>
                  <th className="py-2.5 px-3 rounded-r-md text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {bidders.map((bidder) => (
                  <tr
                    key={bidder.id}
                    onClick={() => navigate(`/bidders/${bidder.id}`)}
                    className="hover:bg-surface-container-low transition-colors group cursor-pointer"
                  >
                    <td className="py-3.5 px-3">
                      <div className="font-semibold text-on-surface group-hover:text-primary transition-colors flex items-center gap-2">
                        <Building2 className="h-4 w-4 text-primary shrink-0" />
                        <span className="truncate max-w-xs">{bidder.company_name}</span>
                      </div>
                      {bidder.registration_number && (
                        <div className="text-[11px] text-on-surface-variant font-mono pl-6 truncate">
                          CIN: {bidder.registration_number}
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-3 font-mono text-on-surface whitespace-nowrap">
                      {bidder.gst_number ? (
                        <span className="bg-surface-container px-2 py-0.5 rounded border border-outline-variant/40">
                          {bidder.gst_number}
                        </span>
                      ) : (
                        <span className="text-outline italic">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-3 font-mono text-on-surface whitespace-nowrap">
                      {bidder.pan_number ? (
                        <span className="bg-surface-container px-2 py-0.5 rounded border border-outline-variant/40">
                          {bidder.pan_number}
                        </span>
                      ) : (
                        <span className="text-outline italic">—</span>
                      )}
                    </td>
                    <td className="py-3.5 px-3 text-on-surface-variant max-w-[160px] truncate">
                      <div className="flex items-center gap-1.5 truncate">
                        <User className="h-3.5 w-3.5 text-outline shrink-0" />
                        <span className="truncate">{bidder.contact_person || bidder.email || "—"}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      {getStatusBadge(bidder.status)}
                    </td>
                    <td className="py-3.5 px-3 text-on-surface-variant font-mono whitespace-nowrap">
                      {formatDate(bidder.created_at)}
                    </td>
                    <td className="py-3.5 px-3 text-right whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary group-hover:underline">
                        <span>Profile</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        {totalCount > pageSize && (
          <div className="flex items-center justify-between pt-4 border-t border-outline-variant/20 text-xs text-on-surface-variant">
            <span>
              Showing Page {page} of {totalPages} ({totalCount} total bidders)
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1 || isLoading}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages || isLoading}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Create Modal */}
      <CreateBidderModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onBidderCreated={() => {
          fetchBidders();
        }}
      />
    </div>
  );
};

export default Bidders;
