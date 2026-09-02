import React, { useState, useEffect, useCallback } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { listTenders } from "../api/tenders";
import { listBidders } from "../api/bidders";
import { getVerification, getVerificationHistory } from "../api/verification";
import {
  TenderResponse,
  BidderResponse,
  VerificationResponse,
} from "../types";
import { Button, Select, Skeleton } from "../components/ui";
import {
  Printer,
  ShieldCheck,
  Building2,
  FileText,
  Hash,
  AlertCircle,
  CheckCircle2,
  Award,
} from "lucide-react";
import { formatDate } from "../lib/utils";

export const Reports: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const urlVerificationId = searchParams.get("verification_id") || "";
  const urlTenderId = searchParams.get("tender_id") || "";
  const urlBidderId = searchParams.get("bidder_id") || "";

  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [bidders, setBidders] = useState<BidderResponse[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState<string>(urlTenderId);
  const [selectedBidderId, setSelectedBidderId] = useState<string>(urlBidderId);

  const [verification, setVerification] = useState<VerificationResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load dropdown lists
  useEffect(() => {
    async function loadDropdowns() {
      try {
        const [tendersRes, biddersRes] = await Promise.all([
          listTenders({ page_size: 50 }),
          listBidders({ page_size: 50 }),
        ]);
        const tItems = tendersRes.data || tendersRes.items || [];
        const bItems = biddersRes.data || biddersRes.items || [];
        setTenders(tItems);
        setBidders(bItems);

        if (!selectedTenderId && tItems.length > 0) setSelectedTenderId(tItems[0].id);
        if (!selectedBidderId && bItems.length > 0) setSelectedBidderId(bItems[0].id);
      } catch (err: any) {
        console.error("Failed to load tenders/bidders for reports:", err);
      }
    }
    loadDropdowns();
  }, []);

  const loadReport = useCallback(async () => {
    setError(null);

    // 1. Direct by verification ID
    if (urlVerificationId) {
      setIsLoading(true);
      try {
        const data = await getVerification(urlVerificationId);
        setVerification(data);
        if (data.tender_id) setSelectedTenderId(data.tender_id);
        if (data.bidder_id) setSelectedBidderId(data.bidder_id);
      } catch (err: any) {
        setError(err?.message || "Failed to load verification report.");
        setVerification(null);
      } finally {
        setIsLoading(false);
      }
      return;
    }

    // 2. By selected tender and bidder
    if (selectedTenderId && selectedBidderId) {
      setIsLoading(true);
      try {
        const hist = await getVerificationHistory(selectedTenderId, selectedBidderId);
        if (hist.length > 0) {
          const fullData = await getVerification(hist[0].verification_id);
          setVerification(fullData);
        } else {
          setVerification(null);
        }
      } catch (err: any) {
        console.error("Failed to load report history:", err);
        setVerification(null);
      } finally {
        setIsLoading(false);
      }
    }
  }, [urlVerificationId, selectedTenderId, selectedBidderId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  const handlePrint = () => {
    window.print();
  };

  const currentTender = tenders.find((t) => t.id === selectedTenderId);
  const currentBidder = bidders.find((b) => b.id === selectedBidderId);

  return (
    <div className="space-y-6 font-sans">
      {/* Top Controls Bar (Hidden in Print) */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 print:hidden">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-on-surface flex items-center gap-2">
            <Printer className="h-6 w-6 text-primary" />
            <span>Procurement Compliance Audit Reports</span>
          </h1>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Generate, inspect, and print official cryptographic evaluation certificates for bid submissions
          </p>
        </div>

        <div className="flex items-center gap-3">
          {verification && (
            <Button
              variant="primary"
              size="sm"
              onClick={handlePrint}
              leftIcon={<Printer className="h-4 w-4" />}
            >
              Print / Export PDF Report
            </Button>
          )}
        </div>
      </div>

      {/* Target Selector (Hidden in Print) */}
      <div className="p-5 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle grid grid-cols-1 sm:grid-cols-2 gap-4 print:hidden">
        <div>
          <Select
            label="Select Procurement Tender"
            value={selectedTenderId}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
              setSelectedTenderId(e.target.value);
              setSearchParams({ tender_id: e.target.value, bidder_id: selectedBidderId });
            }}
            options={tenders.map((t) => ({
              value: t.id,
              label: `${t.tender_number} — ${t.title.slice(0, 40)}...`,
            }))}
          />
        </div>

        <div>
          <Select
            label="Select Bidder Entity"
            value={selectedBidderId}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => {
              setSelectedBidderId(e.target.value);
              setSearchParams({ tender_id: selectedTenderId, bidder_id: e.target.value });
            }}
            options={bidders.map((b) => ({
              value: b.id,
              label: `${b.company_name} (GST: ${b.gst_number || "None"})`,
            }))}
          />
        </div>
      </div>

      {/* Error alert */}
      {error && (
        <div className="p-4 rounded-xl bg-error-container text-error text-xs flex items-center gap-2 print:hidden">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-48 w-full rounded-xl" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      )}

      {/* Printable Report Document */}
      {!isLoading && verification && (
        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-8 sm:p-12 shadow-subtle space-y-8 print:border-none print:shadow-none print:p-0">
          {/* Official Document Header */}
          <div className="border-b-2 border-primary pb-6 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <div className="p-2 rounded bg-primary text-on-primary">
                    <ShieldCheck className="h-6 w-6" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-on-surface uppercase tracking-wider">
                      Government e-Marketplace (GeM)
                    </h2>
                    <p className="text-xs text-on-surface-variant font-mono">
                      Multi-Agent Bid Compliance &amp; Eligibility Evaluation Certificate
                    </p>
                  </div>
                </div>
              </div>

              <div className="text-right font-mono text-xs text-on-surface-variant space-y-0.5">
                <div>Report Ref: <span className="font-bold text-primary">{verification.verification_id}</span></div>
                <div>Issued: <span className="font-semibold text-on-surface">{formatDate(verification.completed_at || verification.created_at)}</span></div>
                <div>Status: <span className="font-bold text-emerald-700">{verification.status}</span></div>
              </div>
            </div>
          </div>

          {/* Core Entity Information Matrix */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 text-xs">
            <div className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-2">
              <span className="font-mono font-bold uppercase tracking-wider text-primary text-[11px] flex items-center gap-1.5">
                <FileText className="h-3.5 w-3.5" />
                <span>Procurement Tender Details</span>
              </span>
              <div className="space-y-1">
                <div><span className="text-on-surface-variant">Tender Ref:</span> <span className="font-mono font-semibold text-on-surface">{currentTender?.tender_number || "—"}</span></div>
                <div><span className="text-on-surface-variant">Title:</span> <span className="font-semibold text-on-surface">{currentTender?.title || "—"}</span></div>
                <div><span className="text-on-surface-variant">Procuring Entity:</span> <span className="text-on-surface">{currentTender?.organization || "—"} ({currentTender?.department || "General"})</span></div>
                <div><span className="text-on-surface-variant">Category:</span> <span className="text-on-surface">{currentTender?.category || "Works"}</span></div>
              </div>
            </div>

            <div className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-2">
              <span className="font-mono font-bold uppercase tracking-wider text-primary text-[11px] flex items-center gap-1.5">
                <Building2 className="h-3.5 w-3.5" />
                <span>Bidder Corporate Details</span>
              </span>
              <div className="space-y-1">
                <div><span className="text-on-surface-variant">Company Name:</span> <span className="font-semibold text-on-surface">{verification.bidder_name}</span></div>
                <div><span className="text-on-surface-variant">GSTIN:</span> <span className="font-mono font-semibold text-on-surface">{currentBidder?.gst_number || "—"}</span></div>
                <div><span className="text-on-surface-variant">PAN:</span> <span className="font-mono font-semibold text-on-surface">{currentBidder?.pan_number || "—"}</span></div>
                <div><span className="text-on-surface-variant">Registration / CIN:</span> <span className="font-mono text-on-surface">{currentBidder?.registration_number || "—"}</span></div>
              </div>
            </div>
          </div>

          {/* Qualification Verdict Banner */}
          <div className="p-6 rounded-xl bg-surface-container-low border-2 border-primary/30 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="space-y-1">
              <span className="text-[11px] font-mono uppercase tracking-wider text-on-surface-variant font-bold">
                Synthesized Qualification Verdict
              </span>
              <div className="text-2xl font-bold font-mono text-primary flex items-center gap-2">
                <Award className="h-7 w-7 text-primary" />
                <span>{verification.decision}</span>
              </div>
              <p className="text-xs text-on-surface-variant font-mono">
                Compliance: {verification.overall_compliance || "COMPLIANT"} • Risk Level: {verification.risk_level} (Score: {Math.round(verification.risk_score)}/100)
              </p>
            </div>

            <div className="text-right font-mono text-xs space-y-1">
              <div>Confidence: <span className="font-bold text-primary">{Math.round((verification.overall_confidence ?? 1.0) * 100)}%</span></div>
              <div>Agents Reporting: <span className="font-bold text-on-surface">{verification.agent_results?.length || 0}</span></div>
              <div>Evaluated Rules: <span className="font-bold text-on-surface">{verification.requirements?.length || 0}</span></div>
            </div>
          </div>

          {/* Key Reasons & Decision Drivers */}
          {verification.reasons && verification.reasons.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-on-surface flex items-center gap-1.5">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <span>Audit Evaluation Findings</span>
              </h3>
              <ul className="space-y-1.5 text-xs text-on-surface pl-2">
                {verification.reasons.map((r, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-primary font-bold">•</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Agent Results Summary Table */}
          {verification.agent_results && verification.agent_results.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-xs font-bold font-mono uppercase tracking-wider text-on-surface flex items-center gap-1.5">
                <ShieldCheck className="h-4 w-4 text-primary" />
                <span>Specialized Autonomous Agent Matrix</span>
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border border-outline-variant/20">
                  <thead className="bg-surface-container-low text-[11px] font-mono text-on-surface-variant uppercase">
                    <tr>
                      <th className="py-2 px-3">Agent Name</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3">Confidence</th>
                      <th className="py-2 px-3">Primary Evaluation / Finding</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/20">
                    {verification.agent_results.map((agent, idx) => (
                      <tr key={idx} className="hover:bg-surface-container-low/40">
                        <td className="py-2.5 px-3 font-mono font-semibold text-primary">
                          {agent.agent || agent.agent_name}
                        </td>
                        <td className="py-2.5 px-3 whitespace-nowrap">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                            agent.status === "PASS" || agent.status === "VERIFIED"
                              ? "bg-emerald-100 text-emerald-800"
                              : agent.status === "FAIL" || agent.status === "ERROR"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-amber-100 text-amber-800"
                          }`}>
                            {agent.status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-mono">
                          {agent.confidence !== undefined ? `${Math.round(agent.confidence * 100)}%` : "100%"}
                        </td>
                        <td className="py-2.5 px-3 text-on-surface">
                          {agent.reason || (agent.issues && agent.issues[0]) || "Rule verification completed."}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Cryptographic Proof & Provenance */}
          <div className="p-4 rounded-xl bg-surface-container-low/70 border border-outline-variant/30 space-y-2 text-xs font-mono">
            <h4 className="font-bold text-[11px] text-on-surface uppercase tracking-wider flex items-center gap-1.5">
              <Hash className="h-3.5 w-3.5 text-primary" />
              <span>Cryptographic Proof &amp; Audit Trail</span>
            </h4>
            <div className="space-y-1 text-on-surface-variant text-[11px] break-all">
              <div>Canonical Result SHA-256: <span className="font-bold text-on-surface">{verification.result_hash || "—"}</span></div>
              <div>Timestamp: <span className="text-on-surface">{formatDate(verification.completed_at || verification.created_at)}</span></div>
            </div>
          </div>

          {/* Sign-Off Block */}
          <div className="pt-12 border-t border-outline-variant/30 grid grid-cols-2 gap-8 text-xs font-mono">
            <div className="space-y-8">
              <div>Evaluation Officer: __________________________</div>
              <div>Designation: Procurement Officer (GeM)</div>
            </div>
            <div className="space-y-8 text-right">
              <div>Signature &amp; Stamp: __________________________</div>
              <div>Date: {formatDate(new Date().toISOString())}</div>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !verification && (
        <div className="text-center py-16 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-8 space-y-3 shadow-subtle">
          <Printer className="h-10 w-10 text-outline mx-auto" />
          <h3 className="text-sm font-semibold text-on-surface">No Compliance Report Available</h3>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto font-mono">
            Please select a tender and bidder with completed verification records, or execute verification from the Verification Center.
          </p>
          <div className="pt-2">
            <Link to={`/verification?tender_id=${selectedTenderId}&bidder_id=${selectedBidderId}`}>
              <Button variant="primary" size="sm">
                Go to Verification Center
              </Button>
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};

export default Reports;
