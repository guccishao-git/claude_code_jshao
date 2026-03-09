Query Jira tickets for Activision DATA projects (DSHD, DWDF, DS) using the Jira Cloud REST API and print a scannable terminal table.

## Step 1 — Load credentials

Run this bash command and capture the output:

```bash
if [ ! -f ~/.jira_config ]; then
  echo "MISSING"
else
  source ~/.jira_config
  echo "JIRA_URL=$JIRA_URL"
  echo "JIRA_EMAIL=$JIRA_EMAIL"
  echo "JIRA_TOKEN_SET=$([ -n "$JIRA_TOKEN" ] && echo yes || echo no)"
  echo "JIRA_PROJECT=$JIRA_PROJECT"
  echo "JIRA_PROJECTS=$JIRA_PROJECTS"
fi
```

If the file is missing or any variable is empty, print these setup instructions and stop:

```
⚠️  ~/.jira_config not found or incomplete.

Create it with the following content (never commit this file):

  JIRA_URL=https://yourcompany.atlassian.net
  JIRA_EMAIL=you@company.com
  JIRA_TOKEN=your_api_token
  JIRA_PROJECT=DATA

Get your API token at: https://id.atlassian.com/manage-profile/security/api-tokens
```

## Step 2 — Infer query mode from arguments (no interactive prompt)

Do NOT present a menu or wait for user input. Infer the query mode directly from the ARGUMENTS:

- If arguments mention "my tickets", "assigned to me", or no specific filter → **Mode 1** (my open tickets)
- If arguments mention a status (e.g. "in progress", "to do", "done") → **Mode 2**, use that status
- If arguments mention an epic key (e.g. "DSHD-100") → **Mode 3**, use that epic key
- If arguments mention a label → **Mode 4**, use that label

Also infer the project from arguments: if a specific project is mentioned (DSHD, DWDF, DS), use it; otherwise use all projects from `$JIRA_PROJECTS`.

## Step 3 — Build the JQL and call the API

Construct JQL based on mode:

| Mode | JQL template |
|------|-------------|
| 1 | `project = {PROJECT} AND assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC` |
| 2 | `project = {PROJECT} AND status = "{STATUS}" ORDER BY updated DESC` |
| 3 | `project = {PROJECT} AND "Epic Link" = "{EPIC_KEY}" ORDER BY updated DESC` |
| 4 | `project = {PROJECT} AND labels = "{LABEL}" ORDER BY updated DESC` |

Run the API call (this is Jira Server/Data Center — use Bearer token, NOT Basic auth):

```bash
source ~/.jira_config
JQL="<constructed JQL>"
curl -s \
  -H "Authorization: Bearer $JIRA_TOKEN" \
  -H "Content-Type: application/json" \
  "$JIRA_URL/rest/api/2/search?jql=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$JQL")&fields=summary,status,assignee,priority,labels&maxResults=50"
```

Note: Use `/rest/api/2/` (not `/rest/api/3/`) — this is Jira Server 9.x, not Jira Cloud.

**IMPORTANT**: Never print `$JIRA_TOKEN`, `$JIRA_EMAIL`, or the Authorization header value.

## Step 4 — Parse and display results

Always save curl output to `/tmp/jira_out.json`, write the parser to `/tmp/jira_parse.py`, then run it:

```bash
curl ... > /tmp/jira_out.json
```

```python
# /tmp/jira_parse.py — always use this exact table format
import json

GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
RESET  = "\033[0m"

def color_status(s):
    s = s.strip()
    if s == "Done":
        return f"{GREEN}{s:<22}{RESET}"
    elif s in ("In Progress", "In Review"):
        return f"{YELLOW}{s:<22}{RESET}"
    elif "Waiting" in s:
        return f"{CYAN}{s:<22}{RESET}"
    else:
        return f"{s:<22}"

data = json.load(open("/tmp/jira_out.json"))
issues = data.get("issues", [])
total = data.get("total", len(issues))

# Set these before running:
project_label = "DSHD / DWDF / DS"  # or specific project
mode_label = "My open tickets"       # e.g. "Status: In Progress", "Label: dbt"

print(f"\n📋 {project_label} — {mode_label} ({total} found)")
print("─" * 90)
print(f"{'KEY':<14} {'STATUS':<22} {'PRIORITY':<10} {'ASSIGNEE':<18} SUMMARY")
print("─" * 90)

if not issues:
    print("No tickets found for this query.")
else:
    for issue in issues:
        key = issue["key"]
        fields = issue["fields"]
        status = fields.get("status", {}).get("name", "Unknown")
        priority = (fields.get("priority") or {}).get("name", "—")
        assignee = ((fields.get("assignee") or {}).get("displayName") or "Unassigned")[:16]
        summary = (fields.get("summary") or "")[:55]
        print(f"{key:<14} {color_status(status):<22} {priority:<10} {assignee:<18} {summary}")

print("─" * 90)
print()
```

```bash
/opt/homebrew/bin/python3 /tmp/jira_parse.py
```

Always include **KEY, STATUS, PRIORITY, ASSIGNEE, SUMMARY** columns. Color-code status: green=Done, yellow=In Progress/In Review, cyan=Waiting.*

## Notes
- Never echo credentials to the terminal at any point
- Truncate summaries at 60 characters
- If `issues` is empty, print: `No tickets found for this query.`
- If curl fails (non-JSON response), print the raw output so the user can debug
