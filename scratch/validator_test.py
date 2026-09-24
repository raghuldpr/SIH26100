import json
import subprocess
import re
from pathlib import Path

def run_validate():
    cmd = ["node", r"C:\Users\Raghul\.agents\skills\archify\bin\archify.mjs", "validate", "architecture", "tendertrust_architecture.architecture.json"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode, res.stdout, res.stderr

print("Validator checker ready")
