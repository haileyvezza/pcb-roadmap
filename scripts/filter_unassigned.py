#!/usr/bin/env python3
"""Filter unassigned people list to ICs (Engineers + PMs).

Excludes:
 - Directors, Development Managers, Managers of Engineering, Engineering Managers
 - Designers (any level)
 - Data Scientists, Data Engineers, ML-only roles that are DS/DE
 - Product Marketing, Writers, Ops, Business Analysts, Data Insights managers
 - Interns, Apprentices, Dev Degree
 - Product Leads (org-level, not project Champions)

Keeps:
 - Engineers, Senior Engineers, Staff Engineers, Principal Engineers, Software Engineers
 - Applied ML / ML Engineers who are ICs
 - Frontend / Backend Developers
 - Product Managers (individual, not leads/directors)
"""

import json
import re
from pathlib import Path

SRC = Path('/tmp/h2_migration/unassigned_people.json')
OUT = Path('/tmp/h2_migration/unassigned_people_filtered.json')

# Case-insensitive substring matches on role/title
EXCLUDE_PATTERNS = [
    r'\bdirector\b',
    r'\bmanager,\s*engineering\b',
    r'\bmanager,\s*data\b',
    r'\bengineering manager\b',
    r'\bdevelopment manager\b',
    r'\bsenior development manager\b',
    r'\bdesigner\b',
    r'\bproduct data scientist\b',
    r'\bdata scientist\b',
    r'\bdata engineer\b',
    r'\bapprentice\b',
    r'\bintern\b',
    r'\bdev degree\b',
    r'\bwriter\b',
    r'\bbusiness analyst\b',
    r'\bproduct marketing\b',
    r'\bproduct lead\b',
    r'\boperations\b',
    r'\bexpansion pack\b',
]

pat = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)

data = json.loads(SRC.read_text())
kept = []
dropped = []
for p in data['unassigned']:
    role = p.get('role', '')
    if pat.search(role):
        dropped.append(p)
    else:
        kept.append(p)

# Group by team + sort by role seniority (Principal > Staff > Senior > Engineer/Developer > other)
def seniority_key(role: str) -> int:
    r = role.lower()
    if 'principal' in r: return 0
    if 'senior staff' in r: return 1
    if 'staff' in r: return 2
    if 'senior' in r: return 3
    return 4

TEAM_ORDER = [
    'Money Movement',
    'Payments Platform Risk',
    'Cross-Border',
    'Payments Merchant Experience',
    'Shop Wallet',
    'Ledger',
    'PCB Leadership / Cross-functional',
]

by_team = {}
for p in kept:
    by_team.setdefault(p['team'], []).append(p)

for team, people in by_team.items():
    people.sort(key=lambda p: (seniority_key(p['role']), p['person']))

ordered = []
for team in TEAM_ORDER:
    if team in by_team:
        ordered.extend(by_team[team])
# Add any teams that weren't in the ordered list (safety net)
for team, people in by_team.items():
    if team not in TEAM_ORDER:
        ordered.extend(people)

result = {
    'generated': data['generated'],
    'source': 'Vault team 1722 (Payments & Cross Border) roster - ICs (Engineers + PMs) not listed as Champion, Aimer, or Contributor on any active roadmap project. Excludes Directors, Managers, Designers, Data Scientists/Engineers, Interns/Apprentices, and PCB SLT + Hailey/Sofia/Anita.',
    'roster_size': data['roster_size'],
    'active_projects_scanned': data['active_projects_scanned'],
    'total_before_role_filter': len(data['unassigned']),
    'dropped_by_role_filter': len(dropped),
    'total_after_role_filter': len(kept),
    'by_team_counts': {team: len(people) for team, people in by_team.items()},
    'unassigned': ordered,
}

OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False))

print(f'Total before filter: {len(data["unassigned"])}')
print(f'Dropped by role filter: {len(dropped)}')
print(f'Total after filter: {len(kept)}')
print()
print('By team (after filter):')
for team in TEAM_ORDER:
    if team in by_team:
        print(f'  {team}: {len(by_team[team])}')
print()
print(f'Written to {OUT}')
