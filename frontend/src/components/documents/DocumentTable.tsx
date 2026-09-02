import React from "react";
import { DocumentResponse } from "../../types";
import { DocumentStatusBadge } from "./DocumentStatusBadge";
import { DocumentHash } from "./DocumentHash";
import { DocumentSourceLink } from "./DocumentSourceLink";
import { Button, Skeleton } from "../ui";
import { FileText, Eye, Download, Play, RotateCcw } from "lucide-react";
import { formatBytes, formatDate } from "../../lib/utils";

export interface DocumentTableProps {
  documents: DocumentResponse[];
  isLoading: boolean;
  onViewDocument: (doc: DocumentResponse) => void;
  onProcessDocument?: (doc: DocumentResponse) => void;
  onDownloadDocument?: (doc: DocumentResponse) => void;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents,
  isLoading,
  onViewDocument,
  onProcessDocument,
  onDownloadDocument,
}) => {
  if (isLoading) {
    return (
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex items-center justify-between py-3 border-b border-outline-variant/20">
            <div className="space-y-1.5 w-1/3">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-3 w-1/2" />
            </div>
            <Skeleton className="h-6 w-24" />
            <Skeleton className="h-6 w-32" />
            <Skeleton className="h-8 w-20" />
          </div>
        ))}
      </div>
    );
  }

  if (documents.length === 0) {
    return (
      <div className="text-center py-16 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-8 space-y-3 shadow-subtle">
        <FileText className="h-10 w-10 text-outline mx-auto" />
        <h3 className="text-sm font-semibold text-on-surface">No Documents Found</h3>
        <p className="text-xs text-on-surface-variant max-w-sm mx-auto font-mono">
          No compliance artifacts or tender notices match the selected filter criteria.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle overflow-hidden">
      <div className="overflow-x-auto custom-scrollbar">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-surface-container-low text-[11px] font-mono text-on-surface-variant uppercase tracking-wider border-b border-outline-variant/30">
            <tr>
              <th className="py-3.5 px-4 font-semibold">Document Artifact</th>
              <th className="py-3.5 px-4 font-semibold">Classification</th>
              <th className="py-3.5 px-4 font-semibold">Status</th>
              <th className="py-3.5 px-4 font-semibold">Origin Context</th>
              <th className="py-3.5 px-4 font-semibold">SHA-256 Digest</th>
              <th className="py-3.5 px-4 font-semibold">Size / Uploaded</th>
              <th className="py-3.5 px-4 font-semibold text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/20 font-sans">
            {documents.map((doc) => (
              <tr
                key={doc.id}
                className="hover:bg-surface-container-low/40 transition-colors group cursor-pointer"
                onClick={() => onViewDocument(doc)}
              >
                {/* Filename */}
                <td className="py-3.5 px-4">
                  <div className="flex items-center gap-2 max-w-[220px]">
                    <FileText className="h-4 w-4 text-primary shrink-0" />
                    <span className="font-semibold text-on-surface truncate" title={doc.original_filename}>
                      {doc.original_filename}
                    </span>
                  </div>
                </td>

                {/* Classification */}
                <td className="py-3.5 px-4 font-mono text-primary font-semibold whitespace-nowrap">
                  {doc.document_type}
                </td>

                {/* Status */}
                <td className="py-3.5 px-4 whitespace-nowrap">
                  <DocumentStatusBadge status={doc.processing_status} />
                </td>

                {/* Source Link */}
                <td className="py-3.5 px-4 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                  <DocumentSourceLink tenderId={doc.tender_id} bidderId={doc.bidder_id} />
                </td>

                {/* Hash */}
                <td className="py-3.5 px-4 whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                  <DocumentHash hash={doc.sha256} truncateLength={10} />
                </td>

                {/* Size & Date */}
                <td className="py-3.5 px-4 font-mono text-on-surface-variant whitespace-nowrap">
                  <div>{formatBytes(doc.file_size || 0)}</div>
                  <div className="text-[10px] text-outline">{formatDate(doc.uploaded_at || doc.created_at)}</div>
                </td>

                {/* Actions */}
                <td className="py-3.5 px-4 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-end gap-1.5">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => onViewDocument(doc)}
                      title="Inspect Document & OCR Extraction"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>

                    {onDownloadDocument && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onDownloadDocument(doc)}
                        title="Download Document"
                      >
                        <Download className="h-3.5 w-3.5" />
                      </Button>
                    )}

                    {onProcessDocument && doc.processing_status !== "PROCESSED" && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onProcessDocument(doc)}
                        title={doc.processing_status === "FAILED" ? "Retry OCR" : "Trigger OCR"}
                      >
                        {doc.processing_status === "FAILED" ? (
                          <RotateCcw className="h-3.5 w-3.5 text-amber-600" />
                        ) : (
                          <Play className="h-3.5 w-3.5 text-primary" />
                        )}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
