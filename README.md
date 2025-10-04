# Slack Complete Export & Markdown Transcript Toolkit

Export every accessible message from a Slack workspace (channels, private channels if you're a [00:55:33] Bob: Hi Alice
```ber, multi‑party DMs, one‑to‑one DMs — including those not currently visible in your sidebar) and optionally convert the resulting JSON into clean, date‑grouped Markdown transcripts.

---
## ✨ Features
- Full historical export of: public channels, private channels (you are in), group DMs (mpim), direct messages (im)
- Attempts to discover "hidden" historical DMs by probing users you’ve messaged
- Robust retry & backoff handling for transient network failures and rate limits
- Skips gracefully over problematic conversations and continues
- Produces a structured `exports/` directory with a JSON file per conversation
- Summary file `exports/export_summary.json`
- Optional transcript generation to `markdown/` with human‑readable logs grouped by date

---
## 🗂 Directory Layout (After Running Both Steps)
```
exports/
  channels/   <channel>.json
  ims/        <display_name>_dm.json
  groups/     mpdm-*.json
  export_summary.json
markdown/
  channels/   <channel>.md
  ims/        <display_name>_dm.md
  groups/     mpdm-*.md
```

---
## 🚀 Quick Start (TL;DR)
```bash
# 1. Clone this repository
git clone <repository-url>
cd slackex

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your token (recommended via .env)
cp .env.example .env
# Edit .env and replace 'xoxp-your-token-here' with your actual token

# 4. Run the exporter
python slack_export.py   # confirm with 'y'

# 5. (Optional) Convert JSON to markdown
python generate_md.py
```

---
## 1. Create a Slack App & Get a User Token
1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Name it something like: `PersonalExport` and pick your workspace
3. In the sidebar: OAuth & Permissions → User Token Scopes → Add:
   - `channels:history`
   - `channels:read`
   - `groups:history`
   - `groups:read`
   - `im:history`
   - `im:read`
   - `mpim:history`
   - `mpim:read`
   - `users:read`
4. Click “Install to Workspace” → Authorize
5. Copy the **User OAuth Token** (`xoxp-...`) — keep it secret.

(You can revoke the token or delete the app after exporting.)

---
## 2. Environment Setup
Ensure Python 3.9+ is installed.

Clone this repository and install dependencies:
```bash
git clone <repository-url>
cd slackex
pip install -r requirements.txt
```

Create a `.env` file from the example:
```bash
cp .env.example .env
```
Then edit `.env` and replace `xoxp-your-token-here` with your actual Slack token.

If you skip `.env`, the script will prompt for the token interactively.

### VS Code Workflow (Recommended)
1. Open the cloned folder in VS Code: `code slackex` (or File → Open Folder)
2. Install the Python extension if not already installed
3. VS Code will likely prompt to create a virtual environment - accept this
4. Open the integrated terminal (Terminal → New Terminal)
5. Install dependencies: `pip install -r requirements.txt`
6. Copy `.env.example` to `.env` and add your Slack token
7. Run scripts directly from the terminal or use the Python extension's run buttons

---
## 3. Run the Exporter
The primary script is `slack_export.py`.

```bash
python slack_export.py
```
You’ll see a confirmation screen summarizing what will be exported. Type `y` to proceed.

Progress example:
```
📥 Exporting channels (12/132): general
      Batch 1 (cursor: None)
      Processed 100 messages (total: 100)
      Processed 73 messages (total: 173)
    ✓ Found 173 total messages in 2 batches
```
A final summary appears when complete.

> You can re‑run the script; it will re-export and overwrite existing JSON files.

---
## 4. Output Structure & JSON Schema (Simplified)
Each conversation JSON contains:
```jsonc
{
  "conversation_info": {
    "id": "C123...",
    "name": "general",
    "type": "public_channel" | "private_channel" | "im" | "mpim",
    "is_archived": false,
    "is_private": false,
    // For DMs:
    "user_id": "U123...",
    "user_name": "alice"
  },
  "messages": [
    {
      "timestamp": "1744616613.903849",   // original Slack ts
      "datetime": "2025-04-14T13:13:33.903849",
      "user": "Display Name",
      "user_id": "U123...",
      "text": "Message text",
      "type": "message",
      "subtype": null,
      // Optional keys: thread_ts, reply_count, files[], reactions[]
    }
  ],
  "export_date": "2025-10-04T12:55:26.227171",
  "message_count": 42
}
```

---
## 5. (Optional) Generate Markdown Transcripts
If you want human‑readable archives:
```bash
python generate_md.py
```
Options:
```bash
python generate_md.py \
  --exports-dir exports \
  --output-dir markdown \
  --limit 5
```
Markdown format:
```
# Slack Conversation: general
*Export Source:* `exports/channels/general.json`  *Conversation Type:* public_channel  *Message Count:* 173  *Generated:* 2025-10-04T07:31:59 UTC
---
## 2025-04-19 (Saturday)
[09:55:00] Alice: Hello
[09:55:33] Bob: Hi Alice
```

---
## 6. Troubleshooting
| Problem | Cause / Fix |
|---------|-------------|
| `ModuleNotFoundError: slack_sdk` | Install dependencies: `pip install -r requirements.txt` |
| `invalid_auth` / `not_authed` | Token incorrect, missing, or revoked; confirm scopes + reinstall app |
| Slow / stops | Large workspace; script applies backoff. Let it run. Re-run if interrupted. |
| Network errors | Automatic retry with exponential backoff. Persistent issues: check connectivity / VPN. |
| Missing DMs | Some users never had a DM channel; script probes but cannot force history if none exists. |
| Rate limited | Handled automatically (`Retry-After`); just wait. |

---
## 7. Safety, Privacy, and Compliance
- This exports only conversations your user can access.
- Treat the JSON & markdown as sensitive data (contains potentially private info).
- Store results securely and delete when no longer needed.
- Revoke/delete the Slack app once the export is done if no longer required.

---
## 8. Extending / Custom Ideas
| Enhancement | Direction |
|-------------|-----------|
| Timezone conversion in markdown | Add `--tz <Zone>` and use `zoneinfo` (Python 3.9+) |
| Thread visualization | Indent thread replies or group under parent message |
| Reaction summaries | Append ` (👍 x3, ✅ x2)` after lines |
| Single combined log | Aggregate per channel or user across dates |
| HTML export | Convert markdown to HTML via a static site generator |

---
## 9. FAQ
**Q: Can admins detect this?**  
A: It uses official API calls within scope limits; normal workspace audit logs may show app installation and API usage.

**Q: Does it export files or attachments?**  
A: Only metadata (name, type, URL). It does not download file binaries.

**Q: Can I resume a partial export?**  
A: Yes—re-running simply re-fetches; you could adapt the code to skip JSONs that already exist if needed.

**Q: Are deleted users included?**  
A: The exporter skips deleted users for new DM discovery but will retain messages already present in channels.

---
## 10. Minimal Command Reference
```bash
# Clone repository
git clone <repository-url>
cd slackex

# Install deps
pip install -r requirements.txt

# Run export (uses .env if present)
python slack_export.py

# Generate markdown transcripts
python generate_md.py

# Limit markdown generation to first N conversations
python generate_md.py --limit 10
```

---
## 11. File Overview
| File | Purpose |
|------|---------|
| `slack_export.py` | Main robust exporter script |
| `generate_md.py` | JSON → Markdown transcript generator |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |
| `.gitignore` | Files/folders to exclude from git |
| `exports/export_summary.json` | Post‑run summary counts |

---
## 12. Deprecation Note
A future Python update will remove `datetime.utcnow()`; you may replace occurrences with:
```python
from datetime import datetime, UTC
now = datetime.now(UTC)  # timezone-aware
```
(This change is cosmetic for now.)

---
## ✅ Completion
You now have a repeatable, scriptable path to extract and preserve your Slack message history plus optional clean transcripts.

If you need enhancements or an HTML search interface layered on the JSON/markdown, feel free to extend or ask.
