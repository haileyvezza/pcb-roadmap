"""Build the unassigned PCB people list for the Coverage Gaps section.

Sources:
  1. PCB roster from Vault (team 1722 and descendants)
  2. Active roadmap projects from /Users/haileyvezza/pcb-roadmap/data/projects.json
  3. Contributors per project via vault_get_project

Output: /tmp/h2_migration/unassigned_people.json + printed summary.
"""

import json
import os
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

sys.path.insert(0, "/tmp/h2_migration")
from vault_http import VaultMcp


# --- Config ---------------------------------------------------------------

PARENT_TEAMS = {
    # team_id: (display_name, vault_team_name)
    "16570": ("Cross-Border", "Cross Border"),
    "16935": ("Ledger", "Ledger"),
    "663": ("Money Movement", "Money Movement"),
    "16574": ("Payments Merchant Experience", "Payments Experience"),
    "2048": ("Payments Platform Risk", "Payments Platform & Risk"),
    "1884": ("Shop Wallet", "Shop Wallet"),
}
PCB_TOP_TEAM_ID = "1722"
PCB_TOP_BUCKET = "PCB Leadership / Cross-functional"

# Manually mapped known descendants (already discovered via vault_get_team).
KNOWN_DESCENDANTS = {
    "663": ["16893"],  # Funds Flow
    "1884": ["16600", "16895", "16970", "16973"],
    "2048": ["13514", "13515", "13626", "13801", "13843", "16576", "16739", "16903"],
    "16574": ["2912", "13625", "16738", "17325"],
    "16935": [],
    "16570": ["16572", "16573"],
}

EXCLUDED = {
    "rohit mishra", "weiqing tu", "sadia latifi", "vishal morde",
    "josh kraut", "hailey vezza", "sofia karabevic", "anita tang",
    # Corrections/aliases: "Sofia Karabevic" is likely "Sofia Karabasevic"
    # (Corpo team, not in PCB roster anyway).
    "sofia karabasevic",
}

INACTIVE_PHASES = {"done", "stopped", "backlog", "paused"}

PROJECTS_JSON = "/Users/haileyvezza/pcb-roadmap/data/projects.json"
OUT_JSON = "/tmp/h2_migration/unassigned_people.json"
DEBUG_JSON = "/tmp/h2_migration/unassigned_debug.json"


# --- Name normalization ---------------------------------------------------

def normalize(name):
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.strip().lower()
    # strip middle initials like "Alice B. Chen" -> "alice chen"
    parts = s.split()
    if len(parts) >= 3:
        cleaned = []
        for i, p in enumerate(parts):
            if 0 < i < len(parts) - 1 and (
                len(p.rstrip(".")) == 1 or p.endswith(".")
            ):
                continue
            cleaned.append(p)
        s = " ".join(cleaned)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Parsers --------------------------------------------------------------

def _text(resp):
    """Extract text content from a vault_get_* MCP JSON-RPC response."""
    if not isinstance(resp, dict):
        return ""
    res = resp.get("result") or {}
    content = res.get("content") or []
    parts = []
    for c in content:
        if isinstance(c, dict) and c.get("type") == "text":
            parts.append(c.get("text") or "")
    return "\n".join(parts)


TEAM_MEMBER_LINE = re.compile(
    r"^-\s+\*\*\[([^\]]+)\]\(([^)]+)\)\*\*\s*-\s*(.+?)\s*\((Home team|Additional team)\)"
)


def parse_team_members(text, deepest_team_name):
    """Yield (name, url, title, home_team_bool, deepest_team_name) rows.

    Only Home team members are treated as belonging to `deepest_team_name`;
    Additional team members are recorded too but their "home team" is
    resolved separately by seeing them elsewhere as Home team.
    """
    for line in text.splitlines():
        m = TEAM_MEMBER_LINE.match(line.strip())
        if not m:
            continue
        name, url, title, home = m.groups()
        yield {
            "name": name.strip(),
            "url": url.strip(),
            "title": title.strip(),
            "home_team_here": home == "Home team",
            "seen_in_team": deepest_team_name,
        }


PROJECT_ID_RE = re.compile(r"/projects/(\d+)")
NAME_LINK_RE = re.compile(r"\[@?([^\]]+)\]\(https://vault\.shopify\.io/users/[^)]+\)")
BULLET_NAME_LINK_RE = re.compile(
    r"^-\s+\[@?([^\]]+)\]\(https://vault\.shopify\.io/users/[^)]+\)"
)


