# PCB Roadmap Site

A dashboard for tracking Payments and Cross Border (PCB) portfolio projects, timelines, and slip insights.

**Live Site:** https://pcb-roadmap.quick.shopify.io  
**GitHub:** https://github.com/haileyvezza/pcb-roadmap

---

## Project Structure

```
pcb-roadmap/
├── index.html          # All Projects - main table view with filters
├── timeline.html       # Timeline - Gantt chart view
├── themes.html         # By Theme - projects grouped by PCB Theme
├── slip.html           # Slip Insights - timeline changes analysis
├── data/
│   ├── projects.json   # Project data (from Google Sheet)
│   └── slip.csv        # Timeline changes (from Vault export)
└── README.md           # This file
```

---

## Data Sources

### 1. Projects Data (`data/projects.json`)

**Source:** [PCB Stack Ranked 2026 H1 Priorities](https://docs.google.com/spreadsheets/d/17xd1aWdtf33kUk3giF5WyC4dJpbClOjPGh2cVMYiuvI)

Pulls from these tabs:
- Money Movement and Expansion
- Payments Platform & Risk
- Cross Border
- Payment Merchant Experience
- Shop Wallet

**Columns used:**
- PCB Theme, Rank, Priority, PCB Big Rock, Project, Description
- Team, Sub Team, Champion
- Starts, Shipping, Status
- Editions, Needs UX, Need ToS/Merchant Comms
- Eng Count, Duration, Dependencies, Partner Dependency

**To refresh:** Use Cursor with Google Workspace MCP to re-read the spreadsheet and regenerate `projects.json`.

### 2. Slip Data (`data/slip.csv`)

**Source:** Vault Timeline Changes export

Download from Vault:
1. Go to Vault → Reports → Timeline Changes
2. Filter to "Payments & Cross Border"
3. Export CSV
4. Replace `data/slip.csv`

**Columns:**
- Team, Project, Phase, Milestone
- Old Date, New Date, Days Changed
- Reason, Champion

---

## Pages

### All Projects (`index.html`)
- Filterable table of all PCB projects
- Filters: Team, Status, Priority, Sub Team, Editions, ToS/Comms, Partner Dependency, PCB Big Rock
- Search across all fields
- Click column headers to sort

### Timeline (`timeline.html`)
- Gantt-style timeline view
- Group by Team or Theme
- Visual representation of project start → ship dates

### By Theme (`themes.html`)
- Projects grouped by PCB Theme
- Expandable/collapsible sections

### Slip (`slip.html`)
- Executive insights: What's Working, What's Not, Where to Apply Pressure
- Summary cards: Total changes, Avg GA slip
- Detailed table of all timeline changes
- Collapsible cause breakdown analysis

---

## Deployment

The site is hosted on Shopify Quick Sites.

**To deploy updates:**
```bash
cd /Users/haileyvezza/pcb-roadmap
yes | quick deploy /Users/haileyvezza/pcb-roadmap pcb-roadmap
```

The site will be live at: https://pcb-roadmap.quick.shopify.io

---

## Making Changes

### Update project data
1. Open Cursor with Google Workspace MCP enabled
2. Ask Cursor to read from the spreadsheet and update `data/projects.json`
3. Deploy

### Update slip data
1. Download new CSV from Vault (Timeline Changes report)
2. Save as `data/slip.csv`
3. Deploy

### Edit executive insights (slip.html)
The insights are hardcoded in `slip.html` in the `<div class="executive-insights">` section. Edit directly:
- **What's Working:** `.exec-insight.working`
- **What's Not:** `.exec-insight.not-working`
- **Where to Apply Pressure:** `.exec-insight.pressure`

### Add new filters
In `index.html`:
1. Add a `<select>` element in `#filter-bar`
2. Update `parseProjects()` to extract the field
3. Update `getFiltered()` to apply the filter
4. Update `buildFilterOptions()` to populate dropdown

### Styling
All CSS is inline in each HTML file within `<style>` tags. Key variables:
```css
:root {
  --bg-primary: #f6f6f7;
  --bg-card: #ffffff;
  --accent-green: #0088FF;
  --accent-red: #ef4444;
  /* ... see full list in any HTML file */
}
```

Dark mode is automatic via `[data-theme="dark"]` selectors.

---

## Tech Stack

- **Pure HTML/CSS/JS** - No build tools or frameworks
- **Static JSON/CSV** - Data files loaded via fetch()
- **Quick Sites** - Shopify internal hosting
- **GitHub** - Version control

---

## Common Tasks

### Refresh all data and redeploy
```bash
# 1. Update projects.json via Cursor + Google Workspace MCP
# 2. Download new slip.csv from Vault
# 3. Deploy
cd /Users/haileyvezza/pcb-roadmap
yes | quick deploy . pcb-roadmap
```

### Push changes to GitHub
```bash
cd /Users/haileyvezza/pcb-roadmap
git add .
git commit -m "Description of changes"
git push
```

### Test locally
```bash
cd /Users/haileyvezza/pcb-roadmap
python3 -m http.server 8000
# Open http://localhost:8000
```

---

## Future Enhancements (Pending)

1. **Clickable Vault links** - Make project names link to their Vault pages (requires Vault URL column in spreadsheet or API access)
2. **Missions page** - Group by PCB Theme with Vault project links (waiting on spreadsheet update)
3. **Auto-refresh** - Connect directly to Google Sheets API for live data

---

## Contact

Built by Cursor AI for Hailey Vezza, PCB Product Operations.
