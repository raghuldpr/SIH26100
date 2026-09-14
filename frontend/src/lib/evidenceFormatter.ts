/**
 * Frontend evidence formatting utilities for TenderTrust
 * Extracts clean, human-readable representations from primitive values or nested structured evidence objects.
 * Prevents raw JSON strings or "[object Object]" from leaking into the UI.
 */

/**
 * Format currency to standard Indian Rupee notation (Cr / Lakh / Thousands)
 */
export function formatFinancialValue(val: number): string {
  if (val >= 10000000) {
    const cr = val / 10000000;
    return `₹${cr.toFixed(2).replace(/\.00$/, "")} Cr`;
  }
  if (val >= 100000) {
    const lk = val / 100000;
    return `₹${lk.toFixed(2).replace(/\.00$/, "")} Lakh`;
  }
  if (val >= 1000) {
    return `₹${val.toLocaleString("en-IN")}`;
  }
  return `₹${val.toLocaleString("en-IN")}`;
}

/**
 * Extracts a human-readable display string from any value (primitive or object).
 * Never returns "[object Object]" or raw unparsed JSON.
 */
export function extractHumanReadableValue(val: any, fieldHint?: string): string {
  if (val === null || val === undefined) {
    return "—";
  }

  if (typeof val === "boolean") {
    return val ? "True" : "False";
  }

  if (typeof val === "number") {
    const hint = (fieldHint || "").toLowerCase();
    if (
      (hint.includes("turnover") ||
        hint.includes("financial") ||
        hint.includes("amount") ||
        hint.includes("value") ||
        hint.includes("inr") ||
        hint.includes("price") ||
        hint.includes("cost") ||
        hint.includes("revenue")) &&
      val >= 1000
    ) {
      return formatFinancialValue(val);
    }
    if (hint.includes("experience") || hint.includes("year")) {
      return `${val} ${val === 1 ? "year" : "years"}`;
    }
    return val.toLocaleString("en-US");
  }

  if (typeof val === "string") {
    const trimmed = val.trim();
    if (!trimmed) return "—";

    // Detect if string is a serialized JSON object/array
    if (
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"))
    ) {
      try {
        const parsed = JSON.parse(trimmed);
        if (typeof parsed === "object" && parsed !== null) {
          return extractHumanReadableValue(parsed, fieldHint);
        }
      } catch {
        // Not valid JSON, continue with normal string
      }
    }
    return trimmed;
  }

  if (Array.isArray(val)) {
    if (val.length === 0) return "—";
    // If array of primitives
    if (val.every((item) => typeof item !== "object" || item === null)) {
      return val.filter((item) => item !== null && item !== undefined).join(", ");
    }
    // If array of objects, map each item's human-readable value
    const extractedItems = val
      .map((item) => extractHumanReadableValue(item, fieldHint))
      .filter((s) => s && s !== "—" && s !== "Structured evidence available");

    if (extractedItems.length > 0) {
      return extractedItems.join(", ");
    }
    return `${val.length} evidence items recorded`;
  }

  if (typeof val === "object") {
    const hint = (fieldHint || "").toLowerCase();

    // 1. Specific field priority based on hint
    if (hint.includes("gst")) {
      const g =
        val.gstin ||
        val.gst ||
        val.gst_number ||
        val.gstin_number ||
        val.registration_number;
      if (g) return String(g).trim();
    }
    if (hint.includes("pan")) {
      const p = val.pan || val.pan_number;
      if (p) return String(p).trim();
    }
    if (hint.includes("udyam") || hint.includes("msme")) {
      const u =
        val.udyam_registration ||
        val.udyam_number ||
        val.udyam ||
        val.registration_number;
      if (u) return String(u).trim();
    }
    if (
      hint.includes("turnover") ||
      hint.includes("financial") ||
      hint.includes("revenue")
    ) {
      const t =
        val.average_turnover ??
        val.annual_turnover ??
        val.turnover ??
        val.average ??
        val.amount ??
        val.revenue ??
        val.detected_value ??
        val.normalized_value;
      if (t !== undefined && t !== null) {
        if (typeof t === "number") return formatFinancialValue(t);
        return String(t).trim();
      }
    }
    if (hint.includes("experience") || hint.includes("year")) {
      const exp =
        val.years_of_experience ??
        val.experience_years ??
        val.years ??
        val.completed_projects ??
        val.project_count;
      if (exp !== undefined && exp !== null) {
        if (typeof exp === "number") return `${exp} ${exp === 1 ? "year" : "years"}`;
        return String(exp).trim();
      }
    }

    // 2. Look for primary identifiers in the object directly
    if (val.gstin) return String(val.gstin).trim();
    if (val.pan) return String(val.pan).trim();
    if (val.udyam_registration) return String(val.udyam_registration).trim();
    if (val.udyam_number) return String(val.udyam_number).trim();

    // 3. Look for standard extracted / normalized value keys
    if (
      val.normalized_value !== undefined &&
      val.normalized_value !== null &&
      typeof val.normalized_value !== "object"
    ) {
      return extractHumanReadableValue(val.normalized_value, fieldHint);
    }
    if (
      val.detected_value !== undefined &&
      val.detected_value !== null &&
      typeof val.detected_value !== "object"
    ) {
      return extractHumanReadableValue(val.detected_value, fieldHint);
    }
    if (
      val.actual_value !== undefined &&
      val.actual_value !== null &&
      typeof val.actual_value !== "object"
    ) {
      return extractHumanReadableValue(val.actual_value, fieldHint);
    }
    if (
      val.bidder_value !== undefined &&
      val.bidder_value !== null &&
      typeof val.bidder_value !== "object"
    ) {
      return extractHumanReadableValue(val.bidder_value, fieldHint);
    }
    if (
      val.required_value !== undefined &&
      val.required_value !== null &&
      typeof val.required_value !== "object"
    ) {
      return extractHumanReadableValue(val.required_value, fieldHint);
    }
    if (
      val.expected_value !== undefined &&
      val.expected_value !== null &&
      typeof val.expected_value !== "object"
    ) {
      return extractHumanReadableValue(val.expected_value, fieldHint);
    }
    if (
      val.value !== undefined &&
      val.value !== null &&
      typeof val.value !== "object"
    ) {
      return extractHumanReadableValue(val.value, fieldHint);
    }

    // 4. Nested normalized_value or detected_value if they were objects
    if (val.normalized_value && typeof val.normalized_value === "object") {
      const nested = extractHumanReadableValue(val.normalized_value, fieldHint);
      if (nested && nested !== "Structured evidence available") return nested;
    }
    if (val.detected_value && typeof val.detected_value === "object") {
      const nested = extractHumanReadableValue(val.detected_value, fieldHint);
      if (nested && nested !== "Structured evidence available") return nested;
    }

    // 5. Common entity names or textual representations
    if (val.legal_name) return String(val.legal_name).trim();
    if (val.company_name) return String(val.company_name).trim();
    if (val.entity_name) return String(val.entity_name).trim();
    if (val.average_turnover !== undefined) return formatFinancialValue(Number(val.average_turnover) || 0);
    if (val.annual_turnover !== undefined) return formatFinancialValue(Number(val.annual_turnover) || 0);
    if (val.years_of_experience !== undefined) return `${val.years_of_experience} years`;
    if (val.result !== undefined && typeof val.result !== "object") return String(val.result).trim();
    if (val.status !== undefined && typeof val.status !== "object") return String(val.status).trim();

    // 6. Look for first non-metadata primitive property
    const metadataKeys = new Set([
      "source_document",
      "document",
      "file",
      "filename",
      "page",
      "page_number",
      "source_page",
      "confidence",
      "document_id",
      "source_text",
      "text",
      "document_hash",
      "document_type",
      "extraction_method",
      "tender_id",
      "bidder_id",
      "evidence_id",
      "id",
      "timestamp",
      "metadata",
      "created_at",
      "updated_at",
    ]);

    for (const [k, v] of Object.entries(val)) {
      if (!metadataKeys.has(k.toLowerCase()) && v !== null && v !== undefined && typeof v !== "object") {
        return String(v).trim();
      }
    }

    // 7. If only source text or document exists, display brief source indication
    if (val.source_document) {
      const pageSuffix = val.page || val.page_number ? ` (p. ${val.page || val.page_number})` : "";
      return `File: ${val.source_document}${pageSuffix}`;
    }
    if (val.source_text && typeof val.source_text === "string") {
      return val.source_text.slice(0, 60).trim();
    }

    return "Structured evidence available";
  }

  return String(val);
}

