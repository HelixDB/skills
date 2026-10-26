#!/usr/bin/env python3
"""Check MCP dependency endpoints and reject retired workflow instructions.

Run from any directory with Python 3.10+. No credentials or network are used.
These are static publication checks, not authenticated MCP acceptance tests.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
errors = []
for path in [
    ROOT / "README.md",
    *ROOT.glob("skills/**/*.md"),
    *ROOT.glob("docs/**/*.md"),
]:
    text = re.sub(r"\s+", " ", path.read_text())
    for pattern in (
        r"https://(?:query|admin)-mcp\.helix-db\.com/mcp",
        r"separate (?:Query|Admin) MCP",
        r"always (?:use|invoke) `?helix-mcp`? first",
        r"always invoke `helix-mcp` before",
        r"If MCP is unavailable, stop the Cloud-specific",
        r"not through MCP",
        r"create_tenant` \(creates a default read-write application key",
    ):
        if re.search(pattern, text):
            errors.append(f"{path.relative_to(ROOT)}: retired MCP guidance: {pattern}")

for name in ("helix-mcp", "helix-query-mcp", "helix-admin-mcp"):
    path = ROOT / "skills" / name / "agents/openai.yaml"
    text = path.read_text()
    urls = re.findall(r'^\s+url: "([^"\n]+)"$', text, re.MULTILINE)
    if urls != ["https://mcp.helix-db.com/mcp"]:
        errors.append(f"{name}: dependency must use exactly the unified MCP endpoint")
    if not re.search(r'^\s+value: "helix-db"$', text, re.MULTILINE):
        errors.append(
            f"{name}: dependency must use the shared helix-db server identifier"
        )
    if name != "helix-mcp" and "allow_implicit_invocation: false" not in text:
        errors.append(f"{name}: execution must require explicit invocation")

for path in ROOT.glob("skills/helix-query-*/SKILL.md"):
    text = path.read_text()
    if path.parent.name == "helix-query-mcp":
        continue
    if not all(
        term in text
        for term in (
            "Human OAuth",
            "Service credential",
            "Agent registration",
            "helix_get_started",
            "helix-query-mcp",
        )
    ):
        errors.append(
            f"{path.relative_to(ROOT)}: missing an identity-specific Cloud workflow"
        )

if errors:
    print("MCP contract checks failed:\n" + "\n".join(errors), file=sys.stderr)
    sys.exit(1)
print("MCP endpoints and identity-aware skill workflows validated.")