def parse_project_people(text):
    """From vault_get_project markdown text, extract champion, aimers,
    and contributors (list of names)."""
    champion = None
    aimers = []
    contributors = []
    lines = text.splitlines()

    mode = None  # None | 'aimers' | 'contrib'
    for raw in lines:
        line = raw.strip()
        low = line.lower()
        # Detect section start markers
        if low.startswith("**aimers**") or low.startswith("- **aimers**"):
            mode = "aimers"
            # sometimes single-line aimer: **Aimer**: [@Name]
            m = NAME_LINK_RE.search(line)
            if m and ":" in line:
                aimers.append(m.group(1).strip())
            continue
        if low.startswith("**contributors**") or low.startswith("- **contributors**"):
            mode = "contrib"
            continue
        if low.startswith("**champion**") or low.startswith("- **champion**"):
            mode = None
            m = NAME_LINK_RE.search(line)
            if m:
                champion = m.group(1).strip()
            continue
        # Also handle the old-style "## Direct Contributors" header
        if low.startswith("## direct contributors") or low.startswith("## contributors"):
            mode = "contrib"
            continue

        # Section terminators: another **Field**: line, or a header
        if line.startswith("## ") or line.startswith("# "):
            mode = None
            continue
        if line.startswith("**") and line.endswith("**:"):
            mode = None
            continue
        if line.startswith("**") and "**:" in line and not line.startswith("**Aimers**") and not line.startswith("**Contributors**"):
            mode = None
            continue

        if mode == "aimers":
            m = BULLET_NAME_LINK_RE.match(line)
            if m:
                aimers.append(m.group(1).strip())
        elif mode == "contrib":
            m = BULLET_NAME_LINK_RE.match(line)
            if m:
                contributors.append(m.group(1).strip())

    # De-dup aimers (same person may appear as Mission/Product/Technical aimer)
    seen = set()
    dedup_aimers = []
    for a in aimers:
        k = a.lower()
        if k not in seen:
            seen.add(k)
            dedup_aimers.append(a)
    return {"champion": champion, "aimers": dedup_aimers, "contributors": contributors}


# --- Roster fetch ---------------------------------------------------------

def fetch_roster(client):
    """Return dict: normalized_name -> {name, title, teams, home_team_name}."""
    roster = {}

    # Team_id -> deepest display team name.
    # For descendants we get the real Vault team name from the response header.
    def add_from_response(text, deepest_name, parent_display):
        header = None
        for ln in text.splitlines():
            if ln.startswith("# Team Members:"):
                header = ln.replace("# Team Members:", "").strip()
                break
        display_team = header or deepest_name
        for row in parse_team_members(text, display_team):
            nn = normalize(row["name"])
            if not nn:
                continue
            entry = roster.setdefault(
                nn,
                {
                    "name": row["name"],
                    "title": row["title"],
                    "teams_seen": [],
                    "home_team": None,
                    "parent_bucket": None,
                },
            )
            if display_team not in entry["teams_seen"]:
                entry["teams_seen"].append(display_team)
            if row["home_team_here"]:
                entry["home_team"] = display_team
                entry["parent_bucket"] = parent_display
                entry["title"] = row["title"]  # prefer title on home team
            elif entry["parent_bucket"] is None:
                entry["parent_bucket"] = parent_display

    # Fetch all teams (parents + known descendants + top-level 1722) in parallel.
    tasks = []
    tasks.append((PCB_TOP_TEAM_ID, PCB_TOP_BUCKET, PCB_TOP_BUCKET))
    for pid, (display, _) in PARENT_TEAMS.items():
        tasks.append((pid, display, display))
        for cid in KNOWN_DESCENDANTS.get(pid, []):
            tasks.append((cid, display, display))

    responses = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut_to_tid = {
            ex.submit(client.call, "vault_get_team_members", {"team_id": tid}): (tid, parent, deepest)
            for (tid, parent, deepest) in tasks
        }
        for fut in as_completed(fut_to_tid):
            tid, parent, deepest = fut_to_tid[fut]
            resp = fut.result()
            responses[tid] = {"parent_display": parent, "text": _text(resp), "raw": resp}

    for tid, info in responses.items():
        add_from_response(info["text"], info["parent_display"], info["parent_display"])

    return roster, responses