/**
 * Extracts provenance metadata from an evidence entry or object
 */
export interface ExtractedEvidenceProvenance {
  sourceDocument?: string;
  pageNumber?: number | string;
  confidence?: number;
  evidenceText?: string;
  evidenceId?: string;
  isComplexObject: boolean;
  rawObject?: Record<string, any>;
}

export function extractEvidenceProvenance(
  entry: any,
  nestedValue?: any
): ExtractedEvidenceProvenance {
  const obj =
    nestedValue && typeof nestedValue === "object"
      ? nestedValue
      : entry && typeof entry === "object"
      ? entry
      : null;

  const result: ExtractedEvidenceProvenance = {
    isComplexObject: Boolean(obj),
    rawObject: obj || undefined,
  };

  if (!obj) return result;

  // Source document
  result.sourceDocument =
    entry?.source_document ||
    entry?.document ||
    entry?.file ||
    obj?.source_document ||
    obj?.document ||
    obj?.file ||
    obj?.filename;

  // Page number
  const rawPage =
    entry?.page_number ??
    entry?.page ??
    entry?.source_page ??
    obj?.page_number ??
    obj?.page ??
    obj?.source_page;
  if (rawPage !== undefined && rawPage !== null && rawPage !== "") {
    result.pageNumber = rawPage;
  }

  // Confidence
  const rawConf = entry?.confidence ?? obj?.confidence;
  if (typeof rawConf === "number" && !isNaN(rawConf)) {
    result.confidence = rawConf;
  }

  // Evidence text
  result.evidenceText =
    entry?.evidence_text ||
    entry?.source_text ||
    obj?.evidence_text ||
    obj?.source_text;

  // Evidence ID
  result.evidenceId =
    entry?.evidence_id ||
    entry?.id ||
    obj?.evidence_id ||
    obj?.id;

  return result;
}

