import React, { useState } from "react";
import {
  VerificationDocumentForensics,
  ForensicDocumentResult,
  ForensicAnomalyItem,
} from "../../types";
import { extractHumanReadableValue } from "../../lib/evidenceFormatter";
import {
  FileSearch,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  FileText,
  Copy,
  Check,
  Info,
  Layers,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

export interface DocumentForensicsProps {
  documentForensics?: VerificationDocumentForensics | null;
}

export const DocumentForensics: React.FC<DocumentForensicsProps> = ({
  documentForensics,
}) => {
  const [filter, setFilter] = useState<"all" | "anomalies" | "clean" | "unresolved">("all");
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [expandedDocs, setExpandedDocs] = useState<Record<string, boolean>>({});

  const toggleDocExpand = (docKey: string) => {
    setExpandedDocs((prev) => ({
      ...prev,
      [docKey]: !prev[docKey],
    }));
  };

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Missing data state
  if (!documentForensics) {
    return (
      <section
        aria-labelledby="document-forensics-heading"
        className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 space-y-3 font-sans"
      >
        <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20">
          <FileSearch className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
          <div>
            <h3 id="document-forensics-heading" className="text-base font-bold text-on-surface">
              Document Forensics
            </h3>
            <p className="text-xs text-on-surface-variant font-sans">
              Evaluates document integrity, PDF streams, metadata timestamps, and cryptographic hashes.
            </p>
          </div>
        </div>
        <div className="py-8 text-center bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <HelpCircle className="h-8 w-8 text-outline mx-auto" aria-hidden="true" />
          <h4 className="text-sm font-semibold text-on-surface font-sans">Forensic Analysis Unavailable</h4>
          <p className="text-xs text-on-surface-variant font-sans max-w-md mx-auto">
            Document forensics data is not available for this verification run.
          </p>
        </div>
      </section>
    );
  }

  const overallStatus = (documentForensics.overall_status || "UNRESOLVED").toUpperCase();
  const overallRisk = (documentForensics.overall_risk || "UNKNOWN").toUpperCase();
  const documents = documentForensics.documents || [];

  const totalAnomalies = documents.reduce((sum, d) => sum + (d.anomalies?.length || 0), 0);
  const anomalyDocsCount = documents.filter((d) => (d.anomalies && d.anomalies.length > 0) || d.status === "ANOMALY" || d.status === "SUSPICIOUS").length;
  const cleanDocsCount = documents.filter((d) => d.status === "CLEAN" && (!d.anomalies || d.anomalies.length === 0)).length;
  const unresolvedDocsCount = documents.filter((d) => d.status === "UNRESOLVED").length;

  const filteredDocs = documents.filter((d) => {
    if (filter === "all") return true;
    if (filter === "anomalies") return (d.anomalies && d.anomalies.length > 0) || d.status === "ANOMALY" || d.status === "SUSPICIOUS";
    if (filter === "clean") return d.status === "CLEAN" && (!d.anomalies || d.anomalies.length === 0);
    if (filter === "unresolved") return d.status === "UNRESOLVED";
    return true;
  });

  const getStatusBadge = (status: string) => {
    const s = (status || "").toUpperCase();
    switch (s) {
      case "CLEAN":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            <span>CLEAN</span>
          </span>
        );
      case "SUSPICIOUS":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-400 dark:bg-amber-950/50 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>SUSPICIOUS</span>
          </span>
        );
      case "ANOMALY":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300 dark:bg-rose-950/40 dark:text-rose-300">
            <AlertOctagon className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
            <span>ANOMALY</span>
          </span>
        );
      case "UNRESOLVED":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300">
            <HelpCircle className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
            <span>{status || "UNRESOLVED"}</span>
          </span>
        );
    }
  };

  const getSeverityBadge = (severity: string) => {
    const s = (severity || "").toUpperCase();
    switch (s) {
      case "CRITICAL":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-rose-100 text-rose-900 border border-rose-300 dark:bg-rose-950/60 dark:text-rose-200">
            <AlertOctagon className="h-3 w-3 text-rose-600 dark:text-rose-400" aria-hidden="true" />
            <span>CRITICAL</span>
          </span>
        );
      case "HIGH":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-red-50 text-red-800 border border-red-200 dark:bg-red-950/40 dark:text-red-300">
            <AlertTriangle className="h-3 w-3 text-red-600 dark:text-red-400" aria-hidden="true" />
            <span>HIGH</span>
          </span>
        );
      case "MEDIUM":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950/40 dark:text-amber-200">
            <AlertTriangle className="h-3 w-3 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>MEDIUM</span>
          </span>
        );
      case "LOW":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300">
            <Info className="h-3 w-3 text-slate-500" aria-hidden="true" />
            <span>LOW</span>
          </span>
        );
      case "INFORMATIONAL":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-surface-container text-on-surface-variant border border-outline-variant/30">
            <Info className="h-3 w-3 text-outline" aria-hidden="true" />
            <span>{severity || "INFO"}</span>
          </span>
        );
    }
  };

  const getOverallBanner = () => {
    if (overallStatus === "CLEAN" && totalAnomalies === 0) {
      return {
        bg: "bg-emerald-50 border-emerald-300 text-emerald-950 dark:bg-emerald-950/30 dark:border-emerald-800 dark:text-emerald-200",
        icon: <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />,
        title: "No Integrity Anomalies Reported",
        description:
          documentForensics.summary ||
          "All evaluated document streams, formatting structures, metadata timestamps, and cryptographic hashes show no integrity anomalies.",
      };
    }

    if (overallStatus === "ANOMALY" || overallStatus === "SUSPICIOUS" || totalAnomalies > 0) {
      return {
        bg: "bg-rose-50 border-rose-300 text-rose-950 dark:bg-rose-950/30 dark:border-rose-800 dark:text-rose-200",
        icon: <AlertOctagon className="h-6 w-6 text-rose-600 dark:text-rose-400 shrink-0" aria-hidden="true" />,
        title: `${totalAnomalies} Document Integrity ${totalAnomalies === 1 ? "Finding" : "Findings"} Reported`,
        description:
          documentForensics.summary ||
          "Automated file analysis detected document structure, metadata, or formatting anomalies requiring technical inspection.",
      };
    }

    return {
      bg: "bg-amber-50 border-amber-300 text-amber-950 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-200",
      icon: <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400 shrink-0" aria-hidden="true" />,
      title: "Forensic Analysis Incomplete or Unresolved",
      description:
        documentForensics.summary ||
        "One or more documents could not be fully analyzed for integrity (unreadable PDF stream, missing file, or unsupported format).",
    };
  };

  const banner = getOverallBanner();

  const formatAnomalyType = (type: string) => {
    if (!type) return "INTEGRITY ANOMALY";
    return type.replace(/_/g, " ").toUpperCase();
  };

  return (
    <section
      aria-labelledby="document-forensics-heading"
      className="bg-surface-container-lowest rounded-xl p-5 md:p-6 shadow-subtle border border-outline-variant/30 space-y-5 font-sans"
    >
      {/* 1. Header & Introductory Text */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-outline-variant/20">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <FileSearch className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
            <h3 id="document-forensics-heading" className="text-base font-bold text-on-surface">
              Document Forensics
            </h3>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono">
              {documents.length} {documents.length === 1 ? "file" : "files"}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            Provides file integrity, document structure, and anomaly analysis from the autonomous verification pipeline. Evaluates PDF streams, file hashes, metadata attributes, and formatting consistency across submitted artifacts.
          </p>
        </div>

        {/* Filter Controls */}
        {documents.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setFilter("all")}
              aria-label={`Filter all ${documents.length} documents`}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                filter === "all"
                  ? "bg-primary text-white"
                  : "bg-surface-container text-on-surface-variant hover:text-on-surface"
              }`}
            >
              All ({documents.length})
            </button>
            {anomalyDocsCount > 0 && (
              <button
                onClick={() => setFilter("anomalies")}
                aria-label={`Filter ${anomalyDocsCount} documents with anomalies`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "anomalies"
                    ? "bg-error text-white"
                    : "bg-rose-50 text-rose-800 hover:bg-rose-100 border border-rose-200"
                }`}
              >
                Findings ({anomalyDocsCount})
              </button>
            )}
            {cleanDocsCount > 0 && (
              <button
                onClick={() => setFilter("clean")}
                aria-label={`Filter ${cleanDocsCount} clean documents`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "clean"
                    ? "bg-emerald-700 text-white"
                    : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200"
                }`}
              >
                Clean ({cleanDocsCount})
              </button>
            )}
            {unresolvedDocsCount > 0 && (
              <button
                onClick={() => setFilter("unresolved")}
                aria-label={`Filter ${unresolvedDocsCount} unresolved documents`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "unresolved"
                    ? "bg-amber-700 text-white"
                    : "bg-amber-50 text-amber-900 hover:bg-amber-100 border border-amber-300"
                }`}
              >
                Unresolved ({unresolvedDocsCount})
              </button>
            )}
          </div>
        )}
      </div>

      {/* 2. Informational Isolation Notice */}
      <div className="p-3 bg-surface-container-low/70 border border-outline-variant/30 rounded-lg text-xs text-on-surface-variant flex items-start gap-2">
        <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
        <span className="leading-relaxed">
          <strong>Analytical Notice:</strong> Document forensics findings provide automated file-level integrity observations and technical diagnostic metrics. These findings serve as evidence for procurement officers and do not independently alter the statutory qualification verdict.
        </span>
      </div>

      {/* 3. Overall Summary Banner */}
      <div className={`p-4 rounded-xl border flex items-start gap-3.5 transition-all ${banner.bg}`}>
        {banner.icon}
        <div className="space-y-1 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h4 className="text-sm font-bold font-sans tracking-tight">
              {banner.title}
            </h4>
            {getStatusBadge(overallStatus)}
            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-black/10 text-on-surface">
              Risk: {overallRisk}
            </span>
          </div>
          <p className="text-xs leading-relaxed opacity-95">
            {banner.description}
          </p>
        </div>
      </div>

      {/* 4. Per-Document Cards */}
      {documents.length === 0 ? (
        <div className="text-center py-8 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-6 space-y-1 font-sans">
          <Layers className="h-6 w-6 text-outline mx-auto" aria-hidden="true" />
          <p className="font-semibold text-on-surface">No Document Records Found</p>
          <p>No document files were attached to this verification execution for forensic evaluation.</p>
        </div>
      ) : filteredDocs.length === 0 ? (
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4 font-sans">
          No documents match filter &quot;{filter}&quot;.
        </div>
      ) : (
        <div className="space-y-4">
          {filteredDocs.map((doc: ForensicDocumentResult, idx: number) => {
            const docKey = doc.document_id || doc.source_document || `doc-${idx}`;
            const docStatus = (doc.status || "UNRESOLVED").toUpperCase();
            const anomalies = doc.anomalies || [];
            const hasAnomalies = anomalies.length > 0;
            const isExpanded = expandedDocs[docKey] ?? hasAnomalies; // Auto-expand if anomalies exist

            const borderClass =
              docStatus === "CLEAN"
                ? "border-emerald-200 dark:border-emerald-800/60"
                : docStatus === "ANOMALY" || docStatus === "SUSPICIOUS"
                ? "border-red-300 dark:border-red-800/70"
                : "border-amber-300 dark:border-amber-700/60";

            const barBg =
              docStatus === "CLEAN"
                ? "bg-emerald-600"
                : docStatus === "ANOMALY" || docStatus === "SUSPICIOUS"
                ? "bg-error"
                : "bg-amber-500";

            return (
              <article
                key={docKey}
                aria-label={`Forensics for ${doc.source_document || "document"}`}
                className={`bg-surface-container-lowest rounded-xl p-5 border ${borderClass} shadow-subtle relative overflow-hidden space-y-3.5 transition-all`}
              >
                {/* Left status accent strip */}
                <div className={`absolute top-0 left-0 w-1.5 h-full ${barBg}`} aria-hidden="true" />

                {/* Card Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                  <div className="flex items-center gap-2 flex-wrap min-w-0">
                    <FileText className="h-4 w-4 text-primary shrink-0" aria-hidden="true" />
                    <span
                      className="font-bold text-sm text-on-surface font-sans break-all"
                      title={doc.source_document}
                    >
                      {doc.source_document || "Submitted Document"}
                    </span>
                    {doc.document_id && (
                      <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-surface-container text-on-surface-variant border border-outline-variant/30">
                        {doc.document_id}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {getStatusBadge(docStatus)}
                    <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">
                      Risk: {doc.risk_level || "LOW"}
                    </span>
                    {hasAnomalies && (
                      <button
                        onClick={() => toggleDocExpand(docKey)}
                        aria-expanded={isExpanded}
                        aria-label={`${isExpanded ? "Collapse" : "Expand"} anomalies for ${doc.source_document}`}
                        className="p-1 rounded hover:bg-surface-container text-on-surface-variant transition-colors"
                      >
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4" aria-hidden="true" />
                        ) : (
                          <ChevronDown className="h-4 w-4" aria-hidden="true" />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Document Metadata Strip */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 text-xs bg-surface-container-low/60 p-3 rounded-lg border border-outline-variant/20">
                  {/* MIME / File format */}
                  <div>
                    <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
                      Format / Stream
                    </span>
                    <span className="font-mono text-on-surface font-medium">
                      {doc.mime_type || doc.file_type || (doc.source_document.toLowerCase().endsWith(".pdf") ? "application/pdf" : "PDF Document")}
                    </span>
                  </div>

                  {/* Cryptographic SHA-256 Digest */}
                  <div className="lg:col-span-2">
                    <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
                      SHA-256 Digest
                    </span>
                    {doc.sha256 ? (
                      <div className="flex items-center gap-2 font-mono text-[11px] text-on-surface pt-0.5">
                        <span className="truncate max-w-[280px]" title={doc.sha256}>
                          {doc.sha256}
                        </span>
                        <button
                          onClick={() => handleCopyHash(doc.sha256!)}
                          className="p-0.5 rounded hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors"
                          title="Copy SHA-256"
                          aria-label="Copy document SHA-256 hash"
                        >
                          {copiedHash === doc.sha256 ? (
                            <Check className="h-3 w-3 text-emerald-600" aria-hidden="true" />
                          ) : (
                            <Copy className="h-3 w-3" aria-hidden="true" />
                          )}
                        </button>
                      </div>
                    ) : (
                      <span className="text-[11px] font-mono text-on-surface-variant italic">
                        Hash not recorded
                      </span>
                    )}
                  </div>
                </div>

                {/* Status Narrative / Findings Summary */}
                {docStatus === "CLEAN" && anomalies.length === 0 ? (
                  <div className="text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2 bg-emerald-50/50 dark:bg-emerald-950/20 p-2.5 rounded-lg border border-emerald-200 dark:border-emerald-800/40">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" aria-hidden="true" />
                    <span>No reported anomalies. Document stream and metadata consistency confirmed.</span>
                  </div>
                ) : docStatus === "UNRESOLVED" && anomalies.length === 0 ? (
                  <div className="text-xs text-amber-800 dark:text-amber-300 flex items-center gap-2 bg-amber-50/50 dark:bg-amber-950/20 p-2.5 rounded-lg border border-amber-200 dark:border-amber-800/40">
                    <HelpCircle className="h-4 w-4 text-amber-600 shrink-0" aria-hidden="true" />
                    <span>Forensic stream analysis incomplete or inconclusive for this artifact.</span>
                  </div>
                ) : null}

                {/* Anomalies List */}
                {hasAnomalies && isExpanded && (
                  <div className="space-y-2.5 pt-2 border-t border-outline-variant/20">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-mono uppercase tracking-wider text-on-surface-variant flex items-center gap-1.5">
                        <AlertOctagon className="h-3.5 w-3.5 text-error" aria-hidden="true" />
                        <span>Detected Anomalies ({anomalies.length})</span>
                      </span>
                    </div>

                    <div className="space-y-2">
                      {anomalies.map((item: ForensicAnomalyItem, aIdx: number) => {
                        const hasPage = item.page_number !== null && item.page_number !== undefined;
                        const hasEvidence = item.evidence && Object.keys(item.evidence).length > 0;

                        return (
                          <div
                            key={item.anomaly_id || aIdx}
                            className="bg-surface-container-low/70 rounded-lg p-3.5 border border-outline-variant/25 text-xs space-y-2"
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-xs font-bold text-on-surface px-2 py-0.5 rounded bg-surface-container border border-outline-variant/30">
                                  {formatAnomalyType(item.anomaly_type)}
                                </span>
                                {item.anomaly_id && (
                                  <span className="font-mono text-[11px] text-on-surface-variant">
                                    ID: {item.anomaly_id}
                                  </span>
                                )}
                                {hasPage && (
                                  <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-surface-container text-on-surface">
                                    Page {item.page_number}
                                  </span>
                                )}
                              </div>
                              {getSeverityBadge(item.severity)}
                            </div>

                            {/* Description */}
                            <p className="text-xs text-on-surface leading-relaxed font-sans">
                              {item.description}
                            </p>

                            {/* Affected field if present */}
                            {item.affected_field && (
                              <div className="text-[11px] text-on-surface-variant font-mono">
                                Affected attribute: <span className="font-bold text-on-surface">{item.affected_field}</span>
                              </div>
                            )}

                            {/* Evidence / Technical Key-Values */}
                            {hasEvidence && (
                              <div className="pt-1.5 border-t border-outline-variant/20 space-y-1">
                                <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
                                  Technical Evidence Payload:
                                </span>
                                <div className="bg-surface-container-lowest p-2 rounded border border-outline-variant/20 font-mono text-[11px] text-on-surface overflow-x-auto space-y-1">
                                  {Object.entries(item.evidence!).map(([k, v]) => {
                                    const displayVal = extractHumanReadableValue(v, k);
                                    const isComplex = typeof v === "object" && v !== null && Object.keys(v).length > 1;

                                    return (
                                      <div key={k} className="py-0.5">
                                        <div className="flex items-start gap-2">
                                          <span className="text-on-surface-variant shrink-0">{k}:</span>
                                          <span className="font-semibold break-all text-on-surface">{displayVal}</span>
                                        </div>
                                        {isComplex && (
                                          <details className="mt-0.5 pl-3">
                                            <summary className="text-[10px] text-primary hover:underline cursor-pointer select-none">
                                              Details
                                            </summary>
                                            <pre className="p-1 bg-black/5 dark:bg-white/5 rounded text-[9px] overflow-x-auto mt-0.5 max-h-24 text-on-surface-variant whitespace-pre-wrap">
                                              {JSON.stringify(v, null, 2)}
                                            </pre>
                                          </details>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default DocumentForensics;