# --- Projects -------------------------------------------------------------

def load_active_projects():
    """Return list of dicts: {project, team, champion, phase, vault_url}."""
    with open(PROJECTS_JSON) as f:
        data = json.load(f)
    rows = data["rows"]
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    vault_urls = data.get("vaultUrls", {})

    active = []
    inactive = []
    for row in rows[1:]:
        rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header)}
        phase = (rec.get("Phase") or "").strip()
        vault_status = (rec.get("Vault Status") or "").strip()
        project = (rec.get("Project") or "").strip()
        if not project:
            continue
        if vault_status.lower() != "on vault":
            inactive.append((project, vault_status, phase))
            continue
        if not phase or phase.lower() in INACTIVE_PHASES:
            inactive.append((project, vault_status, phase))
            continue
        vault_url = vault_urls.get(project, "")
        active.append({
            "project": project,
            "team": (rec.get("Team") or "").strip(),
            "champion": (rec.get("Champion") or "").strip(),
            "phase": phase,
            "vault_url": vault_url,
        })
    return active, inactive


def extract_project_id(url):
    if not url:
        return None
    m = PROJECT_ID_RE.search(url)
    if m:
        return m.group(1)
    return None


def fetch_project_people(client, project_ids):
    """Return dict: project_id -> {champion, aimer, contributors} or {error: ...}."""
    results = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut_to_pid = {}
        for pid in project_ids:
            fut = ex.submit(_fetch_one_project, client, pid)
            fut_to_pid[fut] = pid
        for fut in as_completed(fut_to_pid):
            pid = fut_to_pid[fut]
            try:
                results[pid] = fut.result()
            except Exception as e:  # pragma: no cover
                results[pid] = {"error": str(e)}
    return results


def _fetch_one_project(client, pid, retries=2):
    delay = 0.5
    last_err = None
    for _ in range(retries + 1):
        try:
            resp = client.call("vault_get_project", {"project_id": str(pid)})
            text = _text(resp)
            if not text:
                last_err = f"empty response: {json.dumps(resp)[:200]}"
                time.sleep(delay)
                delay *= 2
                continue
            parsed = parse_project_people(text)
            parsed["_text_snip"] = text[:200]
            return parsed
        except Exception as e:
            last_err = str(e)
            time.sleep(delay)
            delay *= 2
    return {"error": last_err or "unknown"}


# --- Main -----------------------------------------------------------------

