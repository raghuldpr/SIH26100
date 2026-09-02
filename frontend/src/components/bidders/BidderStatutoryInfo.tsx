import React, { useState } from "react";
import { BidderResponse } from "../../types";
import { Badge } from "../ui";
import { Award, Check, Copy, FileBadge, Hash, Shield } from "lucide-react";

export interface BidderStatutoryInfoProps {
  bidder: BidderResponse;
}

export const BidderStatutoryInfo: React.FC<BidderStatutoryInfoProps> = ({ bidder }) => {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const handleCopy = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div>
          <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            <span>Statutory Registrations &amp; Tax Identifiers</span>
          </h3>
          <p className="text-xs text-on-surface-variant font-mono mt-0.5">
            Verified tax identifiers, incorporation numbers, and statutory certificates
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* GSTIN Card */}
          <div className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold flex items-center gap-1.5">
                <Hash className="h-3.5 w-3.5 text-primary" />
                <span>GSTIN (Goods &amp; Services Tax)</span>
              </span>
              {bidder.gst_number ? (
                <Badge variant="success" size="sm">Configured</Badge>
              ) : (
                <Badge variant="neutral" size="sm">Not Provided</Badge>
              )}
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="font-mono text-base font-bold text-on-surface">
                {bidder.gst_number || <span className="text-outline text-xs italic">Pending submission</span>}
              </span>
              {bidder.gst_number && (
                <button
                  onClick={() => handleCopy(bidder.gst_number!, "gst")}
                  className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors"
                  title="Copy GSTIN"
                >
                  {copiedKey === "gst" ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              )}
            </div>
          </div>

          {/* PAN Card */}
          <div className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold flex items-center gap-1.5">
                <FileBadge className="h-3.5 w-3.5 text-primary" />
                <span>PAN (Permanent Account Number)</span>
              </span>
              {bidder.pan_number ? (
                <Badge variant="success" size="sm">Configured</Badge>
              ) : (
                <Badge variant="neutral" size="sm">Not Provided</Badge>
              )}
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="font-mono text-base font-bold text-on-surface">
                {bidder.pan_number || <span className="text-outline text-xs italic">Pending submission</span>}
              </span>
              {bidder.pan_number && (
                <button
                  onClick={() => handleCopy(bidder.pan_number!, "pan")}
                  className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors"
                  title="Copy PAN"
                >
                  {copiedKey === "pan" ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              )}
            </div>
          </div>

          {/* Corporate CIN / Reg Card */}
          <div className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold flex items-center gap-1.5">
                <Award className="h-3.5 w-3.5 text-primary" />
                <span>Corporate CIN / Registration</span>
              </span>
              {bidder.registration_number ? (
                <Badge variant="primary" size="sm">Registered</Badge>
              ) : (
                <Badge variant="neutral" size="sm">Not Provided</Badge>
              )}
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="font-mono text-sm font-bold text-on-surface">
                {bidder.registration_number || <span className="text-outline text-xs italic">Pending submission</span>}
              </span>
              {bidder.registration_number && (
                <button
                  onClick={() => handleCopy(bidder.registration_number!, "cin")}
                  className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors"
                  title="Copy CIN"
                >
                  {copiedKey === "cin" ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              )}
            </div>
          </div>

          {/* Udyam MSME Card */}
          <div className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-mono text-on-surface-variant uppercase font-semibold flex items-center gap-1.5">
                <Award className="h-3.5 w-3.5 text-primary" />
                <span>MSME Udyam Registration</span>
              </span>
              {bidder.udyam_number ? (
                <Badge variant="success" size="sm">MSME Certified</Badge>
              ) : (
                <Badge variant="neutral" size="sm">Not Claimed</Badge>
              )}
            </div>

            <div className="flex items-center justify-between pt-1">
              <span className="font-mono text-sm font-bold text-on-surface">
                {bidder.udyam_number || <span className="text-outline text-xs italic">Non-MSME or Pending</span>}
              </span>
              {bidder.udyam_number && (
                <button
                  onClick={() => handleCopy(bidder.udyam_number!, "udyam")}
                  className="p-1.5 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors"
                  title="Copy Udyam Number"
                >
                  {copiedKey === "udyam" ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
