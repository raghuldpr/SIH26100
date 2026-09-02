import React, { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { getTender } from "../api/tenders";
import { TenderResponse } from "../types";
import { Badge, Button, Skeleton } from "../components/ui";
import { DocumentIntake, TenderRequirements, TenderBidders } from "../components/tenders";
import {
  FileText,
  Building,
  Calendar,
  ArrowLeft,
  AlertCircle,
  FolderOpen,
  Cpu,
  Users,
  Info,
  Clock,
} from "lucide-react";
import { formatDate } from "../lib/utils";

type TabType = "requirements" | "documents" | "bidders" | "overview";

export const TenderDetailsPage: React.FC = () => {
  const { tenderId } = useParams<{ tenderId: string }>();
  const navigate = useNavigate();

  const [tender, setTender] = useState<TenderResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("requirements");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTender = useCallback(async () => {
    if (!tenderId) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await getTender(tenderId);
      setTender(data);
    } catch (err: any) {
      console.error("Failed to load tender details:", err);
      setError(err?.message || "Tender not found or could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    fetchTender();
  }, [fetchTender]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-28 w-full rounded-xl" />
        <Skeleton className="h-12 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (error || !tender) {
    return (
      <div className="p-8 bg-surface-container-lowest rounded-xl border border-outline-variant/30 text-center space-y-4">
        <AlertCircle className="h-10 w-10 text-error mx-auto" />
        <div className="space-y-1">
          <h2 className="text-lg font-bold text-on-surface">Tender Not Found</h2>
          <p className="text-xs text-on-surface-variant max-w-md mx-auto">
            {error || "The requested procurement tender record could not be retrieved."}
          </p>
        </div>
        <Button variant="primary" size="sm" onClick={() => navigate("/tenders")}>
          Return to Tenders List
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 font-sans">
      {/* Top Navigation Breadcrumb */}
      <div>
        <Link
          to="/tenders"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-on-surface-variant hover:text-primary transition-colors mb-2"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Tenders Registry</span>
        </Link>
      </div>

      {/* Tender Header Banner */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-mono text-base font-bold text-primary bg-primary/10 px-3 py-1 rounded border border-primary/25">
                {tender.tender_number}
              </span>
              <Badge variant="primary" size="md">
                {tender.category || "Works"}
              </Badge>
              <Badge
                variant={tender.status === "OPEN" || tender.status === "PUBLISHED" ? "success" : "neutral"}
                size="md"
                dot
              >
                {tender.status}
              </Badge>
            </div>

            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-on-surface">
              {tender.title}
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-xs text-on-surface-variant font-mono pt-1">
              <span className="flex items-center gap-1.5">
                <Building className="h-4 w-4 text-outline shrink-0" />
                <span>{tender.organization} ({tender.department || "General"})</span>
              </span>

              {tender.bid_end_date && (
                <span className="flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 text-outline shrink-0" />
                  <span>Deadline: {formatDate(tender.bid_end_date)}</span>
                </span>
              )}

              <span className="flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-outline shrink-0" />
                <span>Created: {formatDate(tender.created_at)}</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex border-b border-outline-variant/30 gap-2">
        <button
          onClick={() => setActiveTab("requirements")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "requirements"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <Cpu className="h-4 w-4" />
          <span>Clauses &amp; Intelligence</span>
        </button>

        <button
          onClick={() => setActiveTab("documents")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "documents"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <FolderOpen className="h-4 w-4" />
          <span>Document Vault</span>
        </button>

        <button
          onClick={() => setActiveTab("bidders")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "bidders"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <Users className="h-4 w-4" />
          <span>Enrolled Bidders</span>
        </button>

        <button
          onClick={() => setActiveTab("overview")}
          className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === "overview"
              ? "border-primary text-primary"
              : "border-transparent text-on-surface-variant hover:text-on-surface"
          }`}
        >
          <Info className="h-4 w-4" />
          <span>Tender Scope</span>
        </button>
      </div>

      {/* Tab Content Panels */}
      {activeTab === "requirements" && (
        <TenderRequirements tenderId={tender.id} />
      )}

      {activeTab === "documents" && (
        <DocumentIntake tenderId={tender.id} />
      )}

      {activeTab === "bidders" && (
        <TenderBidders tenderId={tender.id} />
      )}

      {activeTab === "overview" && (
        <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <FileText className="h-4 w-4 text-primary" />
            <span>Scope &amp; Technical Instructions</span>
          </h3>
          <p className="text-xs text-on-surface leading-relaxed whitespace-pre-wrap">
            {tender.description || "No specific detailed description provided for this tender notice."}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4 border-t border-outline-variant/20 text-xs font-mono">
            <div>
              <span className="text-on-surface-variant block">Procurement Category:</span>
              <span className="font-semibold text-on-surface">{tender.category || "Works"}</span>
            </div>
            <div>
              <span className="text-on-surface-variant block">Procuring Entity:</span>
              <span className="font-semibold text-on-surface">{tender.organization}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TenderDetailsPage;
