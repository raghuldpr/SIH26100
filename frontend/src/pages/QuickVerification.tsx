import React, { useState, useRef } from "react";
import { Link } from "react-router-dom";
import { quickVerify } from "../api/verification";
import { VerificationResponse } from "../types";
import { Button, Input, Badge, Card } from "../components/ui";
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
  Zap,
  UploadCloud,
  FileText,
  FileCheck,
  Building2,
  Trash2,
  AlertCircle,
  Activity,
  Layers,
  ShieldCheck,
  ArrowRight,
  RefreshCw,
  CheckCircle2,
  GitCompare,
  FileSearch,
  CopyCheck,
} from "lucide-react";

interface BidderFileItem {
  id: string;
  file: File;
  documentType: string;
}

const BIDDER_DOC_TYPES = [
  { value: "GST", label: "GST Registration Certificate" },
  { value: "PAN", label: "PAN Card" },
  { value: "FINANCIAL_STATEMENT", label: "Audited Financials / Turnover (ITR)" },
  { value: "EXPERIENCE_CERTIFICATE", label: "Prior Experience / Work Order" },
  { value: "UDYAM", label: "MSME / Udyam Certificate" },
  { value: "OEM_AUTHORIZATION", label: "OEM Authorization" },
  { value: "MII_DECLARATION", label: "Make In India (MII) Declaration" },
  { value: "OTHER", label: "Other Statutory Filing" },
];

function detectDocType(filename: string): string {
  const fn = filename.toLowerCase();
  if (fn.includes("pan")) return "PAN";
  if (fn.includes("gst") || fn.includes("tax")) return "GST";
  if (fn.includes("udyam") || fn.includes("msme")) return "UDYAM";
  if (fn.includes("financial") || fn.includes("turnover") || fn.includes("balance") || fn.includes("itr")) {
    return "FINANCIAL_STATEMENT";
  }
  if (fn.includes("exp") || fn.includes("work") || fn.includes("order") || fn.includes("completion")) {
    return "EXPERIENCE_CERTIFICATE";
  }
  if (fn.includes("oem")) return "OEM_AUTHORIZATION";
  if (fn.includes("mii") || fn.includes("make")) return "MII_DECLARATION";
  return "OTHER";
}

function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

type TabType = "summary" | "cross_verification" | "forensics" | "similarity" | "agents" | "clauses" | "evidence" | "audit";