def main():
    client = VaultMcp(timeout=90)

    print("Fetching roster...")
    t0 = time.time()
    roster, team_responses = fetch_roster(client)
    print(f"  roster size (normalized names): {len(roster)}  in {time.time()-t0:.1f}s")

    print("Loading active projects from projects.json...")
    active_projects, inactive = load_active_projects()
    print(f"  active: {len(active_projects)}  (inactive/skipped: {len(inactive)})")

    project_ids = []
    missing_url = []
    for p in active_projects:
        pid = extract_project_id(p["vault_url"])
        if pid:
            project_ids.append(pid)
            p["_pid"] = pid
        else:
            missing_url.append(p)
    unique_pids = sorted(set(project_ids))
    print(f"  vault project ids to fetch: {len(unique_pids)} (missing URL: {len(missing_url)})")

    print("Fetching project contributors...")
    t0 = time.time()
    project_people = fetch_project_people(client, unique_pids)
    print(f"  fetched {len(project_people)} projects in {time.time()-t0:.1f}s")

    # Compute assigned set
    assigned_norms = set()
    assigned_debug = []

    # From projects.json champions
    for p in active_projects:
        nm = p["champion"]
        if nm:
            n = normalize(nm)
            if n:
                assigned_norms.add(n)
                assigned_debug.append({"source": "sheet_champion", "project": p["project"], "name": nm})

    # From vault project responses
    project_errors = []
    for p in active_projects:
        pid = p.get("_pid")
        if not pid:
            continue
        info = project_people.get(pid)
        if not info or "error" in info:
            project_errors.append({"project": p["project"], "pid": pid, "error": (info or {}).get("error")})
            continue
        for nm in filter(None, [info.get("champion")]):
            n = normalize(nm)
            if n:
                assigned_norms.add(n)
                assigned_debug.append({"source": "vault_champion", "project": p["project"], "name": nm})
        for nm in info.get("aimers", []) or []:
            n = normalize(nm)
            if n:
                assigned_norms.add(n)
                assigned_debug.append({"source": "vault_aimer", "project": p["project"], "name": nm})
        for nm in info.get("contributors", []):
            n = normalize(nm)
            if n:
                assigned_norms.add(n)
                assigned_debug.append({"source": "vault_contributor", "project": p["project"], "name": nm})

    # Sanity: excluded people not in roster
    roster_norms = set(roster.keys())
    excluded_missing = [ex for ex in EXCLUDED if ex not in roster_norms]

    # Compute unassigned
    unassigned = []
    for nn, entry in roster.items():
        if nn in EXCLUDED:
            continue
        if nn in assigned_norms:
            continue
        unassigned.append({
            "team": entry.get("parent_bucket") or "Unknown",
            "person": entry["name"],
            "role": entry.get("title") or "",
            "home_team": entry.get("home_team") or "",
        })

    # Group by team for summary
    teams_order = [
        "Cross-Border", "Ledger", "Money Movement",
        "Payments Merchant Experience", "Payments Platform Risk", "Shop Wallet",
        PCB_TOP_BUCKET,
    ]
    by_team = {t: [] for t in teams_order}
    for u in unassigned:
        by_team.setdefault(u["team"], []).append(u)
    for lst in by_team.values():
        lst.sort(key=lambda x: x["person"])

    print("\n=== SUMMARY ===")
    print(f"Total PCB roster size: {len(roster)}")
    print(f"Total active projects scanned: {len(active_projects)}  (unique vault IDs: {len(unique_pids)})")
    print(f"Total assigned people (unique normalized): {len(assigned_norms)}")
    print(f"Excluded count: {len(EXCLUDED)}")
    print(f"Unassigned count: {len(unassigned)}")

    print("\n--- By team ---")
    for t in teams_order:
        rows = by_team.get(t, [])
        print(f"\n### {t}  ({len(rows)} unassigned)")
        for r in rows:
            role = r["role"] or "(no title)"
            home = r["home_team"] or "(no home team)"
            print(f"  - {r['person']} — {role}  [home: {home}]")
    other = {k: v for k, v in by_team.items() if k not in teams_order}
    for t, rows in other.items():
        print(f"\n### {t}  ({len(rows)} unassigned)")
        for r in rows:
            print(f"  - {r['person']} — {r['role'] or '(no title)'}  [home: {r['home_team'] or '(no home team)'}]")

    print("\n--- Sanity checks ---")
    if excluded_missing:
        print(f"Excluded names NOT found in roster (possible spelling mismatches): {excluded_missing}")
    else:
        print("All excluded names matched a roster entry.")

    if project_errors:
        print(f"Projects that failed to load contributor info: {len(project_errors)}")
        for pe in project_errors:
            print(f"  - {pe['pid']}: {pe['project']}  ({pe.get('error')})")
    else:
        print("All projects loaded successfully.")

    if missing_url:
        print(f"Active projects with no Vault URL: {len(missing_url)}")
        for p in missing_url:
            print(f"  - {p['project']} ({p['team']})")

    # Save structured output
    output = {
        "generated": date.today().isoformat(),
        "roster_size": len(roster),
        "active_projects_scanned": len(active_projects),
        "assigned_count": len(assigned_norms),
        "excluded_count": len(EXCLUDED),
        "unassigned": [
            {"team": u["team"], "person": u["person"], "role": u["role"]}
            for u in sorted(unassigned, key=lambda x: (x["team"], x["person"]))
        ],
    }
    with open(OUT_JSON, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nWrote {OUT_JSON}")

    debug = {
        "roster": roster,
        "assigned_debug": assigned_debug,
        "project_errors": project_errors,
        "missing_url_projects": [p["project"] for p in missing_url],
        "excluded_missing": excluded_missing,
        "by_team_counts": {t: len(rows) for t, rows in by_team.items()},
    }
    with open(DEBUG_JSON, "w") as f:
        json.dump(debug, f, indent=2, default=str)
    print(f"Wrote {DEBUG_JSON}")


if __name__ == "__main__":
    main()
