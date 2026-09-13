import React, { useState, useEffect, useCallback } from "react";
import { analyzeTender, listTenderRequirements, getTenderIntelligenceProfile } from "../../api/tenders";
import { TenderRequirementResponse } from "../../types";
import { Badge, Button, Skeleton } from "../ui";
import { Cpu, Play, CheckCircle2, AlertCircle, Layers, BookOpen, AlertTriangle, ShieldAlert, FileText } from "lucide-react";

export interface TenderRequirementsProps {
  tenderId: string;
}

export const TenderRequirements: React.FC<TenderRequirementsProps> = ({ tenderId }) => {
  const [requirements, setRequirements] = useState<TenderRequirementResponse[]>([]);
  const [unresolvedRequirements, setUnresolvedRequirements] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  const fetchRequirements = useCallback(async () => {
    setIsLoading(true);
    try {
      // First try to fetch the rich Tender Intelligence Profile
      try {
        const profile = await getTenderIntelligenceProfile(tenderId);
        if (profile) {
          const reqs = profile.requirements && profile.requirements.length > 0
            ? profile.requirements
            : profile.deterministic_requirements || [];
          setRequirements(reqs);
          setUnresolvedRequirements(profile.unresolved_requirements || []);
          setIsLoading(false);
          return;
        }
      } catch {
        // Fallback to basic requirements endpoint
      }

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
      const reqs = profile.requirements && profile.requirements.length > 0
        ? profile.requirements
        : profile.deterministic_requirements || [];
      setRequirements(reqs);
      setUnresolvedRequirements(profile.unresolved_requirements || []);

      setStatusMessage({
        text: `Tender Intelligence extracted ${profile.requirement_count} criteria (${profile.deterministic_count} deterministic, ${profile.unresolved_count} unresolved manual review items).`,
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
    switch (type?.toUpperCase()) {
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
        return <Badge variant="neutral" size="sm">{type || "GENERAL"}</Badge>;
    }
  };

  const getResolutionBadge = (resolution?: string, isUnresolved?: boolean) => {
    if (isUnresolved || resolution === "UNRESOLVED") {
      return (
        <Badge variant="warning" size="sm" dot>
          MANUAL REVIEW REQUIRED
        </Badge>
      );
    }
    if (resolution === "AI_GATEWAY" || resolution === "AI_RESOLVED") {
      return (
        <Badge variant="primary" size="sm">
          AI-ASSISTED
        </Badge>
      );
    }
    return (
      <Badge variant="success" size="sm">
        DETERMINISTIC
      </Badge>
    );
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
              <span>Tender Intelligence &amp; Clause Extraction</span>
            </h3>
            <p className="text-xs text-on-surface-variant font-mono">
              Extracts eligibility parameters, financial criteria, and experience thresholds with deterministic + AI escalation
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
            <span className="text-[11px] text-on-surface-variant font-medium">Unresolved Criteria</span>
            <div className="text-xl font-bold font-mono text-amber-600">
              {unresolvedRequirements.length}
            </div>
          </div>
          <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant/20 space-y-0.5">
            <span className="text-[11px] text-on-surface-variant font-medium">Resolution Engine</span>
            <div className="text-xs font-semibold text-emerald-700 font-mono mt-1">Groq qwen3.8-27b</div>
          </div>
        </div>
      </div>

      {/* Unresolved / Ambiguous Clauses Notice */}
      {unresolvedRequirements.length > 0 && (
        <div className="p-5 bg-amber-50 rounded-xl border border-amber-200 shadow-subtle space-y-3">
          <div className="flex items-center gap-2 text-amber-900 font-bold text-xs uppercase tracking-wider font-mono">
            <ShieldAlert className="h-4 w-4 text-amber-700 shrink-0" />
            <span>Unresolved Criteria Requiring Human Officer Review ({unresolvedRequirements.length})</span>
          </div>
          <p className="text-xs text-amber-800">
            The following clauses contain subjective or ambiguous wording. They have NOT been silently converted to deterministic criteria and require manual review:
          </p>
          <div className="space-y-2">
            {unresolvedRequirements.map((unres, i) => (
              <div key={i} className="p-3 bg-white rounded-lg border border-amber-200 text-xs space-y-1">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className="font-mono font-bold text-amber-900">{unres.rule || "AMBIGUOUS_CLAUSE"}</span>
                  <Badge variant="warning" size="sm" dot>
                    Manual Review Required
                  </Badge>
                </div>
                {unres.description && <p className="text-stone-700">{unres.description}</p>}
                {unres.source_text && (
                  <p className="text-[11px] font-mono italic text-stone-600">&ldquo;{unres.source_text}&rdquo;</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

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
                Click &quot;Extract &amp; Analyze Clauses&quot; above to run the clause parser on uploaded tender documents.
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {requirements.map((req) => {
              const fieldName = req.field || req.parameters?.field || req.rule?.toLowerCase();
              const operator = req.operator || req.parameters?.operator || ">=";
              const requiredValue = req.required_value !== undefined
                ? String(req.required_value)
                : req.parameters?.required_value !== undefined
                ? String(req.parameters.required_value)
                : req.parameters?.min_turnover
                ? `${req.parameters.min_turnover} INR`
                : req.parameters?.min_years
                ? `${req.parameters.min_years} Years`
                : "Specified in Clause";
              const isUnresolved = req.status === "UNRESOLVED" || req.confidence < 0.6;

              return (
                <div
                  key={req.id}
                  className={`p-5 bg-surface-container-lowest rounded-xl border shadow-subtle space-y-3 transition-colors ${
                    isUnresolved ? "border-amber-300 hover:border-amber-400" : "border-outline-variant/30 hover:border-primary/40"
                  }`}
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
                      {getResolutionBadge(req.resolution_method, isUnresolved)}
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
                      <Badge variant={isUnresolved ? "warning" : "success"} size="sm">
                        {Math.round((req.confidence ?? 1.0) * 100)}% Confidence
                      </Badge>
                    </div>
                  </div>

                  {/* Manual Review Alert if Unresolved */}
                  {isUnresolved && (
                    <div className="p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-900 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
                      <span className="font-semibold">
                        Manual Review Required: This requirement requires human verification.
                      </span>
                    </div>
                  )}

                  {/* Structured Rule Parameters Table / Badges */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 rounded-lg bg-surface-container-low border border-outline-variant/20 text-xs font-mono">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Target Field</span>
                      <span className="font-semibold text-on-surface truncate block">{fieldName}</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Operator</span>
                      <span className="font-semibold text-primary">{operator}</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Required Value</span>
                      <span className="font-semibold text-emerald-700">{requiredValue}</span>
                    </div>
                    <div>
                      <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Resolution</span>
                      <span className="font-semibold text-on-surface">{req.resolution_method || (isUnresolved ? "AI Escalate" : "Deterministic")}</span>
                    </div>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-on-surface leading-relaxed">
                    {req.description}
                  </p>

                  {/* Source Excerpt if Available */}
                  {req.source_text && (
                    <div className="p-2.5 rounded-lg bg-surface-container-low border border-outline-variant/20 text-[11px] text-on-surface-variant font-mono italic flex items-start gap-2">
                      <FileText className="h-3.5 w-3.5 text-outline shrink-0 mt-0.5" />
                      <span>&ldquo;{req.source_text}&rdquo;</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
