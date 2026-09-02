import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { listTenders } from "../api/tenders";
import { listBidders } from "../api/bidders";
import {
  runVerification,
  getVerification,
  getVerificationHistory,
} from "../api/verification";
import {
  TenderResponse,
  BidderResponse,
  VerificationResponse,
  VerificationHistoryItem,
} from "../types";
import { Button, Select, Skeleton } from "../components/ui";
import {
  VerificationSummary,
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
} from "lucide-react";

type TabType = "summary" | "agents" | "clauses" | "evidence" | "audit";

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
      // Refresh history list
      const hist = await getVerificationHistory(selectedTenderId, selectedBidderId);
      setHistoryItems(hist);
    } catch (err: any) {
      setError(err?.message || "Multi-agent verification execution failed.");
    } finally {
      setIsRunning(false);
    }
  };

  const currentTender = tenders.find((t) => t.id === selectedTenderId);
  const currentBidder = bidders.find((b) => b.id === selectedBidderId);

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
            onClick={loadVerificationData}
            isLoading={isLoadingVerification}
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
              <span>{historyItems.length} Past Executions</span>
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
              Dispatching verification context to n8n Master Orchestrator. Evaluating GSTIN, PAN, Forensics, Financial Thresholds, and Clause Eligibility...
            </p>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoadingVerification && !isRunning && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
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
            <VerificationSummary verification={activeVerification} />
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
            <VerificationAudit verificationId={activeVerification.verification_id} />
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
    </div>
  );
};

export default Verification;
