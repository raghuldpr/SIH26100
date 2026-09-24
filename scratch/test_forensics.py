import json
import subprocess
from pathlib import Path

def test_add_forensics():
    with open("tendertrust_architecture.architecture.json", "r", encoding="utf-8") as f:
        arch = json.load(f)

    # Add forensics_engine at [270, 350]
    forensics = {
        "id": "forensics_engine",
        "type": "security",
        "label": "Document Forensics",
        "sublabel": "Similarity & Tamper Signals",
        "tag": "Deterministic",
        "pos": [270, 350],
        "size": [140, 52]
    }
    
    # Check if already present
    arch["components"] = [c for c in arch["components"] if c["id"] != "forensics_engine"]
    arch["components"].append(forensics)

    # Connect forensics_engine -> rule_engine (direct horizontal)
    arch["connections"] = [c for c in arch["connections"] if c["id"] not in ["c_forensic_rule", "c_doc_forensic"]]
    arch["connections"].append({
        "id": "c_forensic_rule",
        "from": "forensics_engine",
        "to": "rule_engine",
        "label": "Forensic Signals",
        "variant": "default"
    })

    # Add forensics_engine to boundary
    for b in arch["boundaries"]:
        if b["label"] == "Deterministic Verification Services (Zero LLM)":
            if "forensics_engine" not in b["wraps"]:
                b["wraps"].append("forensics_engine")

    with open("tendertrust_architecture.architecture.json", "w", encoding="utf-8") as f:
        json.dump(arch, f, indent=2)

    cmd = ["node", r"C:\Users\Raghul\.agents\skills\archify\bin\archify.mjs", "validate", "architecture", "tendertrust_architecture.architecture.json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Return code:", res.returncode)
    print("Output:", res.stdout)
    if res.stderr:
        print("Error:", res.stderr)

test_add_forensics()
