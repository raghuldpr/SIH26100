import React, { useState, useEffect, useCallback, useMemo } from "react";
import { listTenders, listTenderDocuments } from "../api/tenders";
import { listBidders, listBidderDocuments } from "../api/bidders";
import { getDocument, processDocument, retryDocument } from "../api/documents";
import { DocumentResponse, TenderResponse, BidderResponse } from "../types";
import {
  DocumentFilters,
  DocumentTable,
  DocumentPreviewModal,
} from "../components/documents";
import { Button } from "../components/ui";
import {
  FolderOpen,
  RefreshCw,
  AlertCircle,
} from "lucide-react";

export const Documents: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [tenders, setTenders] = useState<TenderResponse[]>([]);
  const [bidders, setBidders] = useState<BidderResponse[]>([]);

  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<"ALL" | "TENDER" | "BIDDER">("ALL");
  const [docType, setDocType] = useState("ALL");
  const [status, setStatus] = useState("ALL");

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected document for preview modal
  const [selectedDoc, setSelectedDoc] = useState<DocumentResponse | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // Fetch all contextual documents from existing backend endpoints
  const fetchAllDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch active tenders and bidders
      const [tendersRes, biddersRes] = await Promise.all([
        listTenders({ page_size: 20 }),
        listBidders({ page_size: 20 }),
      ]);

      const tList = tendersRes.data || tendersRes.items || [];
      const bList = biddersRes.data || biddersRes.items || [];
      setTenders(tList);
      setBidders(bList);

      // 2. Fetch documents for these tenders and bidders
      const tenderDocPromises = tList.map((t) =>
        listTenderDocuments(t.id).catch(() => ({ data: [] as DocumentResponse[] }))
      );
      const bidderDocPromises = bList.map((b) =>
        listBidderDocuments(b.id).catch(() => ({ data: [] as DocumentResponse[] }))
      );

      const [tenderDocResults, bidderDocResults] = await Promise.all([
        Promise.all(tenderDocPromises),
        Promise.all(bidderDocPromises),
      ]);

      const allDocs: DocumentResponse[] = [];

      tenderDocResults.forEach((res: any) => {
        const items: DocumentResponse[] = Array.isArray(res) ? res : res?.data || res?.items || [];
        allDocs.push(...items);
      });

      bidderDocResults.forEach((res: any) => {
        const items: DocumentResponse[] = Array.isArray(res) ? res : res?.data || res?.items || [];
        allDocs.push(...items);
      });

      // Deduplicate by ID
      const uniqueDocsMap = new Map<string, DocumentResponse>();
      allDocs.forEach((d) => {
        if (d && d.id) uniqueDocsMap.set(d.id, d);
      });

      setDocuments(Array.from(uniqueDocsMap.values()));
    } catch (err: any) {
      console.error("Failed to load documents:", err);
      setError(err?.message || "Failed to load document archives.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAllDocuments();
  }, [fetchAllDocuments]);

  // Handlers
  const handleViewDocument = (doc: DocumentResponse) => {
    setSelectedDoc(doc);
    setIsPreviewOpen(true);
  };

  const handleDownloadDocument = async (doc: DocumentResponse) => {
    try {
      const refreshed = await getDocument(doc.id);
      if (refreshed.download_url) {
        window.open(refreshed.download_url, "_blank");
      }
    } catch (err: any) {
      console.error("Failed to open document:", err);
    }
  };

  const handleProcessDocument = async (doc: DocumentResponse) => {
    try {
      const updated =
        doc.processing_status === "FAILED"
          ? await retryDocument(doc.id)
          : await processDocument(doc.id);

      setDocuments((prev) =>
        prev.map((d) => (d.id === updated.id ? updated : d))
      );
    } catch (err: any) {
      console.error("OCR execution error:", err);
    }
  };

  const handleDocumentUpdated = (updated: DocumentResponse) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === updated.id ? updated : d))
    );
  };

  // Filtered documents calculation
  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      // 1. Search term (filename or sha256)
      if (search.trim()) {
        const q = search.toLowerCase();
        const matchName = doc.original_filename?.toLowerCase().includes(q);
        const matchHash = doc.sha256?.toLowerCase().includes(q);
        const matchType = doc.document_type?.toLowerCase().includes(q);
        if (!matchName && !matchHash && !matchType) return false;
      }

      // 2. Category filter
      if (category === "TENDER" && !doc.tender_id) return false;
      if (category === "BIDDER" && !doc.bidder_id) return false;

      // 3. Document Type filter
      if (docType !== "ALL" && doc.document_type !== docType) return false;

      // 4. Processing Status filter
      if (status !== "ALL" && doc.processing_status !== status) return false;

      return true;
    });
  }, [documents, search, category, docType, status]);

  // Statistics
  const processedCount = documents.filter((d) => d.processing_status === "PROCESSED").length;
  const inProgressCount = documents.filter((d) => d.processing_status === "PROCESSING").length;
  const failedCount = documents.filter((d) => d.processing_status === "FAILED").length;

  return (
    <div className="space-y-6 font-sans">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-on-surface flex items-center gap-2">
            <FolderOpen className="h-6 w-6 text-primary" />
            <span>Document Vault &amp; OCR Pipeline Hub</span>
          </h1>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Inspect uploaded tender specifications, bidder statutory filings, and OCR extraction provenance
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAllDocuments}
            isLoading={isLoading}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Refresh Vault
          </Button>
        </div>
      </div>

      {/* KPI Tiles */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-1">
          <span className="text-[11px] font-mono uppercase text-on-surface-variant font-semibold">
            Total Vault Artifacts
          </span>
          <div className="text-2xl font-bold font-mono text-on-surface">
            {documents.length}
          </div>
          <span className="text-[10px] text-on-surface-variant font-mono">
            {tenders.length} Tenders • {bidders.length} Bidders
          </span>
        </div>

        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-1">
          <span className="text-[11px] font-mono uppercase text-on-surface-variant font-semibold">
            OCR Processed
          </span>
          <div className="text-2xl font-bold font-mono text-emerald-700">
            {processedCount}
          </div>
          <span className="text-[10px] text-emerald-700 font-mono">
            Extracted &amp; Indexed
          </span>
        </div>

        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-1">
          <span className="text-[11px] font-mono uppercase text-on-surface-variant font-semibold">
            Extracting OCR
          </span>
          <div className="text-2xl font-bold font-mono text-primary">
            {inProgressCount}
          </div>
          <span className="text-[10px] text-primary font-mono">
            Active Processing Pipeline
          </span>
        </div>

        <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-1">
          <span className="text-[11px] font-mono uppercase text-on-surface-variant font-semibold">
            Failed / Needs Retry
          </span>
          <div className="text-2xl font-bold font-mono text-rose-700">
            {failedCount}
          </div>
          <span className="text-[10px] text-rose-700 font-mono">
            Validation / OCR Errors
          </span>
        </div>
      </div>

      {/* Error Callout */}
      {error && (
        <div className="p-4 rounded-xl bg-error-container text-error text-xs flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" onClick={fetchAllDocuments}>
            Retry
          </Button>
        </div>
      )}

      {/* Filters Bar */}
      <DocumentFilters
        search={search}
        onSearchChange={setSearch}
        category={category}
        onCategoryChange={setCategory}
        docType={docType}
        onDocTypeChange={setDocType}
        status={status}
        onStatusChange={setStatus}
      />

      {/* Documents Table */}
      <DocumentTable
        documents={filteredDocuments}
        isLoading={isLoading}
        onViewDocument={handleViewDocument}
        onProcessDocument={handleProcessDocument}
        onDownloadDocument={handleDownloadDocument}
      />

      {/* Preview & Inspection Modal */}
      <DocumentPreviewModal
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
        document={selectedDoc}
        onDocumentUpdated={handleDocumentUpdated}
      />
    </div>
  );
};

export default Documents;
