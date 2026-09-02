import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { listTenders } from "../api/tenders";
import { TenderResponse, TenderStatus } from "../types";
import { Button, Input, Select, Badge, Skeleton } from "../components/ui";
import { CreateTenderModal } from "../components/tenders";
import {
  FileText,
  Plus,
  Search,
  RefreshCw,
  AlertCircle,
  Building,
  Calendar,
  ArrowRight,
} from "lucide-react";
import { formatDate } from "../lib/utils";

export const Tenders: React.FC = () => {
  const navigate = useNavigate();

  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const fetchTenders = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const res = await listTenders({
        page,
        page_size: pageSize,
        status: statusFilter !== "ALL" ? (statusFilter as TenderStatus) : undefined,
        search: searchQuery.trim() || undefined,
      });

      const items = res.data || res.items || [];
      setTenders(items);
      setTotalCount(res.pagination?.total_count ?? res.total ?? items.length);
    } catch (err: any) {
      console.error("Failed to fetch tenders:", err);
      setError(err?.message || "Failed to load tenders list.");
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, statusFilter, searchQuery]);

  useEffect(() => {
    fetchTenders();
  }, [fetchTenders]);

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

  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">
              GeM Procurement Tenders
            </h1>
            <Badge variant="primary" size="sm">
              {totalCount} Total
            </Badge>
          </div>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Manage tender notices, upload NIT documents, and extract compliance criteria
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchTenders}
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
            Create Tender Notice
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle flex flex-col sm:flex-row items-center gap-4">
        <div className="w-full sm:flex-1">
          <Input
            placeholder="Search tender reference, title, organization, or category..."
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
              { value: "ALL", label: "All Lifecycle States" },
              { value: "OPEN", label: "Open / Active" },
              { value: "PUBLISHED", label: "Published on GeM" },
              { value: "EVALUATING", label: "Under Evaluation" },
              { value: "DRAFT", label: "Draft Preparation" },
              { value: "CLOSED", label: "Closed" },
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
          <Button variant="outline" size="sm" onClick={fetchTenders}>
            Retry
          </Button>
        </div>
      )}

      {/* Tenders Table Card */}
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
        ) : tenders.length === 0 ? (
          <div className="text-center py-12 space-y-3 bg-surface-container-low/40 rounded-lg p-6">
            <div className="inline-flex p-3 rounded-full bg-surface-container text-on-surface-variant">
              <FileText className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-on-surface">No procurement tenders found</h3>
              <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
                No tenders match the search criteria. Create a new tender notice to begin.
              </p>
            </div>
            <div className="pt-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsCreateModalOpen(true)}
                leftIcon={<Plus className="h-4 w-4" />}
              >
                Create Tender Notice
              </Button>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto custom-scrollbar">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-outline-variant/30 text-[11px] font-mono uppercase tracking-wider text-on-surface-variant bg-surface-container-low/40">
                  <th className="py-2.5 px-3 rounded-l-md">Tender Reference</th>
                  <th className="py-2.5 px-3">Title & Scope</th>
                  <th className="py-2.5 px-3">Procuring Org</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Deadline</th>
                  <th className="py-2.5 px-3 rounded-r-md text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20">
                {tenders.map((tender) => (
                  <tr
                    key={tender.id}
                    onClick={() => navigate(`/tenders/${tender.id}`)}
                    className="hover:bg-surface-container-low transition-colors group cursor-pointer"
                  >
                    <td className="py-3.5 px-3 font-mono font-semibold text-primary whitespace-nowrap">
                      <span className="bg-primary/5 px-2 py-1 rounded border border-primary/15 group-hover:border-primary/30 transition-colors">
                        {tender.tender_number}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 max-w-xs truncate">
                      <div className="font-semibold text-on-surface group-hover:text-primary transition-colors truncate" title={tender.title}>
                        {tender.title}
                      </div>
                      <div className="text-[11px] text-on-surface-variant font-mono truncate">
                        {tender.department || "General Department"}
                      </div>
                    </td>
                    <td className="py-3.5 px-3 text-on-surface-variant max-w-[160px] truncate">
                      <div className="flex items-center gap-1.5 truncate" title={tender.organization}>
                        <Building className="h-3.5 w-3.5 text-outline shrink-0" />
                        <span className="truncate">{tender.organization}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      <span className="font-mono text-[11px] bg-surface-container px-2 py-0.5 rounded text-on-surface">
                        {tender.category || "Works"}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 whitespace-nowrap">
                      {getStatusBadge(tender.status)}
                    </td>
                    <td className="py-3.5 px-3 text-on-surface-variant font-mono whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="h-3.5 w-3.5 text-outline shrink-0" />
                        <span>{formatDate(tender.bid_end_date)}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-3 text-right whitespace-nowrap">
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-primary group-hover:underline">
                        <span>Details</span>
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
              Showing Page {page} of {totalPages} ({totalCount} total tenders)
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
      <CreateTenderModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onTenderCreated={() => {
          fetchTenders();
        }}
      />
    </div>
  );
};

export default Tenders;
