import React from "react";
import { Input, Select } from "../ui";
import { Search } from "lucide-react";

export interface DocumentFiltersProps {
  search: string;
  onSearchChange: (val: string) => void;
  category: "ALL" | "TENDER" | "BIDDER";
  onCategoryChange: (val: "ALL" | "TENDER" | "BIDDER") => void;
  docType: string;
  onDocTypeChange: (val: string) => void;
  status: string;
  onStatusChange: (val: string) => void;
}

export const DocumentFilters: React.FC<DocumentFiltersProps> = ({
  search,
  onSearchChange,
  category,
  onCategoryChange,
  docType,
  onDocTypeChange,
  status,
  onStatusChange,
}) => {
  return (
    <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
      {/* Search Filter */}
      <div>
        <Input
          placeholder="Search by filename or hash..."
          value={search}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) => onSearchChange(e.target.value)}
          leftIcon={<Search className="h-4 w-4 text-outline" />}
        />
      </div>

      {/* Scope / Category Filter */}
      <div>
        <Select
          value={category}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
            onCategoryChange(e.target.value as "ALL" | "TENDER" | "BIDDER")
          }
          options={[
            { value: "ALL", label: "All Document Vaults" },
            { value: "TENDER", label: "Tender Notices & Specs" },
            { value: "BIDDER", label: "Bidder Compliance Vaults" },
          ]}
        />
      </div>

      {/* Classification Type Filter */}
      <div>
        <Select
          value={docType}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onDocTypeChange(e.target.value)}
          options={[
            { value: "ALL", label: "All Document Classifications" },
            { value: "TENDER_NOTICE", label: "Tender Notice" },
            { value: "TECHNICAL_SPECIFICATION", label: "Technical Specification" },
            { value: "GST_CERTIFICATE", label: "GST Certificate" },
            { value: "PAN_CARD", label: "PAN Card" },
            { value: "UDYAM_CERTIFICATE", label: "Udyam Certificate" },
            { value: "FINANCIAL_STATEMENT", label: "Financial Statement" },
            { value: "PAST_EXPERIENCE", label: "Past Experience" },
            { value: "AFFIDAVIT", label: "Affidavit" },
            { value: "OTHER", label: "Other / Uncategorized" },
          ]}
        />
      </div>

      {/* Processing Status Filter */}
      <div>
        <Select
          value={status}
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onStatusChange(e.target.value)}
          options={[
            { value: "ALL", label: "All Processing Statuses" },
            { value: "PROCESSED", label: "Processed (OCR Complete)" },
            { value: "PROCESSING", label: "Processing (In Progress)" },
            { value: "FAILED", label: "Processing Failed" },
            { value: "NOT_PROCESSED", label: "Not Processed" },
          ]}
        />
      </div>
    </div>
  );
};
