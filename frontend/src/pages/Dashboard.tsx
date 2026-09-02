import React, { useEffect, useState, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { listTenders, TenderResponse } from "../api/tenders";
import { listBidders, BidderResponse } from "../api/bidders";
import { MetricCard, TenderTable, ComplianceChart, VerificationHealth, RecentActivity } from "../components/dashboard";
import { Button, Badge } from "../components/ui";
import {
  FileText,
  Users,
  CheckCircle2,
  Hourglass,
  Plus,
  RefreshCw,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { Link } from "react-router-dom";
import { formatCurrencyINR } from "../lib/utils";

export const Dashboard: React.FC = () => {
  const { user } = useAuth();

  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [bidders, setBidders] = useState<BidderResponse[]>([]);
  const [totalTendersCount, setTotalTendersCount] = useState<number>(0);
  const [totalBiddersCount, setTotalBiddersCount] = useState<number>(0);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Execute parallel requests against live FastAPI backend
      const [tendersRes, biddersRes] = await Promise.all([
        listTenders({ page: 1, page_size: 20 }),
        listBidders({ page: 1, page_size: 20 }),
      ]);

      const tenderItems = tendersRes.data || tendersRes.items || [];
      const bidderItems = biddersRes.data || biddersRes.items || [];

      setTenders(tenderItems);
      setBidders(bidderItems);
      setTotalTendersCount(tendersRes.pagination?.total_count ?? tendersRes.total ?? tenderItems.length);
      setTotalBiddersCount(biddersRes.pagination?.total_count ?? biddersRes.total ?? bidderItems.length);
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
  const evaluatingTenders = tenders.filter((t) => t.status === "EVALUATING");
  const activeTendersCount = activeTenders.length;
  const activeValueSum = activeTenders.reduce((sum, t) => sum + (t.estimated_value || 0), 0);

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

      {/* Row 1: 4 Stitch Metric KPI Cards */}
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
          title="Under Evaluation"
          value={isLoading ? "—" : evaluatingTenders.length}
          subtitle="Multi-agent verification pending"
          icon={Hourglass}
          variant={evaluatingTenders.length > 0 ? "warning" : "default"}
          isLoading={isLoading}
        />

        <MetricCard
          title="Active Tender Value"
          value={isLoading ? "—" : formatCurrencyINR(activeValueSum)}
          subtitle="Cumulative active procurement"
          icon={CheckCircle2}
          variant="success"
          isLoading={isLoading}
        />
      </div>

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
