import React, { useState } from "react";
import { Badge } from "../ui";
import { FolderLock, Hash, Copy, Check, FileText } from "lucide-react";

export interface EvidencePanelProps {
  evidenceSnapshot?: Array<Record<string, any>>;
  documentHashes?: Record<string, string>;
}

export const EvidencePanel: React.FC<EvidencePanelProps> = ({
  evidenceSnapshot = [],
  documentHashes = {},
}) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const hasDocs = Object.keys(documentHashes).length > 0;
  const hasEvidence = evidenceSnapshot.length > 0;

  return (
    <div className="space-y-6">
      {/* Document Cryptographic Hashes */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <Hash className="h-4 w-4 text-primary" />
            <span>Cryptographic Document Digests ({Object.keys(documentHashes).length})</span>
          </h3>
          <p className="text-xs text-on-surface-variant font-mono mt-0.5">
            SHA-256 cryptographic digests verifying document integrity and anti-tamper compliance
          </p>
        </div>

        {!hasDocs ? (
          <div className="text-center py-6 bg-surface-container-low/40 rounded-lg text-xs text-on-surface-variant">
            No document digests associated with this execution.
          </div>
        ) : (
          <div className="divide-y divide-outline-variant/20">
            {Object.entries(documentHashes).map(([docRef, sha256]) => (
              <div
                key={docRef}
                className="py-3 flex items-center justify-between hover:bg-surface-container-low px-2 rounded-lg transition-colors gap-4"
              >
                <div className="space-y-0.5 truncate">
                  <div className="text-xs font-semibold text-on-surface flex items-center gap-2 truncate">
                    <FileText className="h-3.5 w-3.5 text-primary shrink-0" />
                    <span className="truncate">{docRef}</span>
                  </div>
                  <div className="font-mono text-[11px] text-on-surface-variant truncate">
                    SHA-256: {sha256}
                  </div>
                </div>

                <button
                  onClick={() => handleCopy(sha256, docRef)}
                  className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors shrink-0"
                  title="Copy Document Hash"
                >
                  {copiedKey === docRef ? (
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evidence Snapshot */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <FolderLock className="h-4 w-4 text-primary" />
            <span>Evaluated Evidence Snapshot ({evidenceSnapshot.length})</span>
          </h3>
          <p className="text-xs text-on-surface-variant font-mono mt-0.5">
            Structured evidence extracted from bidder filings and statutory verification checks
          </p>
        </div>

        {!hasEvidence ? (
          <div className="text-center py-6 bg-surface-container-low/40 rounded-lg text-xs text-on-surface-variant">
            No structured evidence records captured.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {evidenceSnapshot.map((ev, idx) => (
              <div
                key={idx}
                className="p-3.5 bg-surface-container-low/50 rounded-lg border border-outline-variant/30 space-y-1.5"
              >
                <div className="flex items-center justify-between text-xs">
                  <span className="font-mono font-bold text-primary">
                    {ev.field || ev.key || `Evidence #${idx + 1}`}
                  </span>
                  {ev.confidence !== undefined && (
                    <Badge variant="success" size="sm">
                      {Math.round(ev.confidence * 100)}% Conf
                    </Badge>
                  )}
                </div>

                <div className="font-mono text-xs font-semibold text-on-surface break-words">
                  {typeof ev.value === "object" ? JSON.stringify(ev.value) : String(ev.value ?? "—")}
                </div>

                {(ev.source_document || ev.source_page) && (
                  <div className="text-[10px] font-mono text-on-surface-variant flex items-center gap-2 pt-1 border-t border-outline-variant/20">
                    {ev.source_document && <span>Source: {ev.source_document}</span>}
                    {ev.source_page && <span>Page: {ev.source_page}</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
