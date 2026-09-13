import React, { useState } from "react";
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
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-outline-variant/20">
          <div>
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Hash className="h-5 w-5 text-primary" />
              <span>Cryptographic Document Digests</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
                {Object.keys(documentHashes).length} files
              </span>
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              Deterministic SHA-256 cryptographic digests verifying document tamper-evidence and chain of custody
            </p>
          </div>
        </div>

        {!hasDocs ? (
          <div className="text-center py-8 bg-surface-container-low/40 rounded-xl text-xs text-on-surface-variant border border-dashed border-outline-variant/30">
            No document digests associated with this execution.
          </div>
        ) : (
          <div className="space-y-2.5">
            {Object.entries(documentHashes).map(([docRef, sha256]) => (
              <div
                key={docRef}
                className="p-3.5 bg-surface-container-low/50 rounded-xl border border-outline-variant/25 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-primary/30 transition-colors"
              >
                <div className="space-y-1 min-w-0 flex-1">
                  <div className="text-sm font-semibold text-on-surface flex items-center gap-2 truncate">
                    <FileText className="h-4 w-4 text-primary shrink-0" />
                    <span className="truncate">{docRef}</span>
                  </div>
                  <div className="font-mono text-xs text-on-surface-variant bg-surface-container/70 p-2 rounded-lg break-all border border-outline-variant/20">
                    <span className="text-slate-400 font-normal mr-1">SHA-256:</span>
                    {sha256}
                  </div>
                </div>

                <button
                  onClick={() => handleCopy(sha256, docRef)}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-primary bg-primary/10 hover:bg-primary/20 border border-primary/25 transition-colors self-start sm:self-center shrink-0"
                  title="Copy Document Hash"
                >
                  {copiedKey === docRef ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      <span>Copy Digest</span>
                    </>
                  )}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Evidence Snapshot */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-outline-variant/20">
          <div>
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <FolderLock className="h-5 w-5 text-primary" />
              <span>Evaluated Evidence Snapshot</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
                {evidenceSnapshot.length} points
              </span>
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              Structured evidence extracted from bidder filings, statutory lookups, and financial statements
            </p>
          </div>
        </div>

        {!hasEvidence ? (
          <div className="text-center py-8 bg-surface-container-low/40 rounded-xl text-xs text-on-surface-variant border border-dashed border-outline-variant/30">
            No structured evidence records captured.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {evidenceSnapshot.map((ev, idx) => (
              <div
                key={idx}
                className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2 hover:border-primary/30 transition-colors"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono font-bold text-sm text-primary">
                    {ev.field || ev.key || `Evidence #${idx + 1}`}
                  </span>
                  {ev.confidence !== undefined && (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200">
                      {Math.round(ev.confidence * 100)}% Conf
                    </span>
                  )}
                </div>

                <div className="font-mono text-xs font-medium text-on-surface bg-surface-container/60 p-2 rounded-lg border border-outline-variant/20 break-words">
                  {typeof ev.value === "object" ? JSON.stringify(ev.value) : String(ev.value ?? "—")}
                </div>

                {(ev.source_document || ev.source_page) && (
                  <div className="text-xs text-on-surface-variant flex items-center gap-2 pt-1.5 border-t border-outline-variant/20">
                    {ev.source_document && (
                      <span className="truncate">File: {ev.source_document}</span>
                    )}
                    {ev.source_page && (
                      <span className="shrink-0 font-medium">Page {ev.source_page}</span>
                    )}
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
