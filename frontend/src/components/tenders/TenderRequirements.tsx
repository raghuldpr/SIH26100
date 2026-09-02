import React, { useState, useEffect, useCallback } from "react";
import { analyzeTender, listTenderRequirements } from "../../api/tenders";
import { TenderRequirementResponse } from "../../types";
import { Badge, Button, Skeleton } from "../ui";
import { Cpu, Play, CheckCircle2, AlertCircle, Layers, BookOpen } from "lucide-react";

export interface TenderRequirementsProps {
  tenderId: string;
}

export const TenderRequirements: React.FC<TenderRequirementsProps> = ({ tenderId }) => {
  const [requirements, setRequirements] = useState<TenderRequirementResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const fetchRequirements = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listTenderRequirements(tenderId);
      setRequirements(data);
    } catch (err: any) {
      console.error("Failed to list tender requirements:", err);
    } finally {
      setIsLoading(false);
    }
  }, [tenderId]);

  useEffect(() => {
    fetchRequirements();
  }, [fetchRequirements]);

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true);
    setStatusMessage(null);

    try {
      const profile = await analyzeTender(tenderId, true);
      setRequirements(profile.requirements || profile.deterministic_requirements || []);
      setStatusMessage({
        text: `Tender Intelligence extracted ${profile.requirement_count} compliance clauses successfully (${profile.deterministic_count} deterministic).`,
        type: "success",
      });
      await fetchRequirements();
    } catch (err: any) {
      setStatusMessage({
        text: err?.message || "Analysis failed. Please verify tender document attachments exist.",
        type: "error",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getRequirementTypeBadge = (type: string) => {
    switch (type.toUpperCase()) {
      case "FINANCIAL":
        return <Badge variant="primary" size="sm">FINANCIAL</Badge>;
      case "EXPERIENCE":
      case "PAST_EXPERIENCE":
        return <Badge variant="success" size="sm">EXPERIENCE</Badge>;
      case "STATUTORY":
      case "LEGAL":
        return <Badge variant="neutral" size="sm">STATUTORY</Badge>;
      case "TECHNICAL":
        return <Badge variant="warning" size="sm">TECHNICAL</Badge>;
      default:
        return <Badge variant="neutral" size="sm">{type}</Badge>;
    }
  };

  const mandatoryCount = requirements.filter((r) => r.mandatory).length;

  return (
    <div className="space-y-6">
      {/* Header & Analysis Action */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
              <Cpu className="h-4 w-4 text-primary" />
              <span>Phase 11 Tender Intelligence &amp; Clause Extraction</span>
            </h3>
            <p className="text-xs text-on-surface-variant font-mono">
              Extracts eligibility parameters, financial criteria, and experience thresholds from attached NIT documents
            </p>
          </div>

          <Button
            variant="primary"
            size="sm"
            onClick={handleRunAnalysis}
            isLoading={isAnalyzing}
            leftIcon={<Play className="h-3.5 w-3.5" />}
          >
            Extract &amp; Analyze Clauses
          </Button>
        </div>

        {statusMessage && (
          <div
            className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
              statusMessage.type === "success"
                ? "bg-emerald-50 text-emerald-800 border border-emerald-200"
                : "bg-error-container text-error"
            }`}
          >
            {statusMessage.type === "success" ? (
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            ) : (
              <AlertCircle className="h-4 w-4 shrink-0 text-error" />
            )}
            <span className="font-medium">{statusMessage.text}</span>
          </div>
        )}

        {/* Quick Clause Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-0.5">
            <span className="text-[11px] text-on-surface-variant font-medium">Total Clauses</span>
            <div className="text-xl font-bold font-mono text-on-surface">{requirements.length}</div>
          </div>
          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-0.5">
            <span className="text-[11px] text-on-surface-variant font-medium">Mandatory Criteria</span>
            <div className="text-xl font-bold font-mono text-error">{mandatoryCount}</div>
          </div>
          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-0.5">
            <span className="text-[11px] text-on-surface-variant font-medium">Deterministic Rules</span>
            <div className="text-xl font-bold font-mono text-primary">{requirements.length}</div>
          </div>
          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-0.5">
            <span className="text-[11px] text-on-surface-variant font-medium">Extraction Engine</span>
            <div className="text-xs font-semibold text-emerald-700 font-mono mt-1">Rule Engine Active</div>
          </div>
        </div>
      </div>

      {/* Clause Requirements List */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant flex items-center gap-2">
          <Layers className="h-4 w-4 text-primary" />
          <span>Configured Compliance Requirements ({requirements.length})</span>
        </h4>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 space-y-2">
                <Skeleton className="h-5 w-1/4" />
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-3 w-1/2" />
              </div>
            ))}
          </div>
        ) : requirements.length === 0 ? (
          <div className="text-center py-10 bg-surface-container-lowest rounded-xl border border-outline-variant/30 p-6 space-y-3">
            <BookOpen className="h-8 w-8 text-outline mx-auto" />
            <div className="space-y-1">
              <h5 className="text-sm font-semibold text-on-surface">No clauses extracted yet</h5>
              <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
                Click &quot;Extract &amp; Analyze Clauses&quot; above to run the Phase 11 clause parser on uploaded tender documents.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {requirements.map((req) => (
              <div
                key={req.id}
                className="p-5 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-3 hover:border-primary/40 transition-colors"
              >
                {/* Clause Header */}
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-sm font-bold text-primary bg-primary/5 px-2.5 py-0.5 rounded border border-primary/20">
                      {req.rule}
                    </span>
                    {getRequirementTypeBadge(req.requirement_type)}
                    <Badge variant={req.mandatory ? "danger" : "neutral"} size="sm" dot>
                      {req.mandatory ? "MANDATORY" : "OPTIONAL"}
                    </Badge>
                  </div>

                  <div className="flex items-center gap-2 text-[11px] font-mono text-on-surface-variant">
                    {req.source_section && (
                      <span className="bg-surface-container px-2 py-0.5 rounded">
                        Section: {req.source_section}
                      </span>
                    )}
                    {req.source_page && (
                      <span className="bg-surface-container px-2 py-0.5 rounded">
                        Page {req.source_page}
                      </span>
                    )}
                    <Badge variant="success" size="sm">
                      {Math.round(req.confidence * 100)}% Confidence
                    </Badge>
                  </div>
                </div>

                {/* Description */}
                <p className="text-xs text-on-surface leading-relaxed">
                  {req.description}
                </p>

                {/* Source Excerpt if Available */}
                {req.source_text && (
                  <div className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/20 text-[11px] text-on-surface-variant font-mono italic">
                    &ldquo;{req.source_text}&rdquo;
                  </div>
                )}

                {/* Parameter Chips */}
                {req.parameters && Object.keys(req.parameters).length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {Object.entries(req.parameters).map(([key, val]) => (
                      <span
                        key={key}
                        className="inline-flex items-center gap-1 text-[11px] font-mono px-2 py-0.5 rounded bg-surface-container text-on-surface border border-outline-variant/40"
                      >
                        <span className="text-on-surface-variant font-medium">{key}:</span>
                        <span className="font-bold text-primary">{String(val)}</span>
                      </span>
                    ))}
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
