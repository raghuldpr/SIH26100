import React, { useState } from "react";
import { DocumentResponse } from "../../types";
import { getDocument, processDocument, retryDocument } from "../../api/documents";
import { Modal, Button, Badge } from "../ui";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DocumentHash } from "./DocumentHash";
import {
  FileText,
  Download,
  Play,
  RotateCcw,
  HardDrive,
  AlertCircle,
  FileCode,
} from "lucide-react";
import { formatBytes, formatDate } from "../../lib/utils";

export interface DocumentPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  document: DocumentResponse | null;
  onDocumentUpdated?: (updated: DocumentResponse) => void;
}

export const DocumentPreviewModal: React.FC<DocumentPreviewModalProps> = ({
  isOpen,
  onClose,
  document: initialDoc,
  onDocumentUpdated,
}) => {
  const [doc, setDoc] = useState<DocumentResponse | null>(initialDoc);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  React.useEffect(() => {
    setDoc(initialDoc);
    setActionError(null);
  }, [initialDoc]);

  if (!doc) return null;

  const handleDownload = async () => {
    setIsDownloading(true);
    setActionError(null);
    try {
      const refreshed = await getDocument(doc.id);
      if (refreshed.download_url) {
        window.open(refreshed.download_url, "_blank");
      } else {
        setActionError("Download URL is currently unavailable for this document.");
      }
    } catch (err: any) {
      setActionError(err?.message || "Failed to generate secure download URL.");
    } finally {
      setIsDownloading(false);
    }
  };

  const handleProcess = async () => {
    setIsProcessing(true);
    setActionError(null);
    try {
      const updated = await processDocument(doc.id);
      setDoc(updated);
      if (onDocumentUpdated) onDocumentUpdated(updated);
    } catch (err: any) {
      setActionError(err?.message || "OCR Processing execution failed.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRetry = async () => {
    setIsProcessing(true);
    setActionError(null);
    try {
      const updated = await retryDocument(doc.id);
      setDoc(updated);
      if (onDocumentUpdated) onDocumentUpdated(updated);
    } catch (err: any) {
      setActionError(err?.message || "Retry document processing failed.");
    } finally {
      setIsProcessing(false);
    }
  };

  const isOcrComplete = doc.processing_status === "PROCESSED";
  const isOcrFailed = doc.processing_status === "FAILED";

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-primary" />
          <span className="truncate max-w-md">{doc.original_filename}</span>
        </div>
      }
      footer={
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            {!isOcrComplete && !isOcrFailed && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleProcess}
                isLoading={isProcessing}
                leftIcon={<Play className="h-4 w-4" />}
              >
                Trigger OCR &amp; Extraction
              </Button>
            )}

            {isOcrFailed && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleRetry}
                isLoading={isProcessing}
                leftIcon={<RotateCcw className="h-4 w-4" />}
              >
                Retry Processing
              </Button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              isLoading={isDownloading}
              leftIcon={<Download className="h-4 w-4" />}
            >
              Download Artifact
            </Button>
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      }
    >
      <div className="space-y-6 text-xs font-sans">
        {/* Error Callout if any */}
        {actionError && (
          <div className="p-3 rounded-lg bg-error-container text-error text-xs flex items-center gap-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{actionError}</span>
          </div>
        )}

        {/* Technical Attributes Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-1">
            <span className="text-[10px] font-mono uppercase text-on-surface-variant font-semibold">
              Classification
            </span>
            <div className="font-mono font-bold text-on-surface truncate">
              {doc.document_type}
            </div>
          </div>

          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-1">
            <span className="text-[10px] font-mono uppercase text-on-surface-variant font-semibold">
              Processing Status
            </span>
            <div>
              <DocumentStatusBadge status={doc.processing_status} />
            </div>
          </div>

          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-1">
            <span className="text-[10px] font-mono uppercase text-on-surface-variant font-semibold">
              MIME / Size
            </span>
            <div className="font-mono text-on-surface truncate">
              {formatBytes(doc.file_size || 0)} ({doc.mime_type?.split("/")[1]?.toUpperCase() || "PDF"})
            </div>
          </div>

          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-1">
            <span className="text-[10px] font-mono uppercase text-on-surface-variant font-semibold">
              Uploaded At
            </span>
            <div className="font-mono text-on-surface truncate">
              {formatDate(doc.uploaded_at || doc.created_at)}
            </div>
          </div>
        </div>

        {/* Cryptographic SHA-256 Digest Card */}
        <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <span className="text-xs font-mono font-bold text-on-surface flex items-center gap-1.5">
            <HardDrive className="h-4 w-4 text-primary" />
            <span>Cryptographic Proof Digest (SHA-256):</span>
          </span>
          <DocumentHash hash={doc.sha256} truncateLength={32} />
        </div>

        {/* Processing Error Notice if failed */}
        {doc.processing_error && (
          <div className="p-3.5 bg-error-container text-error rounded-xl border border-error/20 space-y-1">
            <span className="text-xs font-bold font-mono uppercase tracking-wider flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4" />
              <span>Document Extraction Error Notice</span>
            </span>
            <p className="text-xs font-mono leading-relaxed">{doc.processing_error}</p>
          </div>
        )}

        {/* Structured OCR Key-Value Inspector */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold font-mono uppercase tracking-wider text-on-surface flex items-center gap-1.5">
              <FileCode className="h-4 w-4 text-primary" />
              <span>Extracted Structured Key-Values</span>
            </span>
            {doc.extracted_data && Object.keys(doc.extracted_data).length > 0 && (
              <Badge variant="success" size="sm">
                {Object.keys(doc.extracted_data).length} Fields Extracted
              </Badge>
            )}
          </div>

          {!doc.extracted_data || Object.keys(doc.extracted_data).length === 0 ? (
            <div className="p-6 bg-surface-container-low/50 rounded-xl border border-outline-variant/20 text-center font-mono text-on-surface-variant text-xs">
              No structured OCR data extracted yet. Click &quot;Trigger OCR &amp; Extraction&quot; to parse clauses.
            </div>
          ) : (
            <div className="p-4 bg-surface-container-low rounded-xl border border-outline-variant/25 max-h-64 overflow-y-auto custom-scrollbar font-mono text-xs">
              <pre className="text-on-surface whitespace-pre-wrap break-all leading-relaxed">
                {JSON.stringify(doc.extracted_data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};
