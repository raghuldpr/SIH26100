import React, { useState } from "react";
import { Hash, Copy, Check } from "lucide-react";

export interface DocumentHashProps {
  hash?: string;
  truncateLength?: number;
}

export const DocumentHash: React.FC<DocumentHashProps> = ({
  hash,
  truncateLength = 12,
}) => {
  const [copied, setCopied] = useState(false);

  if (!hash) {
    return <span className="text-[11px] font-mono text-on-surface-variant/60">—</span>;
  }

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(hash);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayHash =
    hash.length > truncateLength
      ? `${hash.slice(0, truncateLength)}...`
      : hash;

  return (
    <div className="inline-flex items-center gap-1.5 font-mono text-[11px] text-on-surface-variant bg-surface-container px-2 py-0.5 rounded border border-outline-variant/30">
      <Hash className="h-3 w-3 text-primary shrink-0" />
      <span title={hash} className="font-semibold text-on-surface">
        {displayHash}
      </span>
      <button
        onClick={handleCopy}
        className="text-on-surface-variant hover:text-primary transition-colors p-0.5 rounded"
        title="Copy SHA-256 Digest"
        aria-label="Copy SHA-256 Digest"
      >
        {copied ? (
          <Check className="h-3 w-3 text-emerald-600" />
        ) : (
          <Copy className="h-3 w-3" />
        )}
      </button>
    </div>
  );
};
