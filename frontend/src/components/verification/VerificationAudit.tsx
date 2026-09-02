import React, { useState, useEffect, useCallback } from "react";
import { getVerificationAudit } from "../../api/verification";
import { VerificationAuditEventResponse } from "../../types";
import { Badge, Skeleton } from "../ui";
import { Clock, Copy, Check, Activity } from "lucide-react";
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
    if (type.includes("COMPLETED")) {
      return <Badge variant="success" size="sm">COMPLETED</Badge>;
    }
    if (type.includes("FAILED")) {
      return <Badge variant="danger" size="sm">FAILED</Badge>;
    }
    if (type.includes("DISPATCHED") || type.includes("STARTED")) {
      return <Badge variant="primary" size="sm">DISPATCHED</Badge>;
    }
    return <Badge variant="neutral" size="sm">{type}</Badge>;
  };

  return (
    <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
      <div>
        <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          <span>Immutable Audit Lifecycle Trail ({events.length})</span>
        </h3>
        <p className="text-xs text-on-surface-variant font-mono mt-0.5">
          Cryptographically hashed chronological timeline of execution state transitions
        </p>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="p-3 border border-outline-variant/20 rounded-lg space-y-2">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="text-center py-6 bg-surface-container-low/40 rounded-lg text-xs text-on-surface-variant">
          No audit log events available for this execution.
        </div>
      ) : (
        <div className="relative pl-6 border-l-2 border-primary/20 space-y-6 pt-2">
          {events.map((evt) => (
            <div key={evt.id} className="relative group">
              {/* Bullet */}
              <div className="absolute -left-[31px] top-1.5 w-3.5 h-3.5 rounded-full bg-primary border-2 border-surface-container-lowest shadow-sm" />

              <div className="p-4 bg-surface-container-low/60 rounded-xl border border-outline-variant/25 space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-on-surface">
                      {evt.event_type}
                    </span>
                    {getEventBadge(evt.event_type)}
                  </div>
                  <span className="text-[11px] font-mono text-on-surface-variant flex items-center gap-1">
                    <Clock className="h-3 w-3 text-outline" />
                    <span>{formatDate(evt.created_at)}</span>
                  </span>
                </div>

                {evt.result_hash && (
                  <div className="flex items-center justify-between text-[11px] font-mono p-2 bg-surface-container rounded-lg">
                    <span className="truncate pr-2 text-on-surface-variant">
                      Result Hash: <span className="font-bold text-on-surface">{evt.result_hash}</span>
                    </span>
                    <button
                      onClick={() => handleCopy(evt.result_hash!)}
                      className="text-on-surface-variant hover:text-primary transition-colors shrink-0"
                      title="Copy Hash"
                    >
                      {copiedHash === evt.result_hash ? (
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                )}

                {evt.details && Object.keys(evt.details).length > 0 && (
                  <div className="text-[11px] font-mono text-on-surface-variant bg-surface-container-low p-2 rounded">
                    {JSON.stringify(evt.details)}
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
