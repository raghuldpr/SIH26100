import React from "react";
import { Link } from "react-router-dom";
import { FileText, Building2, ExternalLink } from "lucide-react";

export interface DocumentSourceLinkProps {
  tenderId?: string;
  bidderId?: string;
  tenderTitle?: string;
  bidderName?: string;
}

export const DocumentSourceLink: React.FC<DocumentSourceLinkProps> = ({
  tenderId,
  bidderId,
  tenderTitle,
  bidderName,
}) => {
  if (tenderId) {
    return (
      <Link
        to={`/tenders/${tenderId}`}
        className="inline-flex items-center gap-1.5 text-xs font-mono text-primary hover:underline group"
        title="View Originating Tender"
      >
        <FileText className="h-3.5 w-3.5 text-primary shrink-0" />
        <span className="truncate max-w-[140px] font-semibold">
          {tenderTitle || `Tender (${tenderId.slice(0, 8)})`}
        </span>
        <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
      </Link>
    );
  }

  if (bidderId) {
    return (
      <Link
        to={`/bidders/${bidderId}`}
        className="inline-flex items-center gap-1.5 text-xs font-mono text-emerald-800 hover:underline group"
        title="View Originating Bidder Entity"
      >
        <Building2 className="h-3.5 w-3.5 text-emerald-700 shrink-0" />
        <span className="truncate max-w-[140px] font-semibold">
          {bidderName || `Bidder (${bidderId.slice(0, 8)})`}
        </span>
        <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
      </Link>
    );
  }

  return <span className="text-[11px] font-mono text-on-surface-variant/60">Global Hub</span>;
};
