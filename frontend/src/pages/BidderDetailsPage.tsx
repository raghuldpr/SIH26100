import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getBidder, BidderResponse } from "../api/bidders";
import { Badge, Button, Skeleton } from "../components/ui";
import {
  BidderProfile,
  BidderStatutoryInfo,
  BidderTenders,
  BidderDocuments,
  BidderVerification,
} from "../components/bidders";
import {
  Building2,
  ArrowLeft,
  AlertCircle,
  FileBadge,
  Layers,
  FolderLock,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { formatDate } from "../lib/utils";

type TabType = "overview" | "statutory" | "tenders" | "documents" | "verification";

export const BidderDetailsPage: React.FC = () => {
  const { bidderId } = useParams<{ bidderId: string }>();
  const navigate = useNavigate();

  const [bidder, setBidder] = useState<BidderResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchBidder = useCallback(async () => {
    if (!bidderId) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await getBidder(bidderId);
      setBidder(data);
    } catch (err: any) {
      console.error("Failed to load bidder details:", err);
      setError(err?.message || "Bidder profile not found or could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }, [bidderId]);

  useEffect(() => {
    fetchBidder();
  }, [fetchBidder]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error || !bidder) {
    return (
      <div className="p-8 bg-surface-container-lowest rounded-xl border border-outline-variant/30 text-center space-y-4">
        <AlertCircle className="h-10 w-10 text-error mx-auto" />
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-on-surface">Bidder Not Found</h2>
          <p className="text-xs text-on-surface-variant max-w-md mx-auto">
            {error || "The requested bidder organization profile could not be retrieved."}
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => navigate("/bidders")}>
          Return to Bidder Directory
        </Button>
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ACTIVE":
        return <Badge variant="success" size="md" dot>ACTIVE / ELIGIBLE</Badge>;
      case "INACTIVE":
        return <Badge variant="neutral" size="md" dot>INACTIVE</Badge>;
      case "SUSPENDED":
        return <Badge variant="danger" size="md" dot>SUSPENDED</Badge>;
      default:
        return <Badge variant="neutral" size="md">{status}</Badge>;
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Top Navigation Breadcrumb */}
      <div>
        <Link
          to="/bidders"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant hover:text-primary transition-colors mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Bidder Directory</span>
        </Link>
      </div>

      {/* Bidder Header Banner */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-xs font-bold text-primary bg-primary/10 px-2.5 py-1 rounded border border-primary/25">
                ID: {bidder.id.slice(0, 8)}...
              </span>
              {getStatusBadge(bidder.status)}
              {bidder.udyam_number && (
                <Badge variant="success" size="sm">MSME Udyam Certified</Badge>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-on-surface flex items-center gap-2">
              <Building2 className="h-6 w-6 text-primary" />
              <span>{bidder.company_name}</span>
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-xs text-on-surface-variant font-mono pt-1">
              {bidder.gst_number && (
                <span>GSTIN: <span className="font-semibold text-on-surface">{bidder.gst_number}</span></span>
              )}
              {bidder.pan_number && (
                <span>• PAN: <span className="font-semibold text-on-surface">{bidder.pan_number}</span></span>
              )}
              {bidder.registration_number && (
                <span>• CIN: <span className="font-semibold text-on-surface">{bidder.registration_number}</span></span>
              )}
              <span>• Registered: {formatDate(bidder.created_at)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex border-b border-outline-variant/30 gap-2 overflow-x-auto custom-scrollbar">
        <button
          onClick={() => setActiveTab("overview")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "overview"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <UserCheck className="h-4 w-4" />
          <span>Profile Overview</span>
        </button>

        <button
          onClick={() => setActiveTab("statutory")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "statutory"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <FileBadge className="h-4 w-4" />
          <span>Statutory Info</span>
        </button>

        <button
          onClick={() => setActiveTab("tenders")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "tenders"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <Layers className="h-4 w-4" />
          <span>Associated Tenders</span>
        </button>

        <button
          onClick={() => setActiveTab("documents")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "documents"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <FolderLock className="h-4 w-4" />
          <span>Compliance &amp; Evidence Vault</span>
        </button>

        <button
          onClick={() => setActiveTab("verification")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === "verification"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <ShieldCheck className="h-4 w-4" />
          <span>Verification History</span>
        </button>
      </div>

      {/* Tab Content Panels */}
      {activeTab === "overview" && (
        <BidderProfile bidder={bidder} />
      )}

      {activeTab === "statutory" && (
        <BidderStatutoryInfo bidder={bidder} />
      )}

      {activeTab === "tenders" && (
        <BidderTenders bidderId={bidder.id} />
      )}

      {activeTab === "documents" && (
        <BidderDocuments bidderId={bidder.id} />
      )}

      {activeTab === "verification" && (
        <BidderVerification bidderId={bidder.id} />
      )}
    </div>
  );
};

export default BidderDetailsPage;
