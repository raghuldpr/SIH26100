import React, { useState, useEffect, useCallback } from "react";
import { getVerificationAudit } from "../../api/verification";
import { VerificationAuditEventResponse } from "../../types";
import { Skeleton } from "../ui";
import { Clock, Copy, Check, Activity, CheckCircle2, XCircle, ArrowRightCircle } from "lucide-react";
import { formatDate } from "../../lib/utils";

export interface VerificationAuditProps {
  verificationId: string;
}

export const VerificationAudit: React.FC<VerificationAuditProps> = ({ verificationId }) => {
  const [events, setEvents] = useState<VerificationAuditEventResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  const fetchAudit = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getVerificationAudit(verificationId);
      setEvents(data);
    } catch (err: any) {
      console.error("Failed to load audit events:", err);
    } finally {
      setIsLoading(false);
    }
  }, [verificationId]);

  useEffect(() => {
    fetchAudit();
  }, [fetchAudit]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const getEventBadge = (type: string) => {
    const t = (type || "").toUpperCase();
    if (t.includes("COMPLETED")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-300">
          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
          COMPLETED
        </span>
      );
    }
    if (t.includes("FAILED")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-50 text-rose-800 border border-rose-300">
          <XCircle className="h-3 w-3 text-rose-600" />
          FAILED
        </span>
      );
    }
    if (t.includes("DISPATCHED") || t.includes("STARTED")) {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-primary/10 text-primary border border-primary/20">
          <ArrowRightCircle className="h-3 w-3 text-primary" />
          DISPATCHED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-surface-container text-on-surface-variant border border-outline-variant/30">
        {type}
      </span>
    );
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-outline-variant/20">
        <div>
          <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
            <Activity className="h-5 w-5 text-primary" />
            <span>Immutable Audit Lifecycle Trail</span>
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-surface-container text-on-surface-variant">
              {events.length} events
            </span>
          </h3>
          <p className="text-xs text-on-surface-variant mt-1">
            Tamper-evident cryptographically chained audit log tracking execution transitions and state changes
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="p-4 border border-outline-variant/20 rounded-xl space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-8 bg-surface-container-low/40 rounded-xl text-xs text-on-surface-variant border border-dashed border-outline-variant/30">
          No audit log events available for this execution.
        </div>
      ) : (
        <div className="relative pl-6 border-l-2 border-primary/25 space-y-6 pt-2">
          {events.map((evt) => (
            <div key={evt.id} className="relative group">
              {/* Bullet Node */}
              <div className="absolute -left-[31px] top-2 w-3.5 h-3.5 rounded-full bg-primary ring-4 ring-surface-container-lowest shadow-xs" />

              <div className="p-4 bg-surface-container-low/50 rounded-xl border border-outline-variant/25 space-y-2.5 hover:border-primary/30 transition-colors">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-sm font-bold text-on-surface">
                      {evt.event_type}
                    </span>
                    {getEventBadge(evt.event_type)}
                  </div>
                  <span className="text-xs text-on-surface-variant flex items-center gap-1.5 font-medium">
                    <Clock className="h-3.5 w-3.5 text-outline" />
                    <span>{formatDate(evt.created_at)}</span>
                  </span>
                </div>

                {evt.result_hash && (
                  <div className="flex items-center justify-between text-xs font-mono p-2.5 bg-surface-container/70 rounded-lg border border-outline-variant/20 gap-2">
                    <div className="truncate">
                      <span className="text-on-surface-variant font-medium mr-1">Result Hash:</span>
                      <span className="font-bold text-on-surface">{evt.result_hash}</span>
                    </div>
                    <button
                      onClick={() => handleCopy(evt.result_hash!)}
                      className="p-1 rounded text-on-surface-variant hover:text-primary transition-colors shrink-0"
                      title="Copy Hash"
                    >
                      {copiedHash === evt.result_hash ? (
                        <Check className="h-4 w-4 text-emerald-600" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                )}

                {evt.details && Object.keys(evt.details).length > 0 && (
                  <div className="text-xs font-mono text-on-surface-variant bg-surface-container/40 p-2.5 rounded-lg border border-outline-variant/15 break-all">
                    {JSON.stringify(evt.details, null, 2)}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
