"""Vendors upstream substrates into packs/ at pinned commits.

    python scripts/vendor_packs.py

Three packs:
  packs/simulation/             engineering-intelligence-simulation data + scenarios
  packs/quality-engineering/    31 SKILL.md definitions (8 agents + 23 skills)
  packs/automotive-engineering/ AGENTS.md + agent profile

Upstream content is copied VERBATIM. No reformatting, no "improvement" - the
upstream wording is the expertise, and modifying it creates attribution
obligations and drift.

Every file is sha256'd into packs/MANIFEST.json so later tampering is detectable.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKS = os.path.join(ROOT, "packs")

# A local clone of the public simulation repository (set SIMULATION_SOURCE_DIR).
SIM_LOCAL = os.environ.get("SIMULATION_SOURCE_DIR", "")
SIM_REPO = "rahulphaltankar/engineering-intelligence-simulation"

QES_REPO = "RBraga01/Quality-Engineering-Skills"
QES_BRANCH = "master"
KD_REPO = "K-Dense-AI/scientific-agents"
KD_BRANCH = "main"
KD_PATH = "scientific-agents/automotive-engineer"


GH = shutil.which("gh") or "gh"


def gh(endpoint: str) -> dict | list:
    out = subprocess.run([GH, "api", endpoint], capture_output=True, text=True,
                         encoding="utf-8", shell=False)
    if out.returncode != 0 or not out.stdout:
        raise RuntimeError(f"gh api {endpoint} failed: "
                           f"rc={out.returncode} {(out.stderr or '')[:300]}")
    return json.loads(out.stdout)


def head_sha(repo: str, branch: str) -> str:
    return gh(f"repos/{repo}/commits/{branch}")["sha"]


def fetch_text(repo: str, path: str, ref: str) -> str:
    data = gh(f"repos/{repo}/contents/{path}?ref={ref}")
    return base64.b64decode(data["content"]).decode("utf-8")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def vendor_simulation(manifest: list) -> None:
    dest = os.path.join(PACKS, "simulation")
    if not SIM_LOCAL or not os.path.isdir(SIM_LOCAL):
        print("  SIMULATION_SOURCE_DIR not set to a local clone of "
              f"github.com/{SIM_REPO}; skipping")
        return
    sha = subprocess.run(["git", "-C", SIM_LOCAL, "rev-parse", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    for sub in ("data", "scenarios", "schemas"):
        src = os.path.join(SIM_LOCAL, sub)
        if not os.path.isdir(src):
            continue
        tgt = os.path.join(dest, sub)
        if os.path.isdir(tgt):
            shutil.rmtree(tgt)
        shutil.copytree(src, tgt)
    count = 0
    for root, _, files in os.walk(dest):
        for f in files:
            if f == "pack.yaml":
                continue
            p = os.path.join(root, f)
            manifest.append({
                "pack": "simulation", "source_repo": SIM_REPO, "commit": sha,
                "path": os.path.relpath(p, PACKS).replace("\\", "/"),
                "licence": "MIT", "sha256": sha256(p), "modified": False})
            count += 1
    write(os.path.join(dest, "pack.yaml"),
          "name: simulation\nversion: 0.1.0\n"
          f"source_repo: https://github.com/{SIM_REPO}\ncommit: {sha}\n"
          "licence: MIT\nprovides:\n  - simulation-connector-data\n"
          "data_classification: >-\n"
          "  SIMULATED ENTERPRISE ARTEFACT - not OEM, customer or proprietary data\n")
    print(f"  packs/simulation           {count} files @ {sha[:8]}")


def vendor_quality(manifest: list) -> None:
    sha = head_sha(QES_REPO, QES_BRANCH)
    tree = gh(f"repos/{QES_REPO}/git/trees/{sha}?recursive=1")["tree"]
    wanted = [n["path"] for n in tree if n["type"] == "blob"
              and n["path"].startswith("skills/")
              and n["path"].endswith((".md", ".yaml", ".yml"))]
    dest = os.path.join(PACKS, "quality-engineering")
    skills, agents = [], []
    for path in wanted:
        text = fetch_text(QES_REPO, path, sha)
        target = os.path.join(dest, path)
        write(target, text)
        manifest.append({
            "pack": "quality-engineering", "source_repo": QES_REPO, "commit": sha,
            "path": os.path.relpath(target, PACKS).replace("\\", "/"),
            "licence": "MIT", "sha256": sha256(target), "modified": False})
        if path.endswith("SKILL.md"):
            name = path.split("/")[-2]
            (agents if "/agents/" in path else skills).append(name)
    for extra in ("LICENSE", "THIRD_PARTY_CONTENT.md"):
        try:
            write(os.path.join(dest, extra), fetch_text(QES_REPO, extra, sha))
        except RuntimeError:
            pass
    write(os.path.join(dest, "pack.yaml"),
          "name: quality-engineering\nversion: 0.1.0\n"
          f"source_repo: https://github.com/{QES_REPO}\ncommit: {sha}\n"
          "licence: MIT\nattribution: RBraga01\nprovides:\n"
          + "".join(f"  - agent: {a}\n" for a in sorted(agents))
          + "".join(f"  - skill: {s}\n" for s in sorted(skills)))
    print(f"  packs/quality-engineering  {len(wanted)} files, "
          f"{len(agents)} agents + {len(skills)} skills @ {sha[:8]}")


def vendor_automotive(manifest: list) -> None:
    sha = head_sha(KD_REPO, KD_BRANCH)
    dest = os.path.join(PACKS, "automotive-engineering")
    files = ["AGENTS.md", "CLAUDE.md", "agents/automotive-engineer.md"]
    ok = []
    for rel in files:
        try:
            text = fetch_text(KD_REPO, f"{KD_PATH}/{rel}", sha)
        except RuntimeError:
            continue
        target = os.path.join(dest, rel)
        write(target, text)
        manifest.append({
            "pack": "automotive-engineering", "source_repo": KD_REPO, "commit": sha,
            "path": os.path.relpath(target, PACKS).replace("\\", "/"),
            "licence": "MIT", "sha256": sha256(target), "modified": False})
        ok.append(rel)
    try:
        write(os.path.join(dest, "LICENSE"), fetch_text(KD_REPO, "LICENSE", sha))
    except RuntimeError:
        pass
    write(os.path.join(dest, "pack.yaml"),
          "name: automotive-engineering\nversion: 0.1.0\n"
          f"source_repo: https://github.com/{KD_REPO}\ncommit: {sha}\n"
          f"source_path: {KD_PATH}\nlicence: MIT\nattribution: K-Dense AI\n"
          "provides:\n  - agent: automotive-engineer\n")
    print(f"  packs/automotive-engineering {len(ok)} files @ {sha[:8]}")


def main() -> int:
    os.makedirs(PACKS, exist_ok=True)
    manifest: list = []
    print("Vendoring upstream packs (verbatim, pinned):")
    vendor_simulation(manifest)
    try:
        vendor_quality(manifest)
        vendor_automotive(manifest)
    except RuntimeError as exc:
        print(f"  GitHub fetch failed: {exc}")
        print("  Existing vendored packs (if any) are retained.")
    with open(os.path.join(PACKS, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump({"description": "Vendored upstream content with integrity hashes.",
                   "files": manifest}, fh, indent=2)
    print(f"\n  packs/MANIFEST.json        {len(manifest)} files hashed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
