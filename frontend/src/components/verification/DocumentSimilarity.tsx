import React, { useState } from "react";
import {
  VerificationDocumentSimilarity,
  DocumentSimilarityComparison,
  DocumentReference,
} from "../../types";
import {
  CopyCheck,
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  HelpCircle,
  FileText,
  Copy,
  Check,
  Info,
  Layers,
  ArrowRightLeft,
  Percent,
} from "lucide-react";
import { Progress } from "../ui";

export interface DocumentSimilarityProps {
  documentSimilarity?: VerificationDocumentSimilarity | null;
  totalDocuments?: number;
}

export const DocumentSimilarity: React.FC<DocumentSimilarityProps> = ({
  documentSimilarity,
  totalDocuments,
}) => {
  const [filter, setFilter] = useState<
    "all" | "EXACT_DUPLICATE" | "HIGH_SIMILARITY" | "MODERATE_SIMILARITY" | "LOW_SIMILARITY"
  >("all");
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  // Missing data state
  if (!documentSimilarity) {
    return (
      <section
        aria-labelledby="document-similarity-heading"
        className="bg-surface-container-lowest rounded-xl p-6 shadow-subtle border border-outline-variant/30 space-y-3 font-sans"
      >
        <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20">
          <CopyCheck className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
          <div>
            <h3 id="document-similarity-heading" className="text-base font-bold text-on-surface">
              Document Similarity
            </h3>
            <p className="text-xs text-on-surface-variant">
              Compares cryptographic document digests and normalized text content across submitted artifacts.
            </p>
          </div>
        </div>
        <div className="py-8 text-center bg-surface-container-low/40 rounded-lg p-6 space-y-2">
          <HelpCircle className="h-8 w-8 text-outline mx-auto" aria-hidden="true" />
          <h4 className="text-sm font-semibold text-on-surface">Similarity Analysis Unavailable</h4>
          <p className="text-xs text-on-surface-variant max-w-md mx-auto">
            Document similarity data is not available for this verification run.
          </p>
        </div>
      </section>
    );
  }

  const overallStatus = (documentSimilarity.overall_status || "NO_COMPARISON").toUpperCase();
  const comparisons = documentSimilarity.comparisons || [];

  // Distinct documents participating in comparisons
  const distinctDocNames = new Set<string>();
  comparisons.forEach((c) => {
    if (c.document_a?.source_document) distinctDocNames.add(c.document_a.source_document);
    if (c.document_b?.source_document) distinctDocNames.add(c.document_b.source_document);
  });
  const docCount = totalDocuments || distinctDocNames.size;

  // Exact duplicate count
  const exactDuplicatesCount = comparisons.filter(
    (c) =>
      (c.status || "").toUpperCase() === "EXACT_DUPLICATE" ||
      (c.comparison_type || "").toUpperCase() === "EXACT_DUPLICATE"
  ).length;

  const highSimilarityCount = comparisons.filter(
    (c) => (c.status || "").toUpperCase() === "HIGH_SIMILARITY"
  ).length;

  const moderateSimilarityCount = comparisons.filter(
    (c) => (c.status || "").toUpperCase() === "MODERATE_SIMILARITY"
  ).length;

  const lowSimilarityCount = comparisons.filter(
    (c) => (c.status || "").toUpperCase() === "LOW_SIMILARITY"
  ).length;

  // Highest similarity score
  const validScores = comparisons
    .map((c) => c.similarity_score)
    .filter((s): s is number => typeof s === "number" && !isNaN(s));
  const highestScore = validScores.length > 0 ? Math.max(...validScores) : null;

  const filteredComparisons = comparisons.filter((c) => {
    if (filter === "all") return true;
    return (c.status || "").toUpperCase() === filter;
  });

  const getStatusBadge = (status: string) => {
    const s = (status || "").toUpperCase();
    switch (s) {
      case "EXACT_DUPLICATE":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-900 border border-rose-300 dark:bg-rose-950/60 dark:text-rose-200">
            <AlertOctagon className="h-3.5 w-3.5 text-rose-600 dark:text-rose-400" aria-hidden="true" />
            <span>EXACT DUPLICATE</span>
          </span>
        );
      case "HIGH_SIMILARITY":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-50 text-red-800 border border-red-300 dark:bg-red-950/40 dark:text-red-300">
            <AlertTriangle className="h-3.5 w-3.5 text-red-600 dark:text-red-400" aria-hidden="true" />
            <span>HIGH SIMILARITY</span>
          </span>
        );
      case "MODERATE_SIMILARITY":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950/40 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>MODERATE SIMILARITY</span>
          </span>
        );
      case "SIMILARITY_FOUND":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300 dark:bg-amber-950/40 dark:text-amber-200">
            <AlertTriangle className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <span>SIMILARITY FOUND</span>
          </span>
        );
      case "LOW_SIMILARITY":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            <span>LOW SIMILARITY</span>
          </span>
        );
      case "NO_COMPARISON":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-300 dark:bg-slate-800 dark:text-slate-300">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
            <span>LOW OVERLAP</span>
          </span>
        );
      case "INSUFFICIENT_REFERENCE_CORPUS":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-800 border border-amber-300 dark:bg-amber-950/40 dark:text-amber-200">
            <HelpCircle className="h-3.5 w-3.5 text-amber-600" aria-hidden="true" />
            <span>INSUFFICIENT CORPUS</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-surface-container text-on-surface-variant border border-outline-variant/30">
            <Info className="h-3.5 w-3.5 text-outline" aria-hidden="true" />
            <span>{status || "UNKNOWN"}</span>
          </span>
        );
    }
  };

  const getOverallBanner = () => {
    switch (overallStatus) {
      case "EXACT_DUPLICATE":
        return {
          bg: "bg-rose-50 border-rose-300 text-rose-950 dark:bg-rose-950/30 dark:border-rose-800 dark:text-rose-200",
          icon: <AlertOctagon className="h-6 w-6 text-rose-600 dark:text-rose-400 shrink-0" aria-hidden="true" />,
          title: "Exact Duplicate Document Identified",
          description:
            documentSimilarity.reason ||
            "Cryptographically identical document digests (SHA-256) were identified across submitted files.",
        };
      case "HIGH_SIMILARITY":
        return {
          bg: "bg-red-50 border-red-300 text-red-950 dark:bg-red-950/30 dark:border-red-800 dark:text-red-200",
          icon: <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400 shrink-0" aria-hidden="true" />,
          title: "High Content Overlap Identified",
          description:
            documentSimilarity.reason ||
            "Substantial content overlap detected across normalized text tokens of submitted files.",
        };
      case "MODERATE_SIMILARITY":
      case "SIMILARITY_FOUND":
        return {
          bg: "bg-amber-50 border-amber-300 text-amber-950 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-200",
          icon: <AlertTriangle className="h-6 w-6 text-amber-600 dark:text-amber-400 shrink-0" aria-hidden="true" />,
          title: "Moderate Content Overlap Identified",
          description:
            documentSimilarity.reason ||
            "Substantial or moderate content overlap detected across normalized text tokens of submitted files.",
        };
      case "INSUFFICIENT_REFERENCE_CORPUS":
        return {
          bg: "bg-amber-50 border-amber-300 text-amber-950 dark:bg-amber-950/30 dark:border-amber-800 dark:text-amber-200",
          icon: <HelpCircle className="h-6 w-6 text-amber-600 dark:text-amber-400 shrink-0" aria-hidden="true" />,
          title: "Insufficient Reference Corpus for Cross-Document Comparison",
          description:
            documentSimilarity.reason ||
            "Pairwise similarity comparison requires at least two comparable document files with readable text content.",
        };
      case "LOW_SIMILARITY":
      case "NO_COMPARISON":
        return {
          bg: "bg-surface-container-low/70 border-outline-variant/30 text-on-surface",
          icon: <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400 shrink-0" aria-hidden="true" />,
          title: "Low Content Overlap Observed",
          description:
            documentSimilarity.reason ||
            "Evaluated pairwise comparisons show low token overlap across submitted documents.",
        };
      default:
        return {
          bg: "bg-surface-container-low/70 border-outline-variant/30 text-on-surface",
          icon: <Info className="h-6 w-6 text-outline shrink-0" aria-hidden="true" />,
          title: `Assessment: ${overallStatus}`,
          description:
            documentSimilarity.reason ||
            "Document similarity assessment completed.",
        };
    }
  };

  const banner = getOverallBanner();

  const renderDocumentDocCard = (
    label: string,
    doc: DocumentReference,
    pageOverride?: number | null
  ) => {
    const pageNum = pageOverride !== null && pageOverride !== undefined ? pageOverride : doc.page_number;
    return (
      <div className="bg-surface-container-low/60 rounded-lg p-3 border border-outline-variant/20 space-y-1.5 text-xs">
        <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
          {label}
        </span>
        <div className="flex items-center gap-1.5 font-sans font-semibold text-on-surface">
          <FileText className="h-3.5 w-3.5 text-primary shrink-0" aria-hidden="true" />
          <span className="break-all" title={doc.source_document || "Document"}>
            {doc.source_document || "Submitted Document"}
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] text-on-surface-variant pt-0.5 flex-wrap">
          {doc.document_id && (
            <span>
              ID: <strong className="text-on-surface">{doc.document_id}</strong>
            </span>
          )}
          {pageNum !== null && pageNum !== undefined && (
            <span>
              Page: <strong className="text-on-surface">{pageNum}</strong>
            </span>
          )}
        </div>
        {doc.sha256 && (
          <div className="pt-1 flex items-center justify-between gap-1 font-mono text-[10px] text-on-surface-variant border-t border-outline-variant/20">
            <span className="truncate max-w-[200px]" title={doc.sha256}>
              {doc.sha256}
            </span>
            <button
              onClick={() => handleCopyHash(doc.sha256!)}
              className="p-0.5 rounded hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors shrink-0"
              title="Copy SHA-256"
              aria-label={`Copy SHA-256 for ${doc.source_document || label}`}
            >
              {copiedHash === doc.sha256 ? (
                <Check className="h-3 w-3 text-emerald-600" aria-hidden="true" />
              ) : (
                <Copy className="h-3 w-3" aria-hidden="true" />
              )}
            </button>
          </div>
        )}
      </div>
    );
  };

  return (
    <section
      aria-labelledby="document-similarity-heading"
      className="bg-surface-container-lowest rounded-xl p-5 md:p-6 shadow-subtle border border-outline-variant/30 space-y-5 font-sans"
    >
      {/* 1. Header & Introductory Text */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-outline-variant/20">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <CopyCheck className="h-5 w-5 text-primary shrink-0" aria-hidden="true" />
            <h3 id="document-similarity-heading" className="text-base font-bold text-on-surface">
              Document Similarity
            </h3>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant font-mono">
              {comparisons.length} {comparisons.length === 1 ? "comparison" : "comparisons"}
            </span>
          </div>
          <p className="text-xs text-on-surface-variant leading-relaxed">
            Compares cryptographic document digests (SHA-256) and normalized text content across submitted files to detect exact duplicates and evaluate content overlap across reference documents.
          </p>
        </div>

        {/* Filter Controls */}
        {comparisons.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setFilter("all")}
              aria-label={`Filter all ${comparisons.length} comparisons`}
              className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                filter === "all"
                  ? "bg-primary text-white"
                  : "bg-surface-container text-on-surface-variant hover:text-on-surface"
              }`}
            >
              All ({comparisons.length})
            </button>
            {exactDuplicatesCount > 0 && (
              <button
                onClick={() => setFilter("EXACT_DUPLICATE")}
                aria-label={`Filter ${exactDuplicatesCount} exact duplicates`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "EXACT_DUPLICATE"
                    ? "bg-rose-800 text-white"
                    : "bg-rose-50 text-rose-900 hover:bg-rose-100 border border-rose-300"
                }`}
              >
                Exact Duplicates ({exactDuplicatesCount})
              </button>
            )}
            {highSimilarityCount > 0 && (
              <button
                onClick={() => setFilter("HIGH_SIMILARITY")}
                aria-label={`Filter ${highSimilarityCount} high similarity comparisons`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "HIGH_SIMILARITY"
                    ? "bg-red-700 text-white"
                    : "bg-red-50 text-red-800 hover:bg-red-100 border border-red-200"
                }`}
              >
                High ({highSimilarityCount})
              </button>
            )}
            {moderateSimilarityCount > 0 && (
              <button
                onClick={() => setFilter("MODERATE_SIMILARITY")}
                aria-label={`Filter ${moderateSimilarityCount} moderate similarity comparisons`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "MODERATE_SIMILARITY"
                    ? "bg-amber-700 text-white"
                    : "bg-amber-50 text-amber-900 hover:bg-amber-100 border border-amber-300"
                }`}
              >
                Moderate ({moderateSimilarityCount})
              </button>
            )}
            {lowSimilarityCount > 0 && (
              <button
                onClick={() => setFilter("LOW_SIMILARITY")}
                aria-label={`Filter ${lowSimilarityCount} low similarity comparisons`}
                className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                  filter === "LOW_SIMILARITY"
                    ? "bg-emerald-700 text-white"
                    : "bg-emerald-50 text-emerald-800 hover:bg-emerald-100 border border-emerald-200"
                }`}
              >
                Low ({lowSimilarityCount})
              </button>
            )}
          </div>
        )}
      </div>

      {/* 2. Informational Isolation Notice */}
      <div className="p-3 bg-surface-container-low/70 border border-outline-variant/30 rounded-lg text-xs text-on-surface-variant flex items-start gap-2">
        <Info className="h-4 w-4 text-primary shrink-0 mt-0.5" aria-hidden="true" />
        <span className="leading-relaxed">
          <strong>Informational Comparison:</strong> Document similarity evaluations are descriptive structural metrics and do not independently determine bidder qualification, composite risk scores, or verification decisions. Content overlap may naturally occur in standard government tender boilerplates or regulatory certifications.
        </span>
      </div>

      {/* 3. Overall Status Banner */}
      <div className={`p-4 rounded-xl border flex items-start gap-3.5 transition-all ${banner.bg}`}>
        {banner.icon}
        <div className="space-y-1 flex-1">
          <div className="flex items-center gap-2.5 flex-wrap">
            <h4 className="text-sm font-bold font-sans tracking-tight">
              {banner.title}
            </h4>
            {getStatusBadge(overallStatus)}
          </div>
          <p className="text-xs leading-relaxed opacity-95">
            {banner.description}
          </p>
        </div>
      </div>

      {/* 4. Executive Summary KPI Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* Metric 1: Evaluated Documents */}
        <div className="bg-surface-container-lowest rounded-xl p-3.5 border border-outline-variant/30 space-y-1 shadow-subtle">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
            Documents
          </span>
          <div className="text-xl font-bold text-on-surface">
            {docCount > 0 ? docCount : "—"}
          </div>
          <span className="text-[11px] text-on-surface-variant">Compared in corpus</span>
        </div>

        {/* Metric 2: Comparisons */}
        <div className="bg-surface-container-lowest rounded-xl p-3.5 border border-outline-variant/30 space-y-1 shadow-subtle">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
            Pair Comparisons
          </span>
          <div className="text-xl font-bold text-on-surface font-mono">
            {comparisons.length}
          </div>
          <span className="text-[11px] text-on-surface-variant">Evaluated combinations</span>
        </div>

        {/* Metric 3: Exact Matches */}
        <div className="bg-surface-container-lowest rounded-xl p-3.5 border border-outline-variant/30 space-y-1 shadow-subtle">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
            Exact Duplicates
          </span>
          <div
            className={`text-xl font-bold ${
              exactDuplicatesCount > 0 ? "text-error" : "text-emerald-700 dark:text-emerald-400"
            }`}
          >
            {exactDuplicatesCount}
          </div>
          <span className="text-[11px] text-on-surface-variant">SHA-256 identical</span>
        </div>

        {/* Metric 4: Highest Similarity Score */}
        <div className="bg-surface-container-lowest rounded-xl p-3.5 border border-outline-variant/30 space-y-1 shadow-subtle">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
            Max Content Score
          </span>
          <div className="text-xl font-bold text-primary font-mono">
            {highestScore !== null ? `${(highestScore * 100).toFixed(1)}%` : "—"}
          </div>
          <span className="text-[11px] text-on-surface-variant">Highest token overlap</span>
        </div>

        {/* Metric 5: Reference Corpus */}
        <div className="bg-surface-container-lowest rounded-xl p-3.5 border border-outline-variant/30 space-y-1 shadow-subtle col-span-2 sm:col-span-1">
          <span className="text-[10px] uppercase font-mono tracking-wider text-on-surface-variant block">
            Reference Corpus
          </span>
          <div className="text-sm font-bold text-on-surface pt-1">
            {overallStatus === "INSUFFICIENT_REFERENCE_CORPUS" ? "Insufficient" : "Corpus Active"}
          </div>
          <span className="text-[11px] text-on-surface-variant">Corpus evaluation state</span>
        </div>
      </div>

      {/* 5. Comparisons List */}
      {comparisons.length === 0 ? (
        <div className="text-center py-8 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-6 space-y-1 font-sans">
          <Layers className="h-6 w-6 text-outline mx-auto" aria-hidden="true" />
          <p className="font-semibold text-on-surface">No Pairwise Comparisons</p>
          <p>
            {overallStatus === "INSUFFICIENT_REFERENCE_CORPUS"
              ? "Insufficient document artifacts were available to conduct pairwise similarity comparisons."
              : "No pairwise document similarity comparisons were recorded for this verification run."}
          </p>
        </div>
      ) : filteredComparisons.length === 0 ? (
        <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg p-4 font-sans">
          No document comparisons match filter &quot;{filter}&quot;.
        </div>
      ) : (
        <div className="space-y-4">
          {filteredComparisons.map((comp: DocumentSimilarityComparison) => {
            const compStatus = (comp.status || "LOW_SIMILARITY").toUpperCase();
            const compType = (comp.comparison_type || "CONTENT_SIMILARITY").toUpperCase();
            const scorePercent =
              typeof comp.similarity_score === "number" && !isNaN(comp.similarity_score)
                ? (comp.similarity_score * 100).toFixed(1)
                : null;
            const thresholdPercent =
              typeof comp.threshold === "number" && !isNaN(comp.threshold)
                ? (comp.threshold * 100).toFixed(0)
                : null;

            const borderClass =
              compStatus === "EXACT_DUPLICATE"
                ? "border-red-300 dark:border-red-800/70"
                : compStatus === "HIGH_SIMILARITY"
                ? "border-red-200 dark:border-red-800/60"
                : compStatus === "MODERATE_SIMILARITY"
                ? "border-amber-300 dark:border-amber-700/60"
                : "border-outline-variant/30";

            const barBg =
              compStatus === "EXACT_DUPLICATE"
                ? "bg-rose-600"
                : compStatus === "HIGH_SIMILARITY"
                ? "bg-error"
                : compStatus === "MODERATE_SIMILARITY"
                ? "bg-amber-500"
                : "bg-slate-400";

            return (
              <article
                key={comp.comparison_id}
                aria-label={`Comparison ${comp.comparison_id}`}
                className={`bg-surface-container-lowest rounded-xl p-5 border ${borderClass} shadow-subtle relative overflow-hidden space-y-4 transition-all`}
              >
                {/* Left status accent strip */}
                <div className={`absolute top-0 left-0 w-1.5 h-full ${barBg}`} aria-hidden="true" />

                {/* Header Line */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold text-on-surface px-2 py-0.5 rounded bg-surface-container border border-outline-variant/30">
                      {comp.comparison_id}
                    </span>
                    <span className="text-xs font-mono px-2 py-0.5 rounded bg-surface-container text-on-surface-variant">
                      {compType === "EXACT_DUPLICATE"
                        ? "EXACT SHA-256 MATCH"
                        : "NORMALIZED CONTENT SIMILARITY"}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {getStatusBadge(compStatus)}
                  </div>
                </div>

                {/* Score & Threshold Metric Strip */}
                <div className="bg-surface-container-low/40 p-3 rounded-lg border border-outline-variant/20 space-y-2">
                  <div className="flex items-center justify-between text-xs flex-wrap gap-2">
                    <div className="flex items-center gap-1.5 font-sans font-semibold text-on-surface">
                      <Percent className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
                      <span>Content Similarity Score:</span>
                      <strong className="font-mono text-sm text-primary">
                        {scorePercent !== null ? `${scorePercent}%` : "—"}
                      </strong>
                    </div>

                    {thresholdPercent !== null && (
                      <span className="text-[11px] font-mono text-on-surface-variant">
                        Classification Threshold: ≥{thresholdPercent}%
                      </span>
                    )}
                  </div>

                  {scorePercent !== null && (
                    <Progress
                      value={parseFloat(scorePercent)}
                      variant={
                        compStatus === "EXACT_DUPLICATE" || compStatus === "HIGH_SIMILARITY"
                          ? "error"
                          : compStatus === "MODERATE_SIMILARITY"
                          ? "warning"
                          : "primary"
                      }
                      size="sm"
                    />
                  )}
                </div>

                {/* Document Pair Comparison (Document A vs Document B) */}
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1 text-[11px] font-mono uppercase tracking-wider text-on-surface-variant">
                    <ArrowRightLeft className="h-3 w-3 text-primary" aria-hidden="true" />
                    <span>Compared Document Pair</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {renderDocumentDocCard("Document A (Source)", comp.document_a, comp.document_a_page)}
                    {renderDocumentDocCard("Document B (Reference)", comp.document_b, comp.document_b_page)}
                  </div>
                </div>

                {/* Neutral Comparison Explanation from Backend */}
                {comp.reason && (
                  <p className="text-xs text-on-surface-variant font-sans leading-relaxed pt-1 border-t border-outline-variant/20">
                    {comp.reason}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
};

export default DocumentSimilarity;
