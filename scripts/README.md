# Weekly refresh scripts

## build_unassigned.py + filter_unassigned.py

Rebuild the "Unassigned People" list under `coverageGaps.unassignedPeople` in `data/weekly-commentary.json`.

Requires Vault MCP access (env vars for VAULT_TOKEN).

Usage:

    python3 scripts/build_unassigned.py     # writes /tmp/h2_migration/unassigned_people.json
    python3 scripts/filter_unassigned.py    # writes /tmp/h2_migration/unassigned_people_filtered.json

Then manually paste the by-team output into `data/weekly-commentary.json` under `coverageGaps.unassignedPeople`.

## Exclusion list

- PCB SLT: Rohit Mishra, Weiqing Tu, Sadia Latifi, Vishal Morde, Josh Kraut
- Personal exclusions: Hailey Vezza, Sofia Karabevic (also known as Karabasevic), Anita Tang

## Role filter

`filter_unassigned.py` drops these role patterns before showing: director, manager (engineering/data), engineering manager, development manager, designer, product data scientist, data scientist, data engineer, apprentice, intern, dev degree, writer, business analyst, product marketing, product lead, operations, expansion pack.

## Assignment definition

Someone is "assigned" if their name matches the champion, aimer, OR direct_contributors list on any active roadmap project (Phase != Done/Stopped/Backlog/Paused/empty).
