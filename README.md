# Slack Complete Export & Transcript Tool

**Export all your Slack messages and files before your account gets deactivated or you lose access.**

This tool helps you:
- Download ALL your Slack conversations (public channels, private channels, group DMs, direct messages)
- Save everything in organized JSON files
- Optionally download all file attachments
- Create human-readable markdown transcripts (optional)

## 📋 Simple Step-by-Step Guide

### Step 1: Set Up Requirements

You'll need to install three things (if you don't have them already):

1. **Install VS Code**: Download and install from [code.visualstudio.com](https://code.visualstudio.com/)
2. **Install Python**: Download and install from [python.org/downloads](https://www.python.org/downloads/) (version 3.9 or higher)
   - During installation, be sure to check the box that says "Add Python to PATH"
3. **Install Git**: Download and install from [git-scm.com/downloads](https://git-scm.com/downloads)

### Step 2: Get Your Slack Token

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → Choose "From scratch"
3. Name it "PersonalExport" (or any name you like)
4. Select your Slack workspace and click "Create App"
5. In the left sidebar, click "OAuth & Permissions"
6. Scroll down to  **"User Token Scopes"** → "User Token Scopes"
7. Click "Add an OAuth Scope" and add each of these permissions:
   - `channels:history`
   - `channels:read`
   - `groups:history`
   - `groups:read`
   - `im:history`
   - `im:read`
   - `mpim:history`
   - `mpim:read`
   - `users:read`
   - `files:read` (only needed if you want to download file attachments)
8. Scroll back to the top and click "Install to Workspace"
9. Click "Allow" to authorize the app
10. Copy your token (it starts with `xoxp-`)



### Step 3: Download and Set Up the Tool (Copy & Paste Commands)

1. Open VS Code
2. Press <kbd>Ctrl+`</kbd> (backtick - the key above Tab) to open the terminal
3. Copy and paste this command to download the tool:
   ```
   git clone https://github.com/AbdulJ-7/Slack_Exporter.git && cd Slack_Exporter/slackex
   ```

4. Copy and paste this command to create the configuration file:
   ```
   code .env
   ```
   
5. In the editor that opens, paste the following and replace `YOUR_TOKEN_HERE` with your Slack token from Step 2:
   ```
   # Slack User OAuth Token (starts with xoxp-)
   SLACK_TOKEN=YOUR_TOKEN_HERE
   ```

6. Save the file by pressing <kbd>Ctrl+S</kbd> (or <kbd>Cmd+S</kbd> on Mac)

7. Copy and paste this command to install required packages:
   ```
   pip install -r requirements.txt
   ```

### Step 4: Export Your Slack Messages

**Option A: Messages Only (Faster)**

1. In the VS Code terminal, copy and paste this command:
   ```
   python slack_export_chats.py
   ```

2. Type `y` when prompted to confirm the export
3. Wait for the export to complete (this might take a while for large workspaces)
4. You'll see a summary when it's finished

**Option B: Complete Export with Files (Slower)**

⚠️ **NOTE: This option can take SIGNIFICANTLY longer** depending on the number and size of file attachments in your workspace and your internet speed. For workspaces with many large files, this could take several hours or even days.

1. In the VS Code terminal, copy and paste this command:
   ```
   python slack_export_complete.py
   ```

2. Type `y` when prompted to confirm the export
3. The script will download all messages and file attachments
4. Files will be saved to the `exports/files` directory

### Step 5: (Optional) Create Human-Readable Transcripts

If you want to read your messages in a more user-friendly format:

1. In the VS Code terminal, copy and paste this command:
   ```
   python generate_md.py
   ```

2. Wait for the process to complete
3. Your readable transcripts will be in the `markdown` folder

### Step 6: Find Your Exported Files

1. All your data is stored in the `Slack_Exporter` folder:
   - JSON files: `exports` folder
   - Readable transcripts: `markdown` folder (if you did Step 5)
   
2. Open these files using VS Code or any text editor

## 💡 Frequently Asked Questions

**Q: The terminal says "command not found" for Python**  
A: Try using `python3` instead of `python` in the commands above.

**Q: How long will this take?**  
A: For messages-only export (`slack_export_chats.py`), it depends on the size of your workspace - typically an hour or more for large workspaces with thousands of messages. For complete export with files (`slack_export_complete.py`), it can take significantly longer - potentially several hours or days if you have many large files.

**Q: What if the export stops or crashes?**  
A: Just run the command again - it will resume and continue.

**Q: Are my direct messages included?**  
A: Yes, even direct messages with users that are no longer in your sidebar.

**Q: Are file attachments downloaded?**  
A: Only if you use the `slack_export_complete.py` script. The regular `slack_export_chats.py` script only exports message text and file metadata (like URLs), but doesn't download the actual files.

**Q: Is this allowed by Slack?**  
A: Yes, you're using official Slack APIs with proper permissions to access your own data.

**Q: What if I get an error about invalid token?**  
A: Double-check that you copied the token correctly (it starts with `xoxp-`) and added all the required permissions.

## 🛠️ Troubleshooting Tips

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| `invalid_auth` error | Check your token in the `.env` file |
| Script seems stuck | Large workspaces take time - be patient |
| Complete export very slow | This is normal for large files - let it run |
| Download failures | Run the script again - it will retry failed downloads |
| `python` not found | Try using `python3` instead |

### Command Reference

```bash
# Messages-only export (faster)
python slack_export_chats.py

# Complete export with file attachments (slower)
python slack_export_complete.py

# Generate human-readable markdown transcripts
python generate_md.py
```

## 📄 What Your Transcripts Will Look Like

```
# Slack Conversation: general
*Export Source:* `exports/channels/general.json`  *Conversation Type:* public_channel  *Message Count:* 173

---
## 2025-04-19 (Saturday)
[09:55:00] Alice: Hello
[09:55:33] Bob: Hi Alice
```

## ⚠️ Important Privacy & Storage Notes

- This tool only exports conversations you have legitimate access to
- Store your exported data securely - it contains private conversations
- **For complete exports with files**: Make sure you have enough disk space! Large workspaces can require several GB of storage
- Consider deleting the Slack app you created after you're done exporting
- NEVER share your Slack token with anyone
- Downloaded files maintain the same access permissions they had in Slack