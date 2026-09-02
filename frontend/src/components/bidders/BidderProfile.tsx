import React from "react";
import { BidderResponse } from "../../types";
import { Badge } from "../ui";
import {
  Building2,
  Mail,
  Phone,
  MapPin,
  User,
  Calendar,
  Clock,
  ShieldCheck,
} from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface BidderProfileProps {
  bidder: BidderResponse;
}

export const BidderProfile: React.FC<BidderProfileProps> = ({ bidder }) => {
  const getStatusBadge = (status: string) => {
    switch (status) {
      case "ACTIVE":
        return <Badge variant="success" size="sm" dot>ACTIVE / ELIGIBLE</Badge>;
      case "INACTIVE":
        return <Badge variant="neutral" size="sm" dot>INACTIVE</Badge>;
      case "SUSPENDED":
        return <Badge variant="danger" size="sm" dot>SUSPENDED</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{status}</Badge>;
    }
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Primary Organization Info */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <Building2 className="h-4 w-4 text-primary" />
          <span>Corporate Entity Profile</span>
        </h3>

        <div className="space-y-3 text-xs">
          <div>
            <span className="text-on-surface-variant block font-mono text-[11px]">Corporate Name</span>
            <span className="font-semibold text-sm text-on-surface">{bidder.company_name}</span>
          </div>

          <div>
            <span className="text-on-surface-variant block font-mono text-[11px]">Operational Status</span>
            <div className="pt-1">{getStatusBadge(bidder.status)}</div>
          </div>

          {bidder.registration_number && (
            <div>
              <span className="text-on-surface-variant block font-mono text-[11px]">Corporate Registration / CIN</span>
              <span className="font-mono font-semibold text-primary">{bidder.registration_number}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-outline-variant/20">
            <div>
              <span className="text-on-surface-variant block font-mono text-[11px] flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5 text-outline" />
                <span>Registered At</span>
              </span>
              <span className="font-mono text-[11px] text-on-surface">{formatDate(bidder.created_at)}</span>
            </div>

            <div>
              <span className="text-on-surface-variant block font-mono text-[11px] flex items-center gap-1">
                <Clock className="h-3.5 w-3.5 text-outline" />
                <span>Last Updated</span>
              </span>
              <span className="font-mono text-[11px] text-on-surface">{formatDate(bidder.updated_at)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Primary Contact & Address */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-primary" />
          <span>Contact &amp; Physical Address</span>
        </h3>

        <div className="space-y-3 text-xs">
          <div>
            <span className="text-on-surface-variant block font-mono text-[11px] flex items-center gap-1.5">
              <User className="h-3.5 w-3.5 text-outline" />
              <span>Primary Representative</span>
            </span>
            <span className="font-medium text-on-surface">
              {bidder.contact_person || <span className="text-outline italic">Not specified</span>}
            </span>
          </div>

          <div>
            <span className="text-on-surface-variant block font-mono text-[11px] flex items-center gap-1.5">
              <Mail className="h-3.5 w-3.5 text-outline" />
              <span>Official Email</span>
            </span>
            <span className="font-mono text-on-surface">
              {bidder.email ? (
                <a href={`mailto:${bidder.email}`} className="text-primary hover:underline">
                  {bidder.email}
                </a>
              ) : (
                <span className="text-outline italic">Not specified</span>
              )}
            </span>
          </div>

          <div>
            <span className="text-on-surface-variant block font-mono text-[11px] flex items-center gap-1.5">
              <Phone className="h-3.5 w-3.5 text-outline" />
              <span>Telephone / Mobile</span>
            </span>
            <span className="font-mono text-on-surface">
              {bidder.phone || <span className="text-outline italic">Not specified</span>}
            </span>
          </div>

          <div className="pt-2 border-t border-outline-variant/20">
            <span className="text-on-surface-variant block font-mono text-[11px] flex items-center gap-1.5">
              <MapPin className="h-3.5 w-3.5 text-outline" />
              <span>Registered Office Address</span>
            </span>
            <p className="text-on-surface pt-1 leading-relaxed">
              {bidder.address || <span className="text-outline italic">No address provided.</span>}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