/**
 * Formats Agent Matrix evidence items into clean, human-readable badge chips.
 * Never outputs raw JSON or numerical indices with object dumps.
 */
export interface AgentEvidenceChip {
  id: string;
  label: string;
  value: string;
  rawDetails?: any;
}

export function formatAgentEvidenceChips(rawEvidence: any): AgentEvidenceChip[] {
  if (!rawEvidence) return [];

  const chips: AgentEvidenceChip[] = [];

  // If evidence is an Array of items
  if (Array.isArray(rawEvidence)) {
    rawEvidence.forEach((item, idx) => {
      if (!item) return;
      if (typeof item !== "object") {
        chips.push({
          id: `arr-${idx}`,
          label: `Evidence #${idx + 1}`,
          value: String(item),
        });
        return;
      }

      // It's an object item
      let chipLabel = item.field || item.document_type || item.requirement || `Evidence #${idx + 1}`;
      if (item.gstin) chipLabel = "GSTIN";
      else if (item.pan) chipLabel = "PAN";
      else if (item.udyam_registration || item.udyam_number) chipLabel = "Udyam";
      else if (item.average_turnover !== undefined || item.annual_turnover !== undefined) chipLabel = "Turnover";
      else if (item.years_of_experience !== undefined) chipLabel = "Experience";

      let chipValue = extractHumanReadableValue(item, chipLabel);
      if (chipValue === "Structured evidence available" && item.source_document) {
        const page = item.page || item.page_number;
        chipValue = `${item.source_document}${page ? ` (p. ${page})` : ""}`;
      }

      chips.push({
        id: `item-${idx}`,
        label: chipLabel,
        value: chipValue,
        rawDetails: item,
      });
    });
    return chips;
  }

  // If evidence is a Record<string, any>
  if (typeof rawEvidence === "object") {
    const ignoredKeys = new Set(["extracted_text", "raw_data", "metadata", "document_hash"]);

    for (const [key, val] of Object.entries(rawEvidence)) {
      if (ignoredKeys.has(key)) continue;

      const formattedLabel = key
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());

      const formattedValue = extractHumanReadableValue(val, key);

      chips.push({
        id: key,
        label: formattedLabel,
        value: formattedValue,
        rawDetails: typeof val === "object" ? val : undefined,
      });
    }
  }

  return chips;
}