export const QuickVerification: React.FC = () => {
  // Tender input state
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [tenderTitle, setTenderTitle] = useState("");
  const tenderInputRef = useRef<HTMLInputElement | null>(null);

  // Bidder inputs state
  const [bidderFiles, setBidderFiles] = useState<BidderFileItem[]>([]);
  const [bidderName, setBidderName] = useState("");
  const bidderInputRef = useRef<HTMLInputElement | null>(null);

  // Execution & results state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [verificationResult, setVerificationResult] = useState<VerificationResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("summary");

  // Drag & drop state
  const [isDraggingTender, setIsDraggingTender] = useState(false);
  const [isDraggingBidder, setIsDraggingBidder] = useState(false);

  // Handlers for tender document
  const handleTenderSelect = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Tender document must be in PDF format (.pdf).");
      return;
    }
    setError(null);
    setTenderFile(file);
    if (!tenderTitle) {
      setTenderTitle(file.name.replace(/\.[^/.]+$/, ""));
    }
  };

  // Handlers for bidder documents
  const handleBidderFilesSelect = (files: FileList | File[]) => {
    const allowed = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"];
    const newItems: BidderFileItem[] = [];

    Array.from(files).forEach((f) => {
      const lower = f.name.toLowerCase();
      if (allowed.some((ext) => lower.endsWith(ext))) {
        newItems.push({
          id: Math.random().toString(36).substring(2, 9),
          file: f,
          documentType: detectDocType(f.name),
        });
      }
    });

    if (newItems.length === 0) {
      setError("Please select valid document files (PDF, PNG, JPG, TIFF).");
      return;
    }

    setError(null);
    setBidderFiles((prev) => [...prev, ...newItems]);
  };

  const handleRemoveBidderFile = (id: string) => {
    setBidderFiles((prev) => prev.filter((item) => item.id !== id));
  };

  const handleUpdateBidderFileType = (id: string, docType: string) => {
    setBidderFiles((prev) =>
      prev.map((item) => (item.id === id ? { ...item, documentType: docType } : item))
    );
  };

  const handleReset = () => {
    setTenderFile(null);
    setTenderTitle("");
    setBidderFiles([]);
    setBidderName("");
    setError(null);
    setVerificationResult(null);
    setIsAnalyzing(false);
    setAnalysisStep("");
    setActiveTab("summary");
  };

  // Central analyze handler
  const handleAnalyze = async () => {
    if (!tenderFile) {
      setError("Please upload an official Tender Notice / RFP document (PDF).");
      return;
    }
    if (bidderFiles.length === 0) {
      setError("Please attach at least one bidder compliance document.");
      return;
    }

    setError(null);
    setIsAnalyzing(true);
    setVerificationResult(null);

    try {
      setAnalysisStep("Uploading tender and bidder documents to secure vault...");
      const formData = new FormData();
      formData.append("tender_document", tenderFile);

      bidderFiles.forEach((item) => {
        formData.append("bidder_documents", item.file);
      });

      if (tenderTitle.trim()) {
        formData.append("tender_title", tenderTitle.trim());
      }
      if (bidderName.trim()) {
        formData.append("bidder_name", bidderName.trim());
      }

      setAnalysisStep("Executing clause analysis & multi-agent verification pipeline...");
      const response = await quickVerify(formData);

      setVerificationResult(response);
      setActiveTab("summary");
    } catch (err: any) {
      console.error("Quick verification failed:", err);
      setError(err?.message || "Failed to complete quick verification workflow. Please review your documents.");
    } finally {
      setIsAnalyzing(false);
      setAnalysisStep("");
    }
  };

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-on-surface">
              Quick Verification
            </h1>
            <Badge variant="primary" size="sm">
              Phase 20 Unified
            </Badge>
          </div>
          <p className="text-sm text-on-surface-variant mt-1">
            Upload a tender document and bidder compliance filings to trigger end-to-end multi-agent verification in one click.
          </p>
        </div>

        {verificationResult && (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleReset} leftIcon={<RefreshCw className="h-4 w-4" />}>
              Verify Another Bid
            </Button>
            <Link to="/verification">
              <Button variant="secondary" size="sm" rightIcon={<ArrowRight className="h-4 w-4" />}>
                Full Verification Hub
              </Button>
            </Link>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <div className="p-4 rounded-xl bg-error-container text-error text-xs flex items-center justify-between gap-3 shadow-subtle animate-in fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="font-medium">{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            className="text-xs hover:underline text-error shrink-0 font-semibold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Verification Results Display */}
      {verificationResult ? (
        <div className="space-y-6 animate-in fade-in duration-300">
          {/* Banner Summary */}
          <div className="p-5 rounded-xl border border-outline-variant/40 bg-surface-container-lowest shadow-subtle flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-on-surface-variant">
                    Execution ID: {verificationResult.verification_id}
                  </span>
                  <Badge
                    variant={
                      verificationResult.decision === "QUALIFIED"
                        ? "success"
                        : verificationResult.decision === "MANUAL_REVIEW"
                        ? "warning"
                        : "danger"
                    }
                    size="sm"
                  >
                    {verificationResult.decision || "VERIFIED"}
                  </Badge>
                </div>
                <h2 className="text-base font-bold text-on-surface mt-0.5">
                  {verificationResult.bidder_name || "Bidder Verification Completed"}
                </h2>
              </div>
            </div>

            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="text-right">
                <div className="text-on-surface-variant text-[11px]">Risk Assessment</div>
                <div className="font-semibold text-on-surface">
                  {verificationResult.risk_level || "LOW"} ({verificationResult.risk_score ?? 0}%)
                </div>
              </div>
              {verificationResult.result_hash && (
                <div className="hidden sm:block text-right">
                  <div className="text-on-surface-variant text-[11px]">Result Digest</div>
                  <div className="font-mono text-primary truncate max-w-[140px]" title={verificationResult.result_hash}>
                    {verificationResult.result_hash.slice(0, 12)}...
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Navigation Tabs */}
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
              <span>Cross-Verification ({verificationResult.cross_verification?.checks?.length || 0})</span>
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
              <span>Document Forensics ({verificationResult.document_forensics?.documents?.length || 0})</span>
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
              <span>Document Similarity ({verificationResult.document_similarity?.comparisons?.length || 0})</span>
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
              <span>Agent Matrix ({verificationResult.agent_results?.length || 0})</span>
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
              <span>Clause Breakdown ({verificationResult.requirements?.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("evidence")}
              className={`flex items-center gap-2 px-4 py-3 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                activeTab === "evidence"
                  ? "border-primary text-primary"
                  : "border-transparent text-on-surface-variant hover:text-on-surface"
              }`}
            >
              <FileCheck className="h-4 w-4" />
              <span>Evidence Extracted ({verificationResult.evidence_snapshot?.length || 0})</span>
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

          {/* Tab Contents */}
          {activeTab === "summary" && <VerificationSummary verification={verificationResult} />}
          {activeTab === "cross_verification" && (
            <CrossVerification crossVerification={verificationResult.cross_verification} />
          )}
          {activeTab === "forensics" && (
            <DocumentForensics documentForensics={verificationResult.document_forensics} />
          )}
          {activeTab === "similarity" && (
            <DocumentSimilarity
              documentSimilarity={verificationResult.document_similarity}
              totalDocuments={verificationResult.evidence_snapshot?.length}
            />
          )}
          {activeTab === "agents" && <AgentResults agentResults={verificationResult.agent_results || []} />}
          {activeTab === "clauses" && (
            <ComplianceBreakdown requirements={verificationResult.requirements} />
          )}
          {activeTab === "evidence" && (
            <EvidencePanel
              evidenceSnapshot={verificationResult.evidence_snapshot}
              documentHashes={verificationResult.document_hashes}
            />
          )}
          {activeTab === "audit" && (
            <VerificationAudit
              verification={verificationResult}
              verificationId={verificationResult.verification_id}
            />
          )}
        </div>
      ) : (
        /* Upload & Analyze Intake Screen */
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Panel 1: Tender Document Upload */}
            <Card className="p-5 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-outline-variant/30">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-primary/10 text-primary">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="text-sm font-bold text-on-surface">1. Tender Document</h2>
                      <p className="text-[11px] text-on-surface-variant">
                        Notice Inviting Tender (NIT) or RFP specification (PDF)
                      </p>
                    </div>
                  </div>
                  {tenderFile && (
                    <Badge variant="success" size="sm">
                      Attached
                    </Badge>
                  )}
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <Input
                      label="Tender Title / Reference (Optional)"
                      placeholder="e.g. GeM/2026/B/89124 — Cloud Infrastructure"
                      value={tenderTitle}
                      onChange={(e) => setTenderTitle(e.target.value)}
                      disabled={isAnalyzing}
                    />
                  </div>

                  {/* Tender Drag & Drop Dropzone */}
                  <input
                    type="file"
                    ref={tenderInputRef}
                    accept=".pdf"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleTenderSelect(e.target.files[0]);
                      }
                    }}
                    disabled={isAnalyzing}
                  />

                  {!tenderFile ? (
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsDraggingTender(true);
                      }}
                      onDragLeave={() => setIsDraggingTender(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsDraggingTender(false);
                        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                          handleTenderSelect(e.dataTransfer.files[0]);
                        }
                      }}
                      onClick={() => tenderInputRef.current?.click()}
                      className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
                        isDraggingTender
                          ? "border-primary bg-primary/5"
                          : "border-outline-variant/60 hover:border-primary/50 hover:bg-surface-container-low"
                      }`}
                    >
                      <div className="flex flex-col items-center gap-2">
                        <div className="p-3 rounded-full bg-surface-container text-primary">
                          <UploadCloud className="h-6 w-6" />
                        </div>
                        <div className="text-xs font-semibold text-on-surface">
                          Click to browse or drop tender PDF here
                        </div>
                        <div className="text-[11px] text-on-surface-variant">
                          Supports official NIT/RFP documents up to 50 MB
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-3.5 rounded-xl bg-surface-container-low border border-outline-variant/40 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-3 truncate">
                        <div className="p-2 rounded-lg bg-primary/10 text-primary shrink-0">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div className="truncate">
                          <div className="text-xs font-semibold text-on-surface truncate">
                            {tenderFile.name}
                          </div>
                          <div className="text-[11px] text-on-surface-variant font-mono">
                            {formatBytes(tenderFile.size)} • PDF Document
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={() => {
                          setTenderFile(null);
                          if (tenderInputRef.current) tenderInputRef.current.value = "";
                        }}
                        disabled={isAnalyzing}
                        className="text-on-surface-variant hover:text-error transition-colors p-1"
                        title="Remove tender document"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
              </div>

              <div className="text-[11px] text-on-surface-variant font-mono flex items-center gap-1.5 pt-2 border-t border-outline-variant/20">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                <span>Deterministic clause parsing with Groq AI escalation</span>
              </div>
            </Card>

            {/* Panel 2: Bidder Documents Upload */}
            <Card className="p-5 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-outline-variant/30">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-lg bg-secondary/10 text-secondary">
                      <Building2 className="h-5 w-5" />
                    </div>
                    <div>
                      <h2 className="text-sm font-bold text-on-surface">2. Bidder Documents</h2>
                      <p className="text-[11px] text-on-surface-variant">
                        Attach GST, PAN, Turnover, and Experience proof (PDF, Images)
                      </p>
                    </div>
                  </div>
                  <Badge variant={bidderFiles.length > 0 ? "secondary" : "neutral"} size="sm">
                    {bidderFiles.length} {bidderFiles.length === 1 ? "File" : "Files"}
                  </Badge>
                </div>

                <div className="mt-4 space-y-4">
                  <div>
                    <Input
                      label="Bidder Organization Name (Optional)"
                      placeholder="e.g. Bharat Tech Solutions Pvt Ltd"
                      value={bidderName}
                      onChange={(e) => setBidderName(e.target.value)}
                      disabled={isAnalyzing}
                    />
                  </div>

                  {/* Multi-file input */}
                  <input
                    type="file"
                    ref={bidderInputRef}
                    multiple
                    accept=".pdf,image/png,image/jpeg,image/tiff"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        handleBidderFilesSelect(e.target.files);
                      }
                    }}
                    disabled={isAnalyzing}
                  />

                  {/* Bidder Dropzone */}
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDraggingBidder(true);
                    }}
                    onDragLeave={() => setIsDraggingBidder(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setIsDraggingBidder(false);
                      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                        handleBidderFilesSelect(e.dataTransfer.files);
                      }
                    }}
                    onClick={() => bidderInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-colors ${
                      isDraggingBidder
                        ? "border-secondary bg-secondary/5"
                        : "border-outline-variant/60 hover:border-secondary/50 hover:bg-surface-container-low"
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1.5">
                      <div className="p-2.5 rounded-full bg-surface-container text-secondary">
                        <UploadCloud className="h-5 w-5" />
                      </div>
                      <div className="text-xs font-semibold text-on-surface">
                        Click to select or drop bidder files (PDF, PNG, JPG)
                      </div>
                      <div className="text-[11px] text-on-surface-variant">
                        Attach multiple statutory and financial certificates
                      </div>
                    </div>
                  </div>

                  {/* Selected Bidder Files List */}
                  {bidderFiles.length > 0 && (
                    <div className="space-y-2 max-h-56 overflow-y-auto custom-scrollbar pr-1">
                      {bidderFiles.map((item) => (
                        <div
                          key={item.id}
                          className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/30 flex items-center justify-between gap-3 text-xs"
                        >
                          <div className="flex items-center gap-2.5 min-w-0 truncate">
                            <FileCheck className="h-4 w-4 text-secondary shrink-0" />
                            <div className="min-w-0 truncate">
                              <div className="font-semibold text-on-surface truncate">
                                {item.file.name}
                              </div>
                              <div className="text-[10px] text-on-surface-variant font-mono">
                                {formatBytes(item.file.size)}
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            <select
                              value={item.documentType}
                              onChange={(e) => handleUpdateBidderFileType(item.id, e.target.value)}
                              disabled={isAnalyzing}
                              className="text-[11px] bg-surface-container border border-outline-variant/50 rounded px-2 py-1 text-on-surface focus:outline-none focus:border-primary"
                            >
                              {BIDDER_DOC_TYPES.map((dt) => (
                                <option key={dt.value} value={dt.value}>
                                  {dt.label}
                                </option>
                              ))}
                            </select>
                            <button
                              onClick={() => handleRemoveBidderFile(item.id)}
                              disabled={isAnalyzing}
                              className="text-on-surface-variant hover:text-error transition-colors p-1"
                              title="Remove file"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="text-[11px] text-on-surface-variant font-mono flex items-center gap-1.5 pt-2 border-t border-outline-variant/20">
                <FileCheck className="h-3.5 w-3.5 text-secondary" />
                <span>Automated OCR and structured statutory entity extraction</span>
              </div>
            </Card>
          </div>

          {/* Central Action Bar */}
          <div className="p-6 rounded-xl border border-outline-variant/40 bg-surface-container-lowest shadow-subtle flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="space-y-1 text-center sm:text-left">
              <h3 className="text-sm font-bold text-on-surface">Ready to Analyze</h3>
              <p className="text-xs text-on-surface-variant">
                {!tenderFile && bidderFiles.length === 0
                  ? "Please attach a tender PDF and at least one bidder filing to begin."
                  : !tenderFile
                  ? "Tender document is missing."
                  : bidderFiles.length === 0
                  ? "At least one bidder document is required."
                  : `Tender ready with ${bidderFiles.length} bidder document(s).`}
              </p>
            </div>

            <div className="flex items-center gap-3 w-full sm:w-auto">
              {(tenderFile || bidderFiles.length > 0) && (
                <Button
                  variant="outline"
                  size="md"
                  onClick={handleReset}
                  disabled={isAnalyzing}
                  className="w-full sm:w-auto"
                >
                  Clear Form
                </Button>
              )}

              <Button
                variant="primary"
                size="md"
                onClick={handleAnalyze}
                disabled={!tenderFile || bidderFiles.length === 0 || isAnalyzing}
                isLoading={isAnalyzing}
                leftIcon={<Zap className="h-4 w-4 fill-current" />}
                className="w-full sm:w-auto"
              >
                {isAnalyzing ? "Analyzing & Verifying..." : "Analyze & Verify Bid"}
              </Button>
            </div>
          </div>

          {/* Progress State Overlay */}
          {isAnalyzing && (
            <div className="p-6 rounded-xl border border-primary/30 bg-primary/5 text-center space-y-3 animate-pulse">
              <div className="inline-flex p-3 rounded-full bg-primary/10 text-primary">
                <Activity className="h-8 w-8 animate-spin" />
              </div>
              <div className="space-y-1">
                <h4 className="text-sm font-bold text-on-surface">
                  Autonomous Multi-Agent Pipeline Running
                </h4>
                <p className="text-xs font-mono text-on-surface-variant max-w-lg mx-auto">
                  {analysisStep || "Processing documents and evaluating eligibility..."}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
