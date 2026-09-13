import json
import glob
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

files = glob.glob("c:/Users/Raghul/Desktop/SIH26100/n8n/*.json")
summary = {}

for f in sorted(files):
    fname = os.path.basename(f)
    with open(f, "r", encoding="utf-8") as fp:
        data = json.load(fp)
    wf = data[0] if isinstance(data, list) else data
    nodes = wf.get("nodes", [])
    connections = wf.get("connections", {})
    
    # map outgoing connections
    outgoing = {}
    for src_name, conn_data in connections.items():
        targets = []
        if isinstance(conn_data, dict):
            for conn_type, port_groups in conn_data.items():
                for group in port_groups:
                    for target_item in group:
                        targets.append({
                            "target": target_item.get("node"),
                            "type": conn_type
                        })
        outgoing[src_name] = targets
    
    node_list = []
    for i, n in enumerate(nodes, 1):
        name = n.get("name")
        ntype = n.get("type")
        cred = n.get("credentials")
        retry = n.get("retryOnFail")
        max_tries = n.get("maxTries")
        wait_between = n.get("waitBetweenTries")
        on_error = n.get("onError")
        params = n.get("parameters", {})
        next_nodes = [t["target"] for t in outgoing.get(name, [])]
        
        # summary of parameters
        p_summary = {}
        if ntype == "n8n-nodes-base.webhook":
            p_summary = {"httpMethod": params.get("httpMethod"), "path": params.get("path"), "responseMode": params.get("responseMode")}
        elif ntype == "n8n-nodes-base.executeWorkflow":
            p_summary = {"workflowId": params.get("workflowId")}
        elif ntype == "n8n-nodes-base.httpRequest":
            p_summary = {"url": params.get("url"), "method": params.get("method")}
        elif ntype == "n8n-nodes-base.switch":
            p_summary = {"rules": len(params.get("rules", {}).get("values", []))}
        elif ntype == "n8n-nodes-base.if":
            p_summary = {"conditions": params.get("conditions")}
        elif "@n8n/n8n-nodes-langchain" in ntype:
            p_summary = {"model": params.get("model"), "options": params.get("options")}
        
        node_list.append({
            "index": i,
            "name": name,
            "id": n.get("id"),
            "type": ntype,
            "typeVersion": n.get("typeVersion"),
            "credentials": cred,
            "retryOnFail": retry,
            "maxTries": max_tries,
            "waitBetweenTries": wait_between,
            "onError": on_error,
            "params_summary": p_summary,
            "next_nodes": next_nodes,
            "has_jsCode": "jsCode" in params
        })
    
    summary[fname] = {
        "id": wf.get("id"),
        "name": wf.get("name"),
        "node_count": len(nodes),
        "nodes": node_list
    }

with open("c:/Users/Raghul/Desktop/SIH26100/scratch/n8n_summary.json", "w", encoding="utf-8") as out_fp:
    json.dump(summary, out_fp, indent=2, ensure_ascii=False)

print("Parsed", len(files), "workflows successfully!")
for fname, w in summary.items():
    print(f"{fname}: {w['node_count']} nodes | Name: {w['name']}")
