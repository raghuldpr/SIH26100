## Workflow: 🔹 SIH — Document Forensics Agent — Prototype (`document_forensics_agent.json`)
- **ID**: `SihForensicsAgentProto01`
- **Total Nodes**: 13 (Functional: 11, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Forensics Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Document Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Forensics Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Document Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/document-forensics` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Document Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Forensics Test Webhook']
   - **Out**: ['🔍 Document Integrity Inspection']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  // Default mock documents for registered prototype bidders const MOCK_BIDDER_DOCS = {   "ABC Technologies Pvt Ltd": [    ...`
4. **🔍 Document Integrity Inspection** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Document Input Validation']
   - **Out**: ['📄 PDF & Metadata Inspection']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  const ALLOWED_MIMES = new Set([   'application/pdf',   'image/jpeg',   'image/jpg',   'image/png' ]);  return items.map(i...`
5. **📄 PDF & Metadata Inspection** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Document Integrity Inspection']
   - **Out**: ['🔤 OCR & Text Integrity Inspection']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const docs = d...`
6. **🔤 OCR & Text Integrity Inspection** (`n8n-nodes-base.code`)
   - **In**: ['📄 PDF & Metadata Inspection']
   - **Out**: ['🔗 Duplicate & Hash Analysis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const docs = d...`
7. **🔗 Duplicate & Hash Analysis** (`n8n-nodes-base.code`)
   - **In**: ['🔤 OCR & Text Integrity Inspection']
   - **Out**: ['⚖️ Forensics Risk & Status Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const docs = d...`
8. **⚖️ Forensics Risk & Status Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['🔗 Duplicate & Hash Analysis']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      let status = "VERIFIED";   let confidence = 0.98;   let riskLev...`
9. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['⚖️ Forensics Risk & Status Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
10. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
11. **🛑 Forensics Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "DOCUMENT_FORENSICS_AGENT",     status: "ERROR",     confidence: 0.0,    ...`
12. **Note - Card 1 Document Forensics** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 🔍 DOCUMENT FORENSICS AGENT Deterministic forensic examination of tender bid documents. Va...
13. **Note - Card 2 Forensics Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC FORENSIC RULES Multi-layer inspection checks: • Format & MIME conformanc...

---

## Workflow: 🔹 SIH — Entity Resolution Agent — Prototype (`entity_resolution_agent.json`)
- **ID**: `SihEntityResolutionAgentProto01`
- **Total Nodes**: 13 (Functional: 11, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Entity Resolution Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Entity Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Entity Resolution Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Entity Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/entity-resolution` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Entity Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Entity Resolution Test Webhook']
   - **Out**: ['🔤 Entity Name Normalization']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  // Default mock identity evidence for prototype bidders const MOCK_IDENTITIES = {   "ABC Technologies Pvt Ltd": {     gst...`
4. **🔤 Entity Name Normalization** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Entity Input Validation']
   - **Out**: ['⚖️ Identity Cross-Check Engine']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function normalizeLegalName(raw) {   if (!raw || typeof raw !== 'string') return '';      let s = raw.toUpperCase().trim(...`
5. **⚖️ Identity Cross-Check Engine** (`n8n-nodes-base.code`)
   - **In**: ['🔤 Entity Name Normalization']
   - **Out**: ['🆔 Identifier Consistency Engine']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const canonica...`
6. **🆔 Identifier Consistency Engine** (`n8n-nodes-base.code`)
   - **In**: ['⚖️ Identity Cross-Check Engine']
   - **Out**: ['⚠️ Duplicate & Conflict Detection']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/; const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z...`
7. **⚠️ Duplicate & Conflict Detection** (`n8n-nodes-base.code`)
   - **In**: ['🆔 Identifier Consistency Engine']
   - **Out**: ['📊 Entity Resolution Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const allConfl...`
8. **📊 Entity Resolution Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['⚠️ Duplicate & Conflict Detection']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      let status = "VERIFIED";   let confidence = 0.98;   let riskLev...`
9. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['📊 Entity Resolution Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
10. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
11. **🛑 Entity Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "ENTITY_RESOLUTION_AGENT",     status: "ERROR",     confidence: 0.0,     ...`
12. **Note - Card 1 Entity Resolution** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 🔗 ENTITY RESOLUTION AGENT Deterministic cross-verification of bidder identities. Reconcil...
13. **Note - Card 2 Identity Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC IDENTITY RULES Deterministic identity consistency rules: • Legal suffix ...

---

## Workflow: 🔹 SIH — Experience & Eligibility Agent — Prototype (`experience_eligibility_agent.json`)
- **ID**: `SihExperienceAgentProto01`
- **Total Nodes**: 10 (Functional: 8, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Experience Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Experience Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Experience Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Experience Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/experience-verification` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Experience Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Experience Test Webhook']
   - **Out**: ['⚙️ Experience Rule Evaluation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function isNumeric(val) {   if (typeof val === 'number') return !isNaN(val) && isFinite(val);   if (typeof val !== 'strin...`
4. **⚙️ Experience Rule Evaluation** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Experience Input Validation']
   - **Out**: ['⚖️ Experience Risk & Status Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) {     return { json: { ...data, evaluation...`
5. **⚖️ Experience Risk & Status Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ Experience Rule Evaluation']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   const reqs = data.experience_requirements || {};   const evalRes =...`
6. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['⚖️ Experience Risk & Status Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
7. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
8. **🛑 Experience Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "EXPERIENCE_AGENT",     status: "ERROR",     confidence: 0.0,     evidenc...`
9. **Note - Card 1 Experience Agent** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 🏗 EXPERIENCE & ELIGIBILITY AGENT Deterministic verification of past project performance. ...
10. **Note - Card 2 Eligibility Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC ELIGIBILITY RULES Strict mathematical verification: • Minimum similar wo...

---

## Workflow: 🔹 SIH — Final Compliance Agent — Prototype (`final_compliance_agent.json`)
- **ID**: `SihFinalComplianceAgentProto01`
- **Total Nodes**: 13 (Functional: 11, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Final Compliance Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Final Compliance Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Final Compliance Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Final Compliance Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/final-compliance` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Final Compliance Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Final Compliance Test Webhook']
   - **Out**: ['📋 Mandatory Agent Coverage Check']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  const DEFAULT_MANDATORY_AGENTS = [   "GST_AGENT",   "PAN_AGENT",   "UDYAM_AGENT",   "FINANCIAL_AGENT",   "DOCUMENT_FORENS...`
4. **📋 Mandatory Agent Coverage Check** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Final Compliance Input Validation']
   - **Out**: ['⚖️ Agent Status Evaluation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const results ...`
5. **⚖️ Agent Status Evaluation** (`n8n-nodes-base.code`)
   - **In**: ['📋 Mandatory Agent Coverage Check']
   - **Out**: ['⚙️ Compliance Rule Engine']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const agents =...`
6. **⚙️ Compliance Rule Engine** (`n8n-nodes-base.code`)
   - **In**: ['⚖️ Agent Status Evaluation']
   - **Out**: ['📁 Evidence & Failure Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) {     return {       json: {         ...da...`
7. **📁 Evidence & Failure Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ Compliance Rule Engine']
   - **Out**: ['🏆 Final Decision Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      const agents = data.evaluated_agents || [];   const mandatory =...`
8. **🏆 Final Decision Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['📁 Evidence & Failure Synthesis']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      const mandatory = data.compliance_policy?.mandatory_agents || [...`
9. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['🏆 Final Decision Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
10. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
11. **🛑 Final Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "FINAL_COMPLIANCE_AGENT",     status: "ERROR",     confidence: 0.0,     e...`
12. **Note - Card 1 Final Compliance** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 🏆 FINAL COMPLIANCE AGENT Deterministic compliance adjudication layer. Evaluates aggregate...
13. **Note - Card 2 Decision Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC DECISION RULES Strict rule hierarchy: 1. Input malformation / invalid st...

---

## Workflow: 🔹 SIH — Financial Verification Agent — Prototype (`financial_verification_agent.json`)
- **ID**: `SihFinancialAgentProto01`
- **Total Nodes**: 11 (Functional: 9, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Financial Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Financial Input & Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Financial Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Financial Input & Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/financial-verification` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Financial Input & Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Financial Test Webhook']
   - **Out**: ['🏛 Mock Financial Registry']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function isNumeric(val) {   if (typeof val === 'number') return !isNaN(val) && isFinite(val);   if (typeof val !== 'strin...`
4. **🏛 Mock Financial Registry** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Financial Input & Validation']
   - **Out**: ['⚙️ Deterministic Financial Calculations']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  // Mock financial filings registry database const MOCK_FINANCIAL_REGISTRY = {   "ABC Technologies Pvt Ltd": {     source:...`
5. **⚙️ Deterministic Financial Calculations** (`n8n-nodes-base.code`)
   - **In**: ['🏛 Mock Financial Registry']
   - **Out**: ['⚖️ Financial Risk & Status Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      if (!data.valid_schema) {     return {       json: {         .....`
6. **⚖️ Financial Risk & Status Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ Deterministic Financial Calculations']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      let status = "VERIFIED";   let confidence = 0.99;   let riskLev...`
7. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['⚖️ Financial Risk & Status Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
8. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
9. **🛑 Financial Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "FINANCIAL_AGENT",     status: "ERROR",     confidence: 0.0,     evidence...`
10. **Note - Card 1 Financial Agent** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 💰 FINANCIAL VERIFICATION AGENT Deterministic evaluation of financial compliance criteria....
11. **Note - Card 2 Deterministic Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC ALGORITHMS Strict mathematical calculations: • Multi-year average turnov...

---

## Workflow: 🔹 SIH — GST Verification Agent — Prototype (`gst_verification_agent.json`)
- **ID**: `SihGstAgentProto01`
- **Total Nodes**: 16 (Functional: 12, StickyNotes: 4)
- **Triggers**: ['Execute Workflow Trigger', '📥 GST Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: ['🤖 GST AI Agent (@n8n/n8n-nodes-langchain.agent)', '⚡ Groq Chat Model (@n8n/n8n-nodes-langchain.lmChatGroq)', '📋 Structured Output Parser (@n8n/n8n-nodes-langchain.outputParserStructured)']
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 GST Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/gst-verification` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 GST Test Webhook']
   - **Out**: ['🤖 GST AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json.body || item.json;   const gstin = (data.gstin || "27AABCU9603R1ZM").t...`
4. **🤖 GST AI Agent** (`@n8n/n8n-nodes-langchain.agent`)
   - **In**: ['🔍 Input Validation', '⚡ Groq Chat Model', '📋 Structured Output Parser']
   - **Out**: ['🏛 Mock GST Registry']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
5. **⚡ Groq Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGroq`)
   - **In**: []
   - **Out**: ['🤖 GST AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Credentials**: {'groqApi': {'id': 'groq_api_credential', 'name': 'Groq Account (Manual Config Required)'}}
6. **📋 Structured Output Parser** (`@n8n/n8n-nodes-langchain.outputParserStructured`)
   - **In**: []
   - **Out**: ['🤖 GST AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
7. **🏛 Mock GST Registry** (`n8n-nodes-base.code`)
   - **In**: ['🤖 GST AI Agent']
   - **Out**: ['⚙️ Deterministic GST Format Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); const MOCK_GST_REGISTRY = {   "27AABCU9603R1ZM": {     legal_name: "ABC Technologies Pvt Ltd",     trade_name: "ABC Tech",...`
8. **⚙️ Deterministic GST Format Validation** (`n8n-nodes-base.code`)
   - **In**: ['🏛 Mock GST Registry']
   - **Out**: ['📊 Confidence & Risk Calculation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); const GSTIN_REGEX = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;  return items.map(item => {   const data ...`
9. **📊 Confidence & Risk Calculation** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ Deterministic GST Format Validation']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const bidderName = (data.bidder_name || "").toUpperCase().trim();  ...`
10. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['📊 Confidence & Risk Calculation', '🛑 GST Error Fallback']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
11. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
12. **🛑 GST Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "GST_AGENT",     status: "REVIEW",     confidence: 0.0,     evidence: {  ...`
13. **Note - Input & Trigger** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟦 SECTION 1: TRIGGER & INPUT Accepts verification requests via: 1. Execute Workflow (from Master ...
14. **Note - AI Analysis** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟪 SECTION 2: AI AGENT ANALYSIS Specialized GST AI Agent powered by Groq Llama-3.3-70b-versatile. ...
15. **Note - Registry & Deterministic** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟧 SECTION 3: MOCK REGISTRY & DETERMINISTIC RULES Compares against mock GSTN records. Validates ex...
16. **Note - Result & Reliability** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟩 SECTION 4: CANONICAL STANDARDIZED RESULT Returns canonical schema: `{ agent, status, confidence...

---

## Workflow: 🚀 SIH — MASTER ORCHESTRATOR — Prototype (`master_orchestrator_prototype.json`)
- **ID**: `SihMasterOrchProto01`
- **Total Nodes**: 35 (Functional: 25, StickyNotes: 10)
- **Triggers**: ['📥 BID VERIFICATION REQUEST', '📤 RETURN VERIFICATION RESULT']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: ["🧠 Tender Intelligence Agent -> targetId: {'__rl': True, 'value': 'SihTenderIntelligenceAgentProto01', 'mode': 'id'}", "🧾 GST Verification Agent -> targetId: {'__rl': True, 'value': 'SihGstAgentProto01', 'mode': 'id'}", "🪪 PAN Verification Agent -> targetId: {'__rl': True, 'value': 'SihPanAgentProto01', 'mode': 'id'}", "🏭 Udyam Verification Agent -> targetId: {'__rl': True, 'value': 'SihUdyamAgentProto01', 'mode': 'id'}", "💰 Financial Verification Agent -> targetId: {'__rl': True, 'value': 'SihFinancialAgentProto01', 'mode': 'id'}", "🏗 Experience & Eligibility Agent -> targetId: {'__rl': True, 'value': 'SihExperienceAgentProto01', 'mode': 'id'}", "🔍 Document Forensics Agent -> targetId: {'__rl': True, 'value': 'SihForensicsAgentProto01', 'mode': 'id'}", "🔗 Entity Resolution Agent -> targetId: {'__rl': True, 'value': 'SihEntityResolutionAgentProto01', 'mode': 'id'}", "⚠️ Risk Intelligence Agent -> targetId: {'__rl': True, 'value': 'SihRiskIntelligenceAgentProto01', 'mode': 'id'}", "🏆 Final Compliance Agent -> targetId: {'__rl': True, 'value': 'SihFinalComplianceAgentProto01', 'mode': 'id'}"]

### Node Inventory:
1. **📥 BID VERIFICATION REQUEST** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Validate Verification Request']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/bid-verification` | Method: `POST` | ResponseMode: `responseNode`
2. **🔍 Validate Verification Request** (`n8n-nodes-base.code`)
   - **In**: ['📥 BID VERIFICATION REQUEST']
   - **Out**: ['✅ Request Valid?']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json.body || item.json;   const errors = [];   if (!data.request_id) errors...`
3. **✅ Request Valid?** (`n8n-nodes-base.if`)
   - **In**: ['🔍 Validate Verification Request']
   - **Out**: ['🧠 Agent Selection Engine', '🛑 Invalid Request Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
4. **🛑 Invalid Request Response** (`n8n-nodes-base.code`)
   - **In**: ['✅ Request Valid?']
   - **Out**: ['📤 RETURN VERIFICATION RESULT']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   return {     json: {       request_id: data.request_id || "UNKNOWN"...`
5. **🧠 Agent Selection Engine** (`n8n-nodes-base.code`)
   - **In**: ['✅ Request Valid?']
   - **Out**: ['🧭 Verification Group Router']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.flatMap(item => {   const data = item.json;   const agents = Array.isArray(data.required_agents) ? data.requi...`
6. **🧭 Verification Group Router** (`n8n-nodes-base.switch`)
   - **In**: ['🧠 Agent Selection Engine']
   - **Out**: ['🧠 Tender Intelligence Agent', '🏛 Statutory Verification Agent', '💰 Financial Verification Agent', '🏗 Experience & Eligibility Agent', '🔍 Document Forensics Agent', '🔗 Entity Resolution Agent', '⚠️ Risk Intelligence Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
7. **🧠 Tender Intelligence Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
8. **🏛 Statutory Verification Agent** (`n8n-nodes-base.code`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['🧾 GST Verification Agent', '🪪 PAN Verification Agent', '🏭 Udyam Verification Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   return {     json: {       ...data,       statutory_group: "STATUTO...`
9. **🧾 GST Verification Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🏛 Statutory Verification Agent']
   - **Out**: ['🔗 Merge Statutory Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
10. **🪪 PAN Verification Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🏛 Statutory Verification Agent']
   - **Out**: ['🔗 Merge Statutory Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
11. **🏭 Udyam Verification Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🏛 Statutory Verification Agent']
   - **Out**: ['🔗 Merge Statutory Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
12. **🔗 Merge Statutory Results** (`n8n-nodes-base.merge`)
   - **In**: ['🧾 GST Verification Agent', '🪪 PAN Verification Agent', '🏭 Udyam Verification Agent']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
13. **💰 Financial Verification Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
14. **🏗 Experience & Eligibility Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
15. **🔍 Document Forensics Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
16. **🔗 Entity Resolution Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
17. **⚠️ Risk Intelligence Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['🧭 Verification Group Router']
   - **Out**: ['📦 Collect Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
18. **📦 Collect Agent Results** (`n8n-nodes-base.code`)
   - **In**: ['🧠 Tender Intelligence Agent', '🔗 Merge Statutory Results', '💰 Financial Verification Agent', '🏗 Experience & Eligibility Agent', '🔍 Document Forensics Agent', '🔗 Entity Resolution Agent', '⚠️ Risk Intelligence Agent']
   - **Out**: ['🏆 Final Compliance Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `let initialReq = {}; let selectedGroups = []; try {   const selectionData = $('🧠 Agent Selection Engine').first().json;   selectedGroups = selectionDa...`
19. **🏆 Final Compliance Agent** (`n8n-nodes-base.executeWorkflow`)
   - **In**: ['📦 Collect Agent Results']
   - **Out**: ['📋 Normalize Agent Results']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
20. **📋 Normalize Agent Results** (`n8n-nodes-base.code`)
   - **In**: ['🏆 Final Compliance Agent']
   - **Out**: ['⚠️ Prototype Risk Aggregator']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); const rawResults = [];  try {   const collectData = $('📦 Collect Agent Results').first().json;   if (collectData && Array....`
21. **⚠️ Prototype Risk Aggregator** (`n8n-nodes-base.code`)
   - **In**: ['📋 Normalize Agent Results']
   - **Out**: ['🏆 Prototype Compliance Decision']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const results = data.normalized_results || [];    let riskScore = 0...`
22. **🏆 Prototype Compliance Decision** (`n8n-nodes-base.code`)
   - **In**: ['⚠️ Prototype Risk Aggregator']
   - **Out**: ['📤 Build Final Verification Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const failures = data.risk_failures || [];   const warnings = data....`
23. **📤 Build Final Verification Response** (`n8n-nodes-base.code`)
   - **In**: ['🏆 Prototype Compliance Decision']
   - **Out**: ['📤 RETURN VERIFICATION RESULT']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   return {     json: {       verification_id: `VER-${Date.now().toStr...`
24. **📤 RETURN VERIFICATION RESULT** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['🛑 Invalid Request Response', '📤 Build Final Verification Response', '🛑 Workflow Error Handler']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
25. **🛑 Workflow Error Handler** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: ['📤 RETURN VERIFICATION RESULT']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return [{   json: {     status: "ERROR",     decision: "MANUAL_REVIEW",     error: true,     message: "Verification workfl...`
26. **Note - Card 1 Master Orchestrator** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 🚀 MASTER ORCHESTRATOR Central coordinator for SIH-26100 bid verification. Coordinates sta...
27. **Note - Card 2 Input Validation** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: 📥 INPUT & VALIDATION Receive and validate bidder verification requests. Ensures request_i...
28. **Note - Card 3 Intelligent Routing** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 3: 🧠 INTELLIGENT ROUTING Determine which specialized verification workflows are required. De...
29. **Note - Card 4 Statutory** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 4: 🏛 STATUTORY GST • PAN • Udyam • MCA • EPFO • ESIC • Startup India • NSIC • BIS • DPIIT • ...
30. **Note - Card 5 Financial** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 5: 💰 FINANCIAL Turnover • P&L • Balance Sheet • ITR • CA/UDIN Validates financial threshold ...
31. **Note - Card 6 Document Intelligence** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 6: 🔍 DOCUMENT INTELLIGENCE Authenticity • OCR • Metadata • Signatures • QR Analyzes bid subm...
32. **Note - Card 7 Entity Resolution** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 7: 🔗 ENTITY RESOLUTION Cross-document legal entity consistency. Reconciles bidder name, CIN,...
33. **Note - Card 8 Risk Intelligence** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 8: ⚠️ RISK INTELLIGENCE Blacklisting • Debarment • Risk scoring. Evaluates debarment registe...
34. **Note - Card 9 Final Decision** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 9: 🏆 FINAL DECISION Compliance • Qualification • Risk • Evidence. Synthesizes findings into ...
35. **Note - Card 10 Reliability** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 10: 🔄 RELIABILITY Retry • Error handling • Fallback • Manual Review. Configured with max 3 r...

---

## Workflow: 🔹 SIH — PAN Verification Agent — Prototype (`pan_verification_agent.json`)
- **ID**: `SihPanAgentProto01`
- **Total Nodes**: 16 (Functional: 12, StickyNotes: 4)
- **Triggers**: ['Execute Workflow Trigger', '📥 PAN Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: ['🤖 PAN AI Agent (@n8n/n8n-nodes-langchain.agent)', '⚡ Groq Chat Model (@n8n/n8n-nodes-langchain.lmChatGroq)', '📋 Structured Output Parser (@n8n/n8n-nodes-langchain.outputParserStructured)']
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 PAN Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/pan-verification` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 PAN Test Webhook']
   - **Out**: ['🤖 PAN AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json.body || item.json;   let pan = (data.pan || "").toString().trim().toUp...`
4. **🤖 PAN AI Agent** (`@n8n/n8n-nodes-langchain.agent`)
   - **In**: ['🔍 Input Validation', '⚡ Groq Chat Model', '📋 Structured Output Parser']
   - **Out**: ['🏛 Mock PAN Registry']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
5. **⚡ Groq Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGroq`)
   - **In**: []
   - **Out**: ['🤖 PAN AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Credentials**: {'groqApi': {'id': 'groq_api_credential', 'name': 'Groq Account (Manual Config Required)'}}
6. **📋 Structured Output Parser** (`@n8n/n8n-nodes-langchain.outputParserStructured`)
   - **In**: []
   - **Out**: ['🤖 PAN AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
7. **🏛 Mock PAN Registry** (`n8n-nodes-base.code`)
   - **In**: ['🤖 PAN AI Agent']
   - **Out**: ['⚙️ PAN Format Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); const MOCK_PAN_REGISTRY = {   "AABCU9603R": {     registered_name: "ABC Technologies Pvt Ltd",     pan_type: "Company",   ...`
8. **⚙️ PAN Format Validation** (`n8n-nodes-base.code`)
   - **In**: ['🏛 Mock PAN Registry']
   - **Out**: ['🔗 Name Consistency Check']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); const PAN_REGEX = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/; const ENTITY_MAP = {   'C': 'Company',   'P': 'Individual/Person',   'H': ...`
9. **🔗 Name Consistency Check** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ PAN Format Validation']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const bidderName = (data.bidder_name || "").toUpperCase().trim();  ...`
10. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['🔗 Name Consistency Check', '🛑 PAN Error Fallback']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const record = data.mock_pan_record;      return {     json: {     ...`
11. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
12. **🛑 PAN Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "PAN_AGENT",     status: "REVIEW",     confidence: 0.0,     evidence: {  ...`
13. **Note - Input & Trigger** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟦 SECTION 1: TRIGGER & INPUT Accepts PAN verification requests via: 1. Execute Workflow (from Mas...
14. **Note - AI Analysis** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟪 SECTION 2: AI AGENT ANALYSIS Specialized PAN AI Agent powered by Groq Llama-3.3-70b-versatile. ...
15. **Note - Registry & Format** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟧 SECTION 3: MOCK REGISTRY & FORMAT CHECKS Validates PAN 10-char alphanumeric syntax. Inspects 4t...
16. **Note - Result & Reliability** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟩 SECTION 4: CANONICAL STANDARDIZED RESULT Returns canonical schema: `{ agent: 'PAN_AGENT', statu...

---

## Workflow: 🔹 SIH — Risk Intelligence Agent — Prototype (`risk_intelligence_agent.json`)
- **ID**: `SihRiskIntelligenceAgentProto01`
- **Total Nodes**: 13 (Functional: 11, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Risk Intelligence Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Risk Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Risk Intelligence Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Risk Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/risk-intelligence` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Risk Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Risk Intelligence Test Webhook']
   - **Out**: ['📦 Agent Result Collector']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json.body || item.json;   const errors = [];      const requestId = data.r...`
4. **📦 Agent Result Collector** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Risk Input Validation']
   - **Out**: ['🔍 Risk Signal Extraction']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  // Canonical list of known specialized agents in SIH-26100 const ALL_KNOWN_AGENTS = [   "GST_AGENT",   "PAN_AGENT",   "UD...`
5. **🔍 Risk Signal Extraction** (`n8n-nodes-base.code`)
   - **In**: ['📦 Agent Result Collector']
   - **Out**: ['📊 Confidence Risk Evaluation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function mapAgentToCategory(agent) {   const a = agent.toUpperCase();   if (a.includes('GST') || a.includes('PAN') || a.i...`
6. **📊 Confidence Risk Evaluation** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Risk Signal Extraction']
   - **Out**: ['🧮 Cumulative Risk Scoring']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const agents =...`
7. **🧮 Cumulative Risk Scoring** (`n8n-nodes-base.code`)
   - **In**: ['📊 Confidence Risk Evaluation']
   - **Out**: ['⚖️ Risk Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const extracte...`
8. **⚖️ Risk Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['🧮 Cumulative Risk Scoring']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      let status = "VERIFIED";   let confidence = 0.98;   let riskLev...`
9. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['⚖️ Risk Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
10. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
11. **🛑 Risk Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "RISK_INTELLIGENCE_AGENT",     status: "ERROR",     confidence: 0.0,     ...`
12. **Note - Card 1 Risk Agent** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: ⚠️ RISK INTELLIGENCE AGENT Deterministic risk aggregator across all child verification ag...
13. **Note - Card 2 Scoring Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC SCORING RULES Mathematical scoring breakdown: • NOT_VERIFIED: +40 pts (D...

---

## Workflow: 🔹 SIH — Tender Intelligence Agent — Prototype (`tender_intelligence_agent.json`)
- **ID**: `SihTenderIntelligenceAgentProto01`
- **Total Nodes**: 12 (Functional: 10, StickyNotes: 2)
- **Triggers**: ['Execute Workflow Trigger', '📥 Tender Intelligence Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: []
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Tender Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Tender Intelligence Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Tender Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/tender-intelligence` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Tender Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Tender Intelligence Test Webhook']
   - **Out**: ['⚙️ Requirement Extraction & Normalization']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function parseCurrency(val) {   if (typeof val === 'number') return isNaN(val) ? NaN : val;   if (typeof val !== 'string'...`
4. **⚙️ Requirement Extraction & Normalization** (`n8n-nodes-base.code`)
   - **In**: ['🔍 Tender Input Validation']
   - **Out**: ['📊 Requirement Coverage Analysis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function parseCurrency(val) {   if (typeof val === 'number') return isNaN(val) ? NaN : val;   if (typeof val !== 'string'...`
5. **📊 Requirement Coverage Analysis** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ Requirement Extraction & Normalization']
   - **Out**: ['⚠️ Ambiguity & Conflict Evaluation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  function parseCurrency(val) {   if (typeof val === 'number') return isNaN(val) ? NaN : val;   if (typeof val !== 'string'...`
6. **⚠️ Ambiguity & Conflict Evaluation** (`n8n-nodes-base.code`)
   - **In**: ['📊 Requirement Coverage Analysis']
   - **Out**: ['📊 Tender Intelligence Synthesis']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;   if (!data.valid_schema) return { json: data };      const rawReq =...`
7. **📊 Tender Intelligence Synthesis** (`n8n-nodes-base.code`)
   - **In**: ['⚠️ Ambiguity & Conflict Evaluation']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all();  return items.map(item => {   const data = item.json;      let status = "VERIFIED";   let confidence = 0.98;   let riskLev...`
8. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['📊 Tender Intelligence Synthesis']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: item.json }));...`
9. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
10. **🛑 Tender Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "TENDER_INTELLIGENCE_AGENT",     status: "ERROR",     confidence: 0.0,   ...`
11. **Note - Card 1 Tender Intelligence** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 1: 🧠 TENDER INTELLIGENCE AGENT Deterministic tender specification analysis. Extracts and nor...
12. **Note - Card 2 Extraction Rules** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## CARD 2: ⚙️ DETERMINISTIC EXTRACTION RULES Normalizes Indian currency notations (Crores, Lakhs) an...

---

## Workflow: 🔹 SIH — UDYAM/MSME Verification Agent — Prototype (`udyam_verification_agent.json`)
- **ID**: `SihUdyamAgentProto01`
- **Total Nodes**: 16 (Functional: 12, StickyNotes: 4)
- **Triggers**: ['Execute Workflow Trigger', '📥 Udyam Test Webhook', '📤 Return HTTP Response']
- **AI / LangChain Nodes**: ['🤖 UDYAM AI Agent (@n8n/n8n-nodes-langchain.agent)', '⚡ Groq Chat Model (@n8n/n8n-nodes-langchain.lmChatGroq)', '📋 Structured Output Parser (@n8n/n8n-nodes-langchain.outputParserStructured)']
- **Sub-Workflow Nodes**: []

### Node Inventory:
1. **Execute Workflow Trigger** (`n8n-nodes-base.executeWorkflowTrigger`)
   - **In**: []
   - **Out**: ['🔍 Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
2. **📥 Udyam Test Webhook** (`n8n-nodes-base.webhook`)
   - **In**: []
   - **Out**: ['🔍 Input Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Webhook Path**: `sih26100/udyam-verification` | Method: `POST` | ResponseMode: `responseNode`
3. **🔍 Input Validation** (`n8n-nodes-base.code`)
   - **In**: ['Execute Workflow Trigger', '📥 Udyam Test Webhook']
   - **Out**: ['🤖 UDYAM AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json.body || item.json;   const udyam = (data.udyam || data.udyam_registrat...`
4. **🤖 UDYAM AI Agent** (`@n8n/n8n-nodes-langchain.agent`)
   - **In**: ['🔍 Input Validation', '⚡ Groq Chat Model', '📋 Structured Output Parser']
   - **Out**: ['🏛 Mock MSME Registry']
   - **Error Handling**: retry=True (max 3, 2000ms), onError=continueRegularOutput
5. **⚡ Groq Chat Model** (`@n8n/n8n-nodes-langchain.lmChatGroq`)
   - **In**: []
   - **Out**: ['🤖 UDYAM AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Credentials**: {'groqApi': {'id': 'groq_api_credential', 'name': 'Groq Account (Manual Config Required)'}}
6. **📋 Structured Output Parser** (`@n8n/n8n-nodes-langchain.outputParserStructured`)
   - **In**: []
   - **Out**: ['🤖 UDYAM AI Agent']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
7. **🏛 Mock MSME Registry** (`n8n-nodes-base.code`)
   - **In**: ['🤖 UDYAM AI Agent']
   - **Out**: ['⚙️ Udyam Format Validation']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); const MOCK_UDYAM_REGISTRY = {   "UDYAM-TEST-001": {     enterprise_name: "ABC Technologies Pvt Ltd",     classification: "...`
8. **⚙️ Udyam Format Validation** (`n8n-nodes-base.code`)
   - **In**: ['🏛 Mock MSME Registry']
   - **Out**: ['🔗 Name Consistency Check']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); // Accepts official UDYAM-XX-00-0000000 OR prototype demo UDYAM-TEST-000 const UDYAM_OFFICIAL_REGEX = /^UDYAM-[A-Z]{2}-[0-...`
9. **🔗 Name Consistency Check** (`n8n-nodes-base.code`)
   - **In**: ['⚙️ Udyam Format Validation']
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const bidderName = (data.bidder_name || "").toUpperCase().trim();  ...`
10. **📤 Standardized Result** (`n8n-nodes-base.code`)
   - **In**: ['🔗 Name Consistency Check', '🛑 Udyam Error Fallback']
   - **Out**: ['📤 Return HTTP Response']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => {   const data = item.json;   const record = data.mock_udyam_record;      return {     json: {   ...`
11. **📤 Return HTTP Response** (`n8n-nodes-base.respondToWebhook`)
   - **In**: ['📤 Standardized Result']
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
12. **🛑 Udyam Error Fallback** (`n8n-nodes-base.code`)
   - **In**: []
   - **Out**: ['📤 Standardized Result']
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **JS Code Preview**: `const items = $input.all(); return items.map(item => ({   json: {     agent: "UDYAM_AGENT",     status: "REVIEW",     confidence: 0.0,     evidence: {...`
13. **Note - Input & Trigger** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟦 SECTION 1: TRIGGER & INPUT Accepts Udyam verification requests via: 1. Execute Workflow (from M...
14. **Note - AI Analysis** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟪 SECTION 2: AI AGENT ANALYSIS Specialized Udyam AI Agent powered by Groq Llama-3.3-70b-versatile...
15. **Note - Registry & Format** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟧 SECTION 3: MOCK REGISTRY & FORMAT CHECKS Validates official statutory format UDYAM-XX-00-000000...
16. **Note - Result & Reliability** (`n8n-nodes-base.stickyNote`)
   - **In**: []
   - **Out**: []
   - **Error Handling**: retry=None (max None, Nonems), onError=None
   - **Note Content**: ## 🟩 SECTION 4: CANONICAL STANDARDIZED RESULT Returns canonical schema: `{ agent: 'UDYAM_AGENT', sta...

---
