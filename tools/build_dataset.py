"""Generate the synthetic documents, both policy PDFs, and data/gold/gold.json."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATAGEN = ROOT / "tools" / "datagen"
DATASET = ROOT / "data" / "dataset"
POLICIES = ROOT / "data" / "policies"


def run(script):
    env = os.environ.copy()
    env["DOC_OUT_DIR"] = str(DATASET)
    env["POLICY_OUT_DIR"] = str(POLICIES)
    print(f"\n== {script} ==")
    subprocess.run([sys.executable, str(DATAGEN / script)], cwd=DATAGEN, env=env, check=True)


def main():
    POLICIES.mkdir(parents=True, exist_ok=True)
    run("generate_docs.py")
    run("generate_gold_policy.py")
    run("generate_silver_policy.py")
    run("generate_unknown.py")
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_gold.py")], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
