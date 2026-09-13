import json

with open("c:/Users/Raghul/Desktop/SIH26100/scratch/n8n_summary.json", "r", encoding="utf-8") as f:
    summary = json.load(f)

for fname, wf in summary.items():
    print(f"\n==================================================")
    print(f"WORKFLOW: {fname}")
    print(f"ID: {wf['id']} | Name: {wf['name']} | Nodes: {wf['node_count']}")
    print(f"==================================================")
    for n in wf['nodes']:
        print(f"#{n['index']} | '{n['name']}' | Type: {n['type']} | Next: {n['next_nodes']}")
        if n['params_summary']:
            print(f"    Params: {n['params_summary']}")
