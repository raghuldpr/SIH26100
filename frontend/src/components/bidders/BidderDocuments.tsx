import React, { useState, useEffect, useCallback } from "react";
import { uploadBidderDocument, listBidderDocuments } from "../../api/bidders";
import { DocumentResponse } from "../../types";
import { Badge, Button, Select, Skeleton } from "../ui";
import { UploadCloud, FileText, Download, CheckCircle2, AlertCircle, RefreshCw, FolderLock } from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface BidderDocumentsProps {
  bidderId: string;
}

export const BidderDocuments: React.FC<BidderDocumentsProps> = ({ bidderId }) => {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [documentType, setDocumentType] = useState("GST_CERTIFICATE");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const fetchDocs = useCallback(async () => {
    setIsLoading(true);
    try {
      const docs = await listBidderDocuments(bidderId);
      setDocuments(docs);
    } catch (err: any) {
      console.error("Failed to fetch bidder documents:", err);
    } finally {
      setIsLoading(false);
    }
  }, [bidderId]);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setStatusMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setStatusMessage(null);

    try {
      await uploadBidderDocument(bidderId, selectedFile, documentType);
      setSelectedFile(null);
      setStatusMessage({ text: "Compliance document uploaded successfully to vault.", type: "success" });
      await fetchDocs();
    } catch (err: any) {
      setStatusMessage({ text: err?.message || "Failed to upload document artifact.", type: "error" });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Box */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <FolderLock className="h-4 w-4 text-primary" />
              <span>Bidder Compliance &amp; Evidence Vault</span>
            </h3>
            <p className="text-xs text-on-surface-variant font-mono mt-0.5">
              Upload statutory proof, tax certificates, balance sheets, and credential proofs
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={fetchDocs} leftIcon={<RefreshCw className="h-3.5 w-3.5" />}>
            Refresh
          </Button>
        </div>

        {statusMessage && (
          <div
            className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
              statusMessage.type === "success"
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-error-container text-error"
            }`}
          >
            {statusMessage.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-error" />
            )}
            <span className="font-medium">{statusMessage.text}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
          <div className="sm:col-span-1">
            <Select
              label="Document Classification"
              value={documentType}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setDocumentType(e.target.value)}
              options={[
                { value: "GST_CERTIFICATE", label: "GST Registration Certificate" },
                { value: "PAN_CARD", label: "PAN Card / Tax Clearance" },
                { value: "UDYAM_CERTIFICATE", label: "MSME Udyam Certificate" },
                { value: "FINANCIAL_STATEMENT", label: "Audited Financials / Balance Sheet" },
                { value: "PAST_EXPERIENCE", label: "Past Experience / Work Order" },
                { value: "AFFIDAVIT", label: "Statutory Affidavit / Undertaking" },
                { value: "OTHER", label: "Other Technical Evidence" },
              ]}
              disabled={isUploading}
            />
          </div>

          <div className="sm:col-span-1">
            <label className="block text-xs font-semibold text-on-surface uppercase tracking-wider mb-1.5">
              Attachment (PDF / DOCX / Image)
            </label>
            <input
              type="file"
              accept=".pdf,.docx,.doc,.jpg,.jpeg,.png"
              onChange={handleFileChange}
              disabled={isUploading}
              className="block w-full text-xs text-on-surface file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-surface-container file:text-on-surface hover:file:bg-surface-container-high cursor-pointer"
            />
          </div>

          <div className="sm:col-span-1">
            <Button
              variant="primary"
              size="md"
              className="w-full"
              disabled={!selectedFile || isUploading}
              isLoading={isUploading}
              onClick={handleUpload}
              leftIcon={<UploadCloud className="h-4 w-4" />}
            >
              Upload Evidence
            </Button>
          </div>
        </div>
      </div>

      {/* Uploaded Documents List */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary" />
          <span>Uploaded Evidence Records ({documents.length})</span>
        </h3>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(2)].map((_, i) => (
              <div key={i} className="flex items-center justify-between p-3 border-b border-outline-variant/20">
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
            ))}
          </div>
        ) : documents.length === 0 ? (
          <div className="text-center py-6 text-xs text-on-surface-variant bg-surface-container-low/40 rounded-lg">
            No compliance documents uploaded for this bidder yet.
          </div>
        ) : (
          <div className="divide-y divide-outline-variant/20">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="py-3 flex items-center justify-between hover:bg-surface-container-low px-2 rounded-lg transition-colors"
              >
                <div className="space-y-0.5 truncate pr-4">
                  <div className="text-xs font-semibold text-on-surface flex items-center gap-2 truncate">
                    <FileText className="h-4 w-4 text-primary shrink-0" />
                    <span className="truncate">{doc.original_filename}</span>
                  </div>
                  <div className="text-[11px] text-on-surface-variant font-mono flex items-center gap-3">
                    <span>Type: {doc.document_type}</span>
                    {doc.file_size && <span>• Size: {Math.round(doc.file_size / 1024)} KB</span>}
                    {doc.sha256 && (
                      <span className="truncate max-w-[200px]" title={doc.sha256}>
                        • SHA-256: {doc.sha256.slice(0, 12)}...
                      </span>
                    )}
                    <span>• Uploaded: {formatDate(doc.created_at || doc.uploaded_at)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Badge
                    variant={doc.processing_status === "PROCESSED" ? "success" : "neutral"}
                    size="sm"
                    dot
                  >
                    {doc.processing_status || "STORED"}
                  </Badge>

                  {doc.download_url && (
                    <a
                      href={doc.download_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors"
                      title="Download document artifact"
                    >
                      <Download className="h-4 w-4" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
