import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { listTenders, TenderResponse } from "../api/tenders";
import { listBidders, BidderResponse } from "../api/bidders";
import { listAllDocuments } from "../api/documents";
import { listAllVerifications } from "../api/verification";
import { VerificationHistoryItem } from "../types";
import { MetricCard, TenderTable, ComplianceChart, VerificationHealth, RecentActivity } from "../components/dashboard";
import { Button, Badge } from "../components/ui";
import {
  FileText,
  Users,
  Plus,
  RefreshCw,
  Calendar,
  AlertCircle,
  FolderOpen,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";

export const Dashboard: React.FC = () => {
  const { user } = useAuth();

  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [bidders, setBidders] = useState<BidderResponse[]>([]);
  const [totalTendersCount, setTotalTendersCount] = useState<number>(0);
  const [totalBiddersCount, setTotalBiddersCount] = useState<number>(0);
  const [totalDocsCount, setTotalDocsCount] = useState<number>(0);
  const [verifications, setVerifications] = useState<VerificationHistoryItem[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Execute parallel requests against live FastAPI backend
      const [tendersRes, biddersRes, docsRes, verifsRes] = await Promise.all([
        listTenders({ page: 1, page_size: 20 }),
        listBidders({ page: 1, page_size: 20 }),
        listAllDocuments(1, 20).catch(() => ({ total: 0, items: [] })),
        listAllVerifications(50).catch(() => []),
      ]);

      const tenderItems = tendersRes.data || tendersRes.items || [];
      const bidderItems = biddersRes.data || biddersRes.items || [];
      const docsAny = docsRes as any;

      setTenders(tenderItems);
      setBidders(bidderItems);
      setTotalTendersCount(tendersRes.pagination?.total_count ?? tendersRes.total ?? tenderItems.length);
      setTotalBiddersCount(biddersRes.pagination?.total_count ?? biddersRes.total ?? bidderItems.length);
      setTotalDocsCount(docsAny.pagination?.total_count ?? docsAny.total ?? (docsAny.items || []).length);
      setVerifications(Array.isArray(verifsRes) ? verifsRes : []);
    } catch (err: any) {
      console.error("Dashboard data fetch failed:", err);
      setError(err?.message || "Failed to load dashboard metrics from backend.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Deterministically derived metrics from active data
  const activeTenders = tenders.filter((t) => t.status === "OPEN" || t.status === "PUBLISHED");
  const activeTendersCount = activeTenders.length;

  // Compliance summary derived from real verifications
  const qualifiedCount = verifications.filter(
    (v) => v.decision === "QUALIFIED" || v.overall_compliance === "COMPLIANT"
  ).length;
  const manualReviewCount = verifications.filter(
    (v) => v.decision === "MANUAL_REVIEW" || v.decision === "CONDITIONALLY_QUALIFIED"
  ).length;
  const failedCount = verifications.filter(
    (v) => v.decision === "NOT_QUALIFIED" || v.overall_compliance === "NON_COMPLIANT"
  ).length;

  // Current date formatted for header
  const todayFormatted = new Date().toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="space-y-6 font-sans">
      {/* Top Welcome Header & CTAs (Stitch Reference) */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 pb-2">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-on-surface">
              Welcome Back, {user?.name || "Procurement Officer"}
            </h1>
            <Badge variant="primary" size="sm">
              Live Workspace
            </Badge>
          </div>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Here is the real-time compliance posture of your GeM procurement tenders.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center bg-surface-container-lowest px-3.5 py-2 rounded-lg shadow-subtle border border-outline-variant/30 text-xs text-on-surface">
            <Calendar className="h-4 w-4 text-outline mr-2" />
            <span className="font-medium font-mono">{todayFormatted}</span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={loadDashboardData}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Refresh
          </Button>

          <Link to="/tenders">
            <Button variant="primary" size="sm" leftIcon={<Plus className="h-4 w-4" />}>
              Analyze New Tender
            </Button>
          </Link>
        </div>
      </div>

      {/* Global Error Banner if API Fails */}
      {error && (
        <div className="p-4 rounded-xl bg-error-container text-error text-xs flex items-center justify-between gap-3 shadow-subtle animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 text-error" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={loadDashboardData}>
            Retry Connection
          </Button>
        </div>
      )}

      {/* Row 1: 4 Core Metric KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <MetricCard
          title="Active Tenders"
          value={isLoading ? "—" : activeTendersCount}
          subtitle={`Out of ${totalTendersCount} registered tenders`}
          icon={FileText}
          variant="primary"
          isLoading={isLoading}
        />

        <MetricCard
          title="Registered Bidders"
          value={isLoading ? "—" : totalBiddersCount}
          subtitle="Statutory GSTIN / PAN entities"
          icon={Users}
          variant="default"
          isLoading={isLoading}
        />

        <MetricCard
          title="Vault Documents"
          value={isLoading ? "—" : totalDocsCount}
          subtitle="Uploaded NIT & Bidder attachments"
          icon={FolderOpen}
          variant="default"
          isLoading={isLoading}
        />

        <MetricCard
          title="Verification Executions"
          value={isLoading ? "—" : verifications.length}
          subtitle={`${qualifiedCount} Qualified • ${manualReviewCount} Review`}
          icon={ShieldCheck}
          variant={manualReviewCount > 0 ? "warning" : qualifiedCount > 0 ? "success" : "default"}
          isLoading={isLoading}
        />
      </div>

      {/* Compliance Summary Bar */}
      {verifications.length > 0 && (
        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span className="text-xs font-bold uppercase tracking-wider text-on-surface">Compliance Summary</span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            <Badge variant="success" size="sm" dot>
              {qualifiedCount} QUALIFIED
            </Badge>
            <Badge variant="warning" size="sm" dot>
              {manualReviewCount} MANUAL REVIEW
            </Badge>
            <Badge variant={failedCount > 0 ? "danger" : "neutral"} size="sm" dot>
              {failedCount} DISQUALIFIED
            </Badge>
          </div>
        </div>
      )}

      {/* Row 2: Analytics Visualizations (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <ComplianceChart tenders={tenders} isLoading={isLoading} />
        </div>
        <div>
          <VerificationHealth
            totalBidders={totalBiddersCount}
            totalTenders={totalTendersCount}
            isLoading={isLoading}
          />
        </div>
      </div>

      {/* Row 3: Data Tables & Activity (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2">
          <TenderTable
            tenders={tenders}
            isLoading={isLoading}
            error={error}
            onRetry={loadDashboardData}
            maxDisplay={6}
          />
        </div>
        <div>
          <RecentActivity bidders={bidders} isLoading={isLoading} maxDisplay={5} />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
