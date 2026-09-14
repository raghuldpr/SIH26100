import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { listTenders } from "../api/tenders";
import { listBidders } from "../api/bidders";
import {
  runVerification,
  getVerification,
  getVerificationHistory,
  listAllVerifications,
} from "../api/verification";
import {
  TenderResponse,
  BidderResponse,
  VerificationResponse,
  VerificationHistoryItem,
} from "../types";
import { Button, Select, Skeleton, Badge } from "../components/ui";
import {
  VerificationSummary,
  CrossVerification,
  DocumentForensics,
  DocumentSimilarity,
  AgentResults,
  ComplianceBreakdown,
  EvidencePanel,
  VerificationAudit,
} from "../components/verification";
import {
  ShieldCheck,
  Play,
  RefreshCw,
  AlertCircle,
  FileText,
  Building2,
  Layers,
  Activity,
  Printer,
  History,
  Eye,
  GitCompare,
  FileSearch,
  CopyCheck,
} from "lucide-react";
import { formatDate } from "../lib/utils";

type TabType = "summary" | "cross_verification" | "forensics" | "similarity" | "agents" | "clauses" | "evidence" | "audit";

export const Verification: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const urlTenderId = searchParams.get("tender_id") || "";
  const urlBidderId = searchParams.get("bidder_id") || "";
  const urlVerificationId = searchParams.get("verification_id") || "";

  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [bidders, setBidders] = useState<BidderResponse[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string>(urlTenderId);
  const [selectedBidderId, setSelectedBidderId] = useState<string>(urlBidderId);

  const [activeVerification, setActiveVerification] = useState<VerificationResponse | null>(null);
  const [historyItems, setHistoryItems] = useState<VerificationHistoryItem[]>([]);
  const [globalHistory, setGlobalHistory] = useState<VerificationHistoryItem[]>([]);
  const [isLoadingGlobalHistory, setIsLoadingGlobalHistory] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>("summary");

  const [isLoadingDropdowns, setIsLoadingDropdowns] = useState(true);
  const [isLoadingVerification, setIsLoadingVerification] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available tenders and bidders for dropdown selection
  useEffect(() => {
    async function loadDropdowns() {
      setIsLoadingDropdowns(true);
      try {
        const [tendersRes, biddersRes] = await Promise.all([
          listTenders({ page_size: 50 }),
          listBidders({ page_size: 50 }),
        ]);
        const tItems = tendersRes.data || tendersRes.items || [];
        const bItems = biddersRes.data || biddersRes.items || [];
        setTenders(tItems);
        setBidders(bItems);

        if (!selectedTenderId && tItems.length > 0) {
          setSelectedTenderId(tItems[0].id);
        }
        if (!selectedBidderId && bItems.length > 0) {
          setSelectedBidderId(bItems[0].id);
        }
      } catch (err: any) {
        console.error("Failed to load tenders/bidders:", err);
      } finally {
        setIsLoadingDropdowns(false);
      }
    }
    loadDropdowns();
  }, []);

  const loadGlobalHistory = useCallback(async () => {
    setIsLoadingGlobalHistory(true);
    try {
      const items = await listAllVerifications(50);
      setGlobalHistory(items);
    } catch (err: any) {
      console.error("Failed to load global verification history:", err);
    } finally {
      setIsLoadingGlobalHistory(false);
    }
  }, []);

  useEffect(() => {
    loadGlobalHistory();
  }, [loadGlobalHistory]);

  // Fetch verification result by ID or by tender/bidder pair
  const loadVerificationData = useCallback(async () => {
    setError(null);

    // 1. If explicit verification_id in URL, load it directly
    if (urlVerificationId) {
      setIsLoadingVerification(true);
      try {
        const res = await getVerification(urlVerificationId);
        setActiveVerification(res);
        if (res.tender_id) setSelectedTenderId(res.tender_id);
        if (res.bidder_id) setSelectedBidderId(res.bidder_id);
      } catch (err: any) {
        setError(err?.message || "Failed to load verification record.");
        setActiveVerification(null);
      } finally {
        setIsLoadingVerification(false);
      }
      return;
    }

    // 2. Otherwise if tender and bidder selected, check history
    if (selectedTenderId && selectedBidderId) {
      setIsLoadingVerification(true);
      try {
        const hist = await getVerificationHistory(selectedTenderId, selectedBidderId);
        setHistoryItems(hist);

        if (hist.length > 0) {
          // Load latest completed verification
          const latest = hist[0];
          const fullRes = await getVerification(latest.verification_id);
          setActiveVerification(fullRes);
        } else {
          setActiveVerification(null);
        }
      } catch (err: any) {
        console.error("Failed to load verification history:", err);
        setActiveVerification(null);
      } finally {
        setIsLoadingVerification(false);
      }
    }
  }, [urlVerificationId, selectedTenderId, selectedBidderId]);

  useEffect(() => {
    loadVerificationData();
  }, [loadVerificationData]);

  // Execute verification
  const handleExecuteVerification = async () => {
    if (!selectedTenderId || !selectedBidderId) {
      setError("Please select both a Tender and a Bidder organization.");
      return;
    }

    setIsRunning(true);
    setError(null);

    try {
      const response = await runVerification({
        tender_id: selectedTenderId,
        bidder_id: selectedBidderId,
      });
      setActiveVerification(response);
      setSearchParams({
        tender_id: selectedTenderId,
        bidder_id: selectedBidderId,
        verification_id: response.verification_id,
      });
      // Refresh history lists
      const hist = await getVerificationHistory(selectedTenderId, selectedBidderId);
      setHistoryItems(hist);
      loadGlobalHistory();
    } catch (err: any) {
      setError(err?.message || "Multi-agent verification execution failed.");
    } finally {
      setIsRunning(false);
    }
  };

  const handleSelectHistoryItem = async (item: VerificationHistoryItem) => {
    setIsLoadingVerification(true);
    setError(null);
    try {
      const res = await getVerification(item.verification_id);
      setActiveVerification(res);
      if (res.tender_id) setSelectedTenderId(res.tender_id);
      if (res.bidder_id) setSelectedBidderId(res.bidder_id);
      setSearchParams({
        tender_id: res.tender_id || "",
        bidder_id: res.bidder_id || "",
        verification_id: res.verification_id,
      });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err: any) {
      setError("Failed to load selected verification execution details.");
    } finally {
      setIsLoadingVerification(false);
    }
  };

  const currentTender = tenders.find((t) => t.id === selectedTenderId);
  const currentBidder = bidders.find((b) => b.id === selectedBidderId);

  const getDecisionBadge = (decision?: string) => {
    switch (decision?.toUpperCase()) {
      case "QUALIFIED":
        return <Badge variant="success" size="sm">QUALIFIED</Badge>;
      case "CONDITIONALLY_QUALIFIED":
        return <Badge variant="warning" size="sm">CONDITIONAL</Badge>;
      case "NOT_QUALIFIED":
        return <Badge variant="danger" size="sm">NOT QUALIFIED</Badge>;
      case "MANUAL_REVIEW":
        return <Badge variant="primary" size="sm">MANUAL REVIEW</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{decision || "PENDING"}</Badge>;
    }
  };

  const getRiskBadge = (risk?: string) => {
    switch (risk?.toUpperCase()) {
      case "LOW":
        return <span className="text-emerald-400 font-mono text-xs font-semibold">LOW</span>;
      case "MEDIUM":
        return <span className="text-amber-400 font-mono text-xs font-semibold">MEDIUM</span>;
      case "HIGH":
      case "CRITICAL":
        return <span className="text-red-400 font-mono text-xs font-semibold">HIGH</span>;
      default:
        return <span className="text-on-surface-variant font-mono text-xs">{risk || "—"}</span>;
    }
  };

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-on-surface flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-primary" />
            <span>Multi-Agent Verification Center</span>
          </h1>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Execute autonomous 10-agent compliance verification, evaluate statutory rules, and audit cryptographic hashes
          </p>
        </div>

        <div className="flex items-center gap-3">
          {activeVerification && (
            <Link to={`/reports?verification_id=${activeVerification.verification_id}`}>
              <Button variant="outline" size="sm" leftIcon={<Printer className="h-4 w-4" />}>
                View Compliance Report
              </Button>
            </Link>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              loadVerificationData();
              loadGlobalHistory();
            }}
            isLoading={isLoadingVerification || isLoadingGlobalHistory}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Refresh
          </Button>

          <Button
            variant="primary"
            size="sm"
            onClick={handleExecuteVerification}
            isLoading={isRunning}
            disabled={!selectedTenderId || !selectedBidderId || isRunning}
            leftIcon={<Play className="h-4 w-4" />}
          >
            {isRunning ? "Executing 10-Agent Verification..." : "Run Multi-Agent Verification"}
          </Button>
        </div>
      </div>

      {/* Target Tender and Bidder Context Selector */}
      <div className="p-5 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase tracking-wider font-mono text-on-surface flex items-center gap-1.5">
            <Layers className="h-4 w-4 text-primary" />
            <span>Verification Target Context</span>
          </span>
          {historyItems.length > 0 && (
            <span className="text-[11px] font-mono text-on-surface-variant flex items-center gap-1">
              <History className="h-3.5 w-3.5 text-outline" />
              <span>{historyItems.length} Past Executions for Selection</span>
            </span>
          )}
        </div>

        {isLoadingDropdowns ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Skeleton className="h-10 w-full rounded-lg" />
            <Skeleton className="h-10 w-full rounded-lg" />
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <Select
                label="Target Procurement Tender *"
                value={selectedTenderId}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                  setSelectedTenderId(e.target.value);
                  setSearchParams({ tender_id: e.target.value, bidder_id: selectedBidderId });
                }}
                options={tenders.map((t) => ({
                  value: t.id,
                  label: `${t.tender_number} — ${t.title.slice(0, 40)}...`,
                }))}
                disabled={isRunning}
              />
              {currentTender && (
                <div className="text-[11px] font-mono text-on-surface-variant mt-1.5 flex items-center gap-2 truncate">
                  <FileText className="h-3.5 w-3.5 text-outline shrink-0" />
                  <Link to={`/tenders/${currentTender.id}`} className="hover:text-primary hover:underline truncate">
                    {currentTender.organization} ({currentTender.department || "General"})
                  </Link>
                </div>
              )}
            </div>

            <div>
              <Select
                label="Target Bidder Organization *"
                value={selectedBidderId}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
                  setSelectedBidderId(e.target.value);
                  setSearchParams({ tender_id: selectedTenderId, bidder_id: e.target.value });
                }}
                options={bidders.map((b) => ({
                  value: b.id,
                  label: `${b.company_name} (GST: ${b.gst_number || "None"})`,
                }))}
                disabled={isRunning}
              />
              {currentBidder && (
                <div className="text-[11px] font-mono text-on-surface-variant mt-1.5 flex items-center gap-2 truncate">
                  <Building2 className="h-3.5 w-3.5 text-outline shrink-0" />
                  <Link to={`/bidders/${currentBidder.id}`} className="hover:text-primary hover:underline truncate">
                    PAN: {currentBidder.pan_number || "—"} • GST: {currentBidder.gst_number || "—"}
                  </Link>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-error-container text-error text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={handleExecuteVerification}>
            Retry
          </Button>
        </div>
      )}

      {/* Indeterminate Running Banner */}
      {isRunning && (
        <div className="p-6 bg-surface-container-lowest rounded-xl border border-primary/40 shadow-subtle text-center space-y-3 animate-pulse">
          <div className="inline-flex p-3 rounded-full bg-primary/10 text-primary">
            <Activity className="h-8 w-8 animate-spin" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-on-surface">
              Autonomous Multi-Agent Orchestration In Progress
            </h3>
            <p className="text-xs text-on-surface-variant max-w-md mx-auto font-mono">
              Dispatching verification context to multi-agent orchestrator. Evaluating GSTIN, PAN, Forensics, Financial Thresholds, and Clause Eligibility...
            </p>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoadingVerification && !isRunning && (
        <div className="space-y-6 animate-pulse">
          {/* Hero Banner Skeleton */}
          <div className="rounded-xl p-6 bg-surface-container-low/80 border border-outline-variant/30 flex flex-col lg:flex-row justify-between gap-6">
            <div className="space-y-3 flex-1">
              <div className="flex items-center gap-3">
                <Skeleton className="h-10 w-10 rounded-xl" />
                <Skeleton className="h-8 w-64 rounded-lg" />
                <Skeleton className="h-6 w-24 rounded-full" />
              </div>
              <Skeleton className="h-4 w-96 rounded" />
              <div className="flex items-center gap-4 pt-2">
                <Skeleton className="h-4 w-40 rounded" />
                <Skeleton className="h-4 w-48 rounded" />
                <Skeleton className="h-4 w-32 rounded" />
              </div>
            </div>
            <Skeleton className="h-28 w-full lg:w-80 rounded-xl" />
          </div>

          {/* Explanation Section Skeleton */}
          <div className="rounded-xl p-6 bg-surface-container-lowest border border-outline-variant/30 space-y-3">
            <Skeleton className="h-4 w-48 rounded" />
            <Skeleton className="h-16 w-full rounded-lg" />
          </div>

          {/* KPI Metrics Skeleton */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3.5">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-surface-container-lowest rounded-xl p-4 border border-outline-variant/30 space-y-2">
                <Skeleton className="h-3 w-16 rounded" />
                <Skeleton className="h-8 w-20 rounded" />
                <Skeleton className="h-3 w-24 rounded" />
              </div>
            ))}
          </div>

          {/* Decision Factors Skeleton */}
          <div className="rounded-xl p-6 bg-surface-container-lowest border border-outline-variant/30 space-y-4">
            <Skeleton className="h-5 w-40 rounded" />
            <Skeleton className="h-24 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
        </div>
      )}

      {/* Main Results View */}
      {!isLoadingVerification && !isRunning && activeVerification && (
        <div className="space-y-6">
          {/* Tabs Bar */}
          <div className="flex border-b border-outline-variant/30 gap-2 overflow-x-auto custom-scrollbar">
            <button
              onClick={() => setActiveTab("summary")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "summary"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <ShieldCheck className="h-4 w-4" />
              <span>Summary &amp; Outcome</span>
            </button>

            <button
              onClick={() => setActiveTab("cross_verification")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "cross_verification"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <GitCompare className="h-4 w-4" />
              <span>Cross-Verification ({activeVerification.cross_verification?.checks?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("forensics")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "forensics"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <FileSearch className="h-4 w-4" />
              <span>Document Forensics ({activeVerification.document_forensics?.documents?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("similarity")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "similarity"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <CopyCheck className="h-4 w-4" />
              <span>Document Similarity ({activeVerification.document_similarity?.comparisons?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("agents")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "agents"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <Layers className="h-4 w-4" />
              <span>Agent Matrix ({activeVerification.agent_results?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("clauses")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "clauses"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <FileText className="h-4 w-4" />
              <span>Clause Breakdown ({activeVerification.requirements?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("evidence")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "evidence"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <Building2 className="h-4 w-4" />
              <span>Evidence &amp; Hashes</span>
            </button>

            <button
              onClick={() => setActiveTab("audit")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "audit"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <Activity className="h-4 w-4" />
              <span>Audit Trail</span>
            </button>
          </div>

          {/* Tab Content */}
          {activeTab === "summary" && (
            <VerificationSummary
              verification={activeVerification}
              tenderReference={currentTender?.tender_number || activeVerification.tender_number}
              tenderTitle={currentTender?.title || activeVerification.tender_title}
            />
          )}

          {activeTab === "cross_verification" && (
            <CrossVerification crossVerification={activeVerification.cross_verification} />
          )}

          {activeTab === "forensics" && (
            <DocumentForensics documentForensics={activeVerification.document_forensics} />
          )}

          {activeTab === "similarity" && (
            <DocumentSimilarity
              documentSimilarity={activeVerification.document_similarity}
              totalDocuments={activeVerification.evidence_snapshot?.length}
            />
          )}

          {activeTab === "agents" && (
            <AgentResults agentResults={activeVerification.agent_results || []} />
          )}

          {activeTab === "clauses" && (
            <ComplianceBreakdown requirements={activeVerification.requirements || []} />
          )}

          {activeTab === "evidence" && (
            <EvidencePanel
              evidenceSnapshot={activeVerification.evidence_snapshot || []}
              documentHashes={activeVerification.document_hashes || {}}
            />
          )}

          {activeTab === "audit" && (
            <VerificationAudit
              verification={activeVerification}
              tenderReference={currentTender?.tender_number || activeVerification.tender_number}
              tenderTitle={currentTender?.title || activeVerification.tender_title}
            />
          )}
        </div>
      )}

      {/* Empty State when no verification exists yet */}
      {!isLoadingVerification && !isRunning && !activeVerification && (
        <div className="text-center py-16 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-8 space-y-4 shadow-subtle">
          <div className="inline-flex p-4 rounded-full bg-surface-container text-on-surface-variant">
            <ShieldCheck className="h-10 w-10 text-primary" />
          </div>
          <div className="space-y-1">
            <h3 className="text-base font-bold text-on-surface">
              No Verification Executed for this Combination
            </h3>
            <p className="text-xs text-on-surface-variant max-w-md mx-auto font-mono">
              Click &quot;Run Multi-Agent Verification&quot; to initiate the autonomous verification workflow across GST, PAN, Financial, Forensics, and Experience verification agents.
            </p>
          </div>
          <div className="pt-2">
            <Button
              variant="primary"
              size="md"
              onClick={handleExecuteVerification}
              disabled={!selectedTenderId || !selectedBidderId}
              leftIcon={<Play className="h-4 w-4" />}
            >
              Run Multi-Agent Verification
            </Button>
          </div>
        </div>
      )}

      {/* Verification History Table Section */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
          <div>
            <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <History className="h-4 w-4 text-primary" />
              <span>Verification History ({globalHistory.length})</span>
            </h3>
            <p className="text-xs text-on-surface-variant font-mono mt-0.5">
              Chronological log of multi-agent verification runs, decisions, risk levels, and immutable result hashes
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            leftIcon={<RefreshCw className="h-3.5 w-3.5" />}
            onClick={loadGlobalHistory}
            isLoading={isLoadingGlobalHistory}
          >
            Refresh Log
          </Button>
        </div>

        {isLoadingGlobalHistory ? (
          <div className="space-y-2">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-lg" />
            ))}
          </div>
        ) : globalHistory.length === 0 ? (
          <div className="text-center py-8 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-6">
            No verification executions recorded yet. Run a verification above to populate the audit log.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-outline-variant/30 bg-surface-container-low/60 text-[11px] font-mono text-on-surface-variant uppercase tracking-wider">
                  <th className="py-2.5 px-3">Verification ID</th>
                  <th className="py-2.5 px-3">Tender</th>
                  <th className="py-2.5 px-3">Bidder</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Decision</th>
                  <th className="py-2.5 px-3">Risk Level</th>
                  <th className="py-2.5 px-3">Created</th>
                  <th className="py-2.5 px-3">Completed</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/20 text-xs font-mono">
                {globalHistory.map((item) => (
                  <tr
                    key={item.verification_id}
                    className={`hover:bg-surface-container-low/50 transition-colors ${
                      activeVerification?.verification_id === item.verification_id ? "bg-primary/5 font-semibold" : ""
                    }`}
                  >
                    <td className="py-2.5 px-3 text-primary font-bold">
                      <span className="cursor-pointer hover:underline" onClick={() => handleSelectHistoryItem(item)}>
                        {item.verification_id}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-on-surface max-w-[140px] truncate" title={item.tender_number || item.tender_id}>
                      {item.tender_number || item.tender_id?.slice(0, 8) || "—"}
                    </td>
                    <td className="py-2.5 px-3 font-sans text-on-surface max-w-[160px] truncate" title={item.bidder_name || item.bidder_id}>
                      {item.bidder_name || item.bidder_id?.slice(0, 8) || "—"}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded bg-surface-container text-[11px] text-on-surface">
                        {item.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {getDecisionBadge(item.decision)}
                    </td>
                    <td className="py-2.5 px-3">
                      {getRiskBadge(item.risk_level)}
                    </td>
                    <td className="py-2.5 px-3 text-on-surface-variant text-[11px]">
                      {formatDate(item.created_at)}
                    </td>
                    <td className="py-2.5 px-3 text-on-surface-variant text-[11px]">
                      {item.completed_at ? formatDate(item.completed_at) : "—"}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <Button
                        variant={activeVerification?.verification_id === item.verification_id ? "primary" : "secondary"}
                        size="sm"
                        leftIcon={<Eye className="h-3 w-3" />}
                        onClick={() => handleSelectHistoryItem(item)}
                      >
                        {activeVerification?.verification_id === item.verification_id ? "Viewing" : "View"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default Verification;
