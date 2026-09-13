import json
import glob
import os

files = glob.glob("c:/Users/Raghul/Desktop/SIH26100/n8n/*.json")

report = []
for f in sorted(files):
    fname = os.path.basename(f)
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    wf = data[0] if isinstance(data, list) else data
    
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    
    # Map incoming and outgoing connections
    outgoing = {}
    incoming = {}
    for src_name, conn_data in connections.items():
        if isinstance(conn_data, dict):
            for conn_type, port_groups in conn_data.items():
                for group in port_groups:
                    for target_item in group:
                        tgt = target_item.get("node")
                        outgoing.setdefault(src_name, []).append((tgt, conn_type))
                        incoming.setdefault(tgt, []).append((src_name, conn_type))

    report.append(f"## Workflow: {wf.get('name')} (`{fname}`)")
    report.append(f"- **ID**: `{wf.get('id')}`")
    report.append(f"- **Total Nodes**: {len(nodes)} (Functional: {len([n for n in nodes if n.get('type') != 'n8n-nodes-base.stickyNote'])}, StickyNotes: {len([n for n in nodes if n.get('type') == 'n8n-nodes-base.stickyNote'])})")
    
    # Find triggers
    triggers = [n for n in nodes if "trigger" in n.get("type", "").lower() or "webhook" in n.get("type", "").lower()]
    report.append(f"- **Triggers**: {[t.get('name') for t in triggers]}")
    
    # Find AI/Groq nodes
    ai_nodes = [n for n in nodes if "@n8n/n8n-nodes-langchain" in n.get("type", "")]
    report.append(f"- **AI / LangChain Nodes**: {[a.get('name') + ' (' + a.get('type') + ')' for a in ai_nodes]}")
    
    # Find Executed sub-workflows
    sub_wfs = [n for n in nodes if n.get("type") == "n8n-nodes-base.executeWorkflow"]
    report.append(f"- **Sub-Workflow Nodes**: {[s.get('name') + ' -> targetId: ' + str(s.get('parameters', {}).get('workflowId')) for s in sub_wfs]}")
    
    # Nodes details
    report.append("\n### Node Inventory:")
    for idx, n in enumerate(nodes, 1):
        name = n.get("name")
        ntype = n.get("type")
        is_sticky = ntype == "n8n-nodes-base.stickyNote"
        outs = outgoing.get(name, [])
        ins = incoming.get(name, [])
        cred = n.get("credentials")
        retry = n.get("retryOnFail")
        max_tries = n.get("maxTries")
        wait_between = n.get("waitBetweenTries")
        on_err = n.get("onError")
        params = n.get("parameters", {})
        
        report.append(f"{idx}. **{name}** (`{ntype}`)")
        report.append(f"   - **In**: {[i[0] for i in ins]}")
        report.append(f"   - **Out**: {[o[0] for o in outs]}")
        report.append(f"   - **Error Handling**: retry={retry} (max {max_tries}, {wait_between}ms), onError={on_err}")
        if cred:
            report.append(f"   - **Credentials**: {cred}")
        if is_sticky:
            content_preview = params.get("content", "")[:100].replace("\n", " ")
            report.append(f"   - **Note Content**: {content_preview}...")
        elif "jsCode" in params:
            code_preview = params.get("jsCode", "")[:150].replace("\n", " ")
            report.append(f"   - **JS Code Preview**: `{code_preview}...`")
        elif "url" in params:
            report.append(f"   - **URL**: `{params.get('url')}` | Method: `{params.get('method')}`")
        elif "path" in params:
            report.append(f"   - **Webhook Path**: `{params.get('path')}` | Method: `{params.get('httpMethod')}` | ResponseMode: `{params.get('responseMode')}`")
    report.append("\n---\n")

with open("c:/Users/Raghul/Desktop/SIH26100/scratch/n8n_detailed_audit.md", "w", encoding="utf-8") as fp:
    fp.write("\n".join(report))

print("Generated detailed audit report successfully!")
