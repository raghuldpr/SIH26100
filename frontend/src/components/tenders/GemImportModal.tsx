import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { lookupGemTender, importGemTender } from "../../api/gem";
import { GeMLookupResponse, TenderResponse } from "../../types";
import { Button, Input, Modal, Badge } from "../ui";
import {
  Search,
  Download,
  AlertCircle,
  FileText,
  Building2,
  UploadCloud,
  ExternalLink,
  Trash2,
} from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface GemImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTenderImported: (tender: TenderResponse) => void;
}

export const GemImportModal: React.FC<GemImportModalProps> = ({
  isOpen,
  onClose,
  onTenderImported,
}) => {
  const navigate = useNavigate();

  // Search state
  const [bidId, setBidId] = useState("GEM/2026/B/8912401");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<GeMLookupResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Manual fallback fields if unavailable or manual edit
  const [manualTitle, setManualTitle] = useState("");
  const [manualOrg, setManualOrg] = useState("");
  const [manualDept, setManualDept] = useState("General");
  const [manualCategory, setManualCategory] = useState("General");

  // Document attachment state
  const [manualFile, setManualFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Import execution state
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const resetModal = () => {
    setBidId("GEM/2026/B/8912401");
    setSearchResult(null);
    setSearchError(null);
    setManualTitle("");
    setManualOrg("");
    setManualDept("General");
    setManualCategory("General");
    setManualFile(null);
    setImportError(null);
    setIsSearching(false);
    setIsImporting(false);
  };

  const handleClose = () => {
    resetModal();
    onClose();
  };

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!bidId.trim()) {
      setSearchError("Please enter a valid GeM Bid ID.");
      return;
    }

    setSearchError(null);
    setSearchResult(null);
    setImportError(null);
    setIsSearching(true);

    try {
      const result = await lookupGemTender(bidId.trim());
      setSearchResult(result);

      if (result.status === "found" && result.gem_data) {
        setManualTitle(result.gem_data.title);
        setManualOrg(result.gem_data.organization);
        setManualDept(result.gem_data.department || "General");
        setManualCategory(result.gem_data.category || "General");
      } else if (result.status === "unavailable") {
        setManualTitle(`GeM Procurement Tender ${bidId.trim()}`);
        setManualOrg("GeM Procuring Organization");
      }
    } catch (err: any) {
      console.error("GeM lookup failed:", err);
      setSearchError(err?.message || "Failed to search GeM tender. Please check your network or try again.");
    } finally {
      setIsSearching(false);
    }
  };

  const handleImport = async () => {
    if (!searchResult) return;

    setImportError(null);
    setIsImporting(true);

    try {
      const formData = new FormData();
      formData.append("bid_id", searchResult.bid_id);

      const titleToUse = manualTitle.trim() || searchResult.gem_data?.title || `GeM Tender ${searchResult.bid_id}`;
      const orgToUse = manualOrg.trim() || searchResult.gem_data?.organization || "GeM Procuring Entity";

      formData.append("title", titleToUse);
      formData.append("organization", orgToUse);
      formData.append("department", manualDept.trim() || searchResult.gem_data?.department || "General");
      formData.append("category", manualCategory.trim() || searchResult.gem_data?.category || "General");

      if (searchResult.gem_data?.published_date) {
        formData.append("bid_start_date", searchResult.gem_data.published_date);
      }
      if (searchResult.gem_data?.bid_end_date) {
        formData.append("bid_end_date", searchResult.gem_data.bid_end_date);
      }

      // Attach file if provided manually
      if (manualFile) {
        formData.append("file", manualFile);
      }

      const importedTender = await importGemTender(formData);
      onTenderImported(importedTender);
      handleClose();
      navigate(`/tenders/${importedTender.id}`);
    } catch (err: any) {
      console.error("GeM import failed:", err);
      setImportError(err?.message || "Failed to import GeM tender into database.");
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Import Tender from GeM"
      maxWidth="lg"
    >
      <div className="space-y-5 text-on-surface">
        {/* Search Bar Form */}
        <form onSubmit={handleSearch} className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-on-surface mb-1">
              GeM Bid / Tender ID *
            </label>
            <div className="flex gap-2">
              <div className="flex-1">
                <Input
                  placeholder="e.g. GEM/2026/B/8912401"
                  value={bidId}
                  onChange={(e) => setBidId(e.target.value)}
                  disabled={isSearching || isImporting}
                  leftIcon={<Search className="h-4 w-4 text-outline" />}
                />
              </div>
              <Button
                type="submit"
                variant="primary"
                size="md"
                isLoading={isSearching}
                disabled={!bidId.trim() || isSearching || isImporting}
                leftIcon={<Search className="h-4 w-4" />}
              >
                Search
              </Button>
            </div>
            <p className="text-[11px] text-on-surface-variant mt-1 font-mono">
              Try demo ID: <button type="button" onClick={() => setBidId("GEM/2026/B/8912401")} className="text-primary hover:underline font-semibold">GEM/2026/B/8912401</button> or <button type="button" onClick={() => setBidId("GEM/2026/B/9876543")} className="text-primary hover:underline font-semibold">GEM/2026/B/9876543</button>
            </p>
          </div>
        </form>

        {/* Search Error Alert */}
        {searchError && (
          <div className="p-3.5 rounded-xl bg-error-container text-error text-xs flex items-center gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="font-medium">{searchError}</span>
          </div>
        )}

        {/* Import Error Alert */}
        {importError && (
          <div className="p-3.5 rounded-xl bg-error-container text-error text-xs flex items-center gap-2.5">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span className="font-medium">{importError}</span>
          </div>
        )}

        {/* Result State 1: Already Imported */}
        {searchResult && searchResult.already_imported && (
          <div className="p-4 rounded-xl border border-warning/40 bg-warning/5 space-y-3 animate-in fade-in">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-warning/10 text-warning shrink-0">
                <AlertCircle className="h-5 w-5" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-on-surface">GeM Tender Already Imported</h4>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  {searchResult.message || "This tender has already been persisted in TenderTrust."}
                </p>
                {searchResult.existing_tender && (
                  <div className="mt-2 text-xs font-mono space-y-1">
                    <div><span className="text-on-surface-variant">Title:</span> <span className="font-semibold">{searchResult.existing_tender.title}</span></div>
                    <div><span className="text-on-surface-variant">Organization:</span> {searchResult.existing_tender.organization}</div>
                  </div>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-warning/20">
              <Button variant="outline" size="sm" onClick={handleClose}>
                Close
              </Button>
              {searchResult.existing_tender_id && (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => {
                    handleClose();
                    navigate(`/tenders/${searchResult.existing_tender_id}`);
                  }}
                  rightIcon={<ExternalLink className="h-4 w-4" />}
                >
                  Open Tender
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Result State 2: Found via GeM */}
        {searchResult && !searchResult.already_imported && searchResult.status === "found" && searchResult.gem_data && (
          <div className="space-y-4 animate-in fade-in">
            <div className="p-4 rounded-xl border border-primary/30 bg-surface-container-low space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Badge variant="primary" size="sm">GeM Verified</Badge>
                  <span className="text-xs font-mono font-bold text-on-surface">
                    {searchResult.gem_data.bid_id}
                  </span>
                </div>
                <Badge variant="success" size="sm">
                  {searchResult.gem_data.status || "Active"}
                </Badge>
              </div>

              <div>
                <h3 className="text-sm font-bold text-on-surface">
                  {searchResult.gem_data.title}
                </h3>
                <div className="flex items-center gap-1.5 text-xs text-on-surface-variant mt-1 font-mono">
                  <Building2 className="h-3.5 w-3.5 shrink-0" />
                  <span>{searchResult.gem_data.organization}</span>
                  {searchResult.gem_data.department && (
                    <span>• {searchResult.gem_data.department}</span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2 border-t border-outline-variant/30 text-xs font-mono">
                <div>
                  <span className="text-[11px] text-on-surface-variant block">Category</span>
                  <span className="font-semibold text-on-surface">{searchResult.gem_data.category}</span>
                </div>
                <div>
                  <span className="text-[11px] text-on-surface-variant block">Bid End Date</span>
                  <span className="font-semibold text-on-surface">
                    {searchResult.gem_data.bid_end_date ? formatDate(searchResult.gem_data.bid_end_date) : "N/A"}
                  </span>
                </div>
                <div>
                  <span className="text-[11px] text-on-surface-variant block">Est. Contract Value</span>
                  <span className="font-semibold text-on-surface">
                    {searchResult.gem_data.estimated_value
                      ? `₹${searchResult.gem_data.estimated_value.toLocaleString("en-IN")}`
                      : "Not Disclosed"}
                  </span>
                </div>
              </div>
            </div>

            {/* Document section */}
            <div className="p-3.5 rounded-xl border border-outline-variant/30 bg-surface-container-lowest flex items-center justify-between text-xs">
              <div className="flex items-center gap-2.5">
                <FileText className="h-5 w-5 text-primary shrink-0" />
                <div>
                  <div className="font-semibold text-on-surface">Official GeM NIT Document</div>
                  <div className="text-[11px] text-on-surface-variant font-mono">
                    {searchResult.gem_data.document_available
                      ? searchResult.gem_data.document_name || "Official NIT Document Attached"
                      : "Document not accessible automatically"}
                  </div>
                </div>
              </div>

              {searchResult.gem_data.document_available ? (
                <Badge variant="success" size="sm">
                  Ready for Ingestion
                </Badge>
              ) : (
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="text-xs text-primary hover:underline font-semibold"
                >
                  Upload Manually
                </button>
              )}
            </div>

            {/* Manual file upload dropzone if document not available or user wants to override */}
            {!searchResult.gem_data.document_available && (
              <div>
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".pdf"
                  className="hidden"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      setManualFile(e.target.files[0]);
                    }
                  }}
                />
                {!manualFile ? (
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className="border-2 border-dashed border-outline-variant/50 rounded-xl p-4 text-center cursor-pointer hover:border-primary/50 text-xs"
                  >
                    <UploadCloud className="h-5 w-5 mx-auto text-outline mb-1" />
                    <span className="font-semibold text-on-surface">Click to attach official GeM tender NIT PDF</span>
                  </div>
                ) : (
                  <div className="p-2.5 rounded-lg bg-surface-container border border-outline-variant/40 flex items-center justify-between text-xs font-mono">
                    <span className="truncate">{manualFile.name}</span>
                    <button onClick={() => setManualFile(null)} className="text-error p-1">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" size="md" onClick={handleClose} disabled={isImporting}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleImport}
                isLoading={isImporting}
                leftIcon={<Download className="h-4 w-4" />}
              >
                {isImporting ? "Importing to Database..." : "Import Tender"}
              </Button>
            </div>
          </div>
        )}

        {/* Result State 3: Unavailable with Manual Fallback */}
        {searchResult && !searchResult.already_imported && searchResult.status === "unavailable" && (
          <div className="space-y-4 animate-in fade-in">
            <div className="p-3.5 rounded-xl bg-surface-container-low border border-outline-variant/40 text-xs space-y-1">
              <div className="flex items-center gap-2 text-on-surface font-semibold">
                <AlertCircle className="h-4 w-4 text-primary shrink-0" />
                <span>GeM Automated Retrieval Notice</span>
              </div>
              <p className="text-on-surface-variant text-[11px] leading-relaxed">
                Direct automated lookup on the GeM portal is protected or currently unreachable.
                You can specify the tender details and attach the official GeM NIT document manually below to complete persistent import.
              </p>
            </div>

            <div className="space-y-3">
              <Input
                label="GeM Bid ID *"
                value={bidId}
                disabled
              />
              <Input
                label="Tender Title *"
                placeholder="e.g. GeM Custom Bid for IT Infrastructure Support"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                disabled={isImporting}
              />
              <Input
                label="Procuring Organization *"
                placeholder="e.g. Ministry of Heavy Industries"
                value={manualOrg}
                onChange={(e) => setManualOrg(e.target.value)}
                disabled={isImporting}
              />
            </div>

            {/* File Dropzone */}
            <div>
              <label className="block text-xs font-semibold text-on-surface mb-1">
                Official GeM Tender / NIT PDF Document
              </label>
              <input
                type="file"
                ref={fileInputRef}
                accept=".pdf"
                className="hidden"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setManualFile(e.target.files[0]);
                  }
                }}
              />
              {!manualFile ? (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="border-2 border-dashed border-outline-variant/60 rounded-xl p-5 text-center cursor-pointer hover:border-primary/50 text-xs"
                >
                  <UploadCloud className="h-6 w-6 mx-auto text-primary mb-1" />
                  <div className="font-semibold text-on-surface">Click to select official GeM NIT PDF</div>
                  <div className="text-[11px] text-on-surface-variant font-mono">Enables automated clause parsing &amp; verification</div>
                </div>
              ) : (
                <div className="p-3 rounded-lg bg-surface-container border border-outline-variant/40 flex items-center justify-between text-xs font-mono">
                  <div className="flex items-center gap-2 truncate">
                    <FileText className="h-4 w-4 text-primary shrink-0" />
                    <span className="truncate">{manualFile.name}</span>
                  </div>
                  <button onClick={() => setManualFile(null)} className="text-error p-1">
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" size="md" onClick={handleClose} disabled={isImporting}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleImport}
                isLoading={isImporting}
                disabled={!manualTitle.trim() || !manualOrg.trim()}
                leftIcon={<Download className="h-4 w-4" />}
              >
                {isImporting ? "Importing to Database..." : "Import GeM Tender"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
};
