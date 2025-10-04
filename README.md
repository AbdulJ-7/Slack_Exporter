# Slack Complete Export & Markdown Transcript Toolkit

Export every accessible message from a Slack workspace (channels, private channels if you're a member, multi‑party DMs, one‑to‑one DMs — including those not currently visible in your sidebar) and optionally convert the resulting JSON into clean, date‑grouped Markdown transcripts.

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
  channels/
    <channel>.json
  ims/
    <display_name>_dm.json
  groups/
    mpdm-*.json
  export_summary.json
markdown/
  channels/
    <channel>.md
  ims/
    <display_name>_dm.md
  groups/
    mpdm-*.md
```

---
## 1. Create a Slack App & Get a User Token
1. Go to https://api.slack.com/apps → Create New App → From scratch
2. Name it something like: `PersonalExport` and pick your workspace
3. In the sidebar: OAuth & Permissions → Scroll down to User Token Scopes → Add:
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
## 2. VS Code Setup & Workflow (Recommended)

### Prerequisites
- Python 3.9+ installed
- VS Code installed
- Git installed

### Setup Steps

#### 1. Open VS Code & Clone Repository
1. Open VS Code
2. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac) to open the Command Palette
3. Type `Git: Clone` and select it
4. Enter the repository URL: `https://github.com/AbdulJ-7/Slack_Exporter.git`
5. Select a folder on your computer to save the project
6. When prompted, click "Open" to open the cloned repository

#### 2. VS Code Setup
1. Install the **Python extension** if prompted (or from Extensions marketplace)
2. VS Code may prompt to create a virtual environment - **accept this recommendation**
3. Open the **integrated terminal** by clicking Terminal → New Terminal or pressing `` Ctrl+` `` (backtick)

#### 3. Install Dependencies
**In VS Code terminal:**
```bash
pip install -r requirements.txt
```

#### 4. Configure Environment
1. In VS Code's Explorer panel (left sidebar), find `.env.example`
2. Right-click on `.env.example` and select "Copy"
3. Right-click in the same folder and select "Paste"
4. When prompted, rename the file to `.env`
5. Double-click on the new `.env` file to open it
6. Replace `xoxp-your-token-here` with your actual Slack token from Step 1
7. Save the file (`Ctrl+S` or `Cmd+S`)

#### 5. Run Scripts
**Option A: Using VS Code's Run Button** (easiest for beginners)
1. Open `slack_export.py` by clicking on it in the Explorer panel
2. Click the ▶️ play button in the top-right corner of the VS Code window
3. After the export completes, open `generate_md.py`
4. Click the ▶️ play button again to generate markdown files

**Option B: Using VS Code terminal**
1. Make sure the terminal is open at the bottom of VS Code (if not, press `` Ctrl+` ``)
2. Type the following commands:
   ```bash
   python slack_export.py
   python generate_md.py
   ```

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
## 10. Command Reference
```bash
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
