import React from "react";
import { Badge, StatusIndicator } from "../ui";
import { ProcessingStatus } from "../../types";

export interface DocumentStatusBadgeProps {
  status: ProcessingStatus | string;
}

export const DocumentStatusBadge: React.FC<DocumentStatusBadgeProps> = ({ status }) => {
  const s = (status || "").toUpperCase();

  switch (s) {
    case "PROCESSED":
      return <Badge variant="success" size="sm" dot>PROCESSED</Badge>;
    case "PROCESSING":
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold bg-primary/10 text-primary border border-primary/20">
          <StatusIndicator status="running" ping />
          <span>EXTRACTING OCR...</span>
        </span>
      );
    case "FAILED":
      return <Badge variant="danger" size="sm" dot>FAILED</Badge>;
    case "NOT_PROCESSED":
    default:
      return <Badge variant="neutral" size="sm">NOT PROCESSED</Badge>;
  }
};
