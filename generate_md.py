import os
import json
from pathlib import Path
from datetime import datetime, UTC
import argparse
import re

"""
Generate Markdown transcripts from Slack export JSON files produced by slack_export_4.py

Features:
- Processes channels, ims, and groups
- Outputs parallel directory structure under `markdown/`
- One markdown file per conversation JSON
- Groups messages by calendar date with a date heading (e.g., ## 2025-04-14 (Monday))
- Each message line format: [HH:MM:SS] Username: message text
- Escapes markdown special sequences minimally to avoid accidental formatting
- Preserves multi-line messages
- Optionally include thread markers (disabled by default)
"""

DATE_HEADER_FMT = "## {date} ({weekday})"
MSG_LINE_FMT = "[{time}] {user}: {text}"
TIME_FMT = "%H:%M:%S"

MD_ROOT = Path("markdown")
EXPORT_ROOT = Path("exports")
SUBDIRS = ["channels", "ims", "groups"]

MD_HEADER_TEMPLATE = """# Slack Conversation: {name}\n\n*Export Source:* `{source_json}`  \
*Conversation Type:* {conv_type}  \
*Message Count:* {message_count}  \
*Generated:* {generated_at} UTC\n\n---\n"""

# Basic markdown escaping (keep it light; we just neutralize leading '#' and accidental lists)
LEADING_MARKDOWN_PATTERN = re.compile(r"^(\s*)([-*+]|\d+\.)\s+")


def sanitize_text(text: str) -> str:
    if text is None:
        return ""
    # Normalize newlines
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    # Escape backticks by doubling (simple approach)
    text = text.replace('`', '\\`')
    lines = []
    for line in text.split('\n'):
        # Prevent accidental headings or lists
        if line.startswith('#'):
            line = '\\' + line
        if LEADING_MARKDOWN_PATTERN.match(line):
            line = line.replace('-', '\\-', 1)
        lines.append(line)
    return '\n'.join(lines).strip()


def load_json(path: Path):
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def format_message(msg: dict) -> tuple:
    """Return (date_str, formatted_line or None, original_ts)"""
    ts = msg.get('timestamp') or msg.get('ts')
    if not ts:
        return None, None, None
    try:
        dt = datetime.fromtimestamp(float(ts))
    except Exception:
        return None, None, None

    date_str = dt.strftime('%Y-%m-%d')
    time_str = dt.strftime(TIME_FMT)

    user = msg.get('user') or msg.get('user_name') or msg.get('user_id') or 'unknown'
    text = sanitize_text(msg.get('text', ''))

    if not text and not msg.get('files'):
        return date_str, None, ts  # Skip empty messages unless they reference files

    # Represent file placeholders if present
    if msg.get('files'):
        file_lines = []
        for f in msg['files']:
            name = f.get('name') or f.get('title') or 'file'
            file_lines.append(f"[file: {name}]")
        if text:
            text += "\n" + "\n".join(file_lines)
        else:
            text = "\n".join(file_lines)

    line = MSG_LINE_FMT.format(time=time_str, user=user, text=text)
    return date_str, line, ts


def process_conversation(json_path: Path, output_root: Path):
    data = load_json(json_path)
    conv_info = data.get('conversation_info', {})
    name = conv_info.get('name') or json_path.stem
    conv_type = conv_info.get('type', 'unknown')
    messages = data.get('messages', [])
    message_count = data.get('message_count', len(messages))

    # Prepare output directory
    rel_dir = json_path.parent.relative_to(EXPORT_ROOT)
    out_dir = output_root / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{json_path.stem}.md"

    # Group messages by date
    grouped = {}
    for msg in messages:
        date_key, line, ts = format_message(msg)
        if date_key is None or line is None:
            continue
        grouped.setdefault(date_key, []).append((ts, line))

    # Sort dates and within-date by timestamp
    sorted_dates = sorted(grouped.keys())

    parts = [
        MD_HEADER_TEMPLATE.format(
            name=name,
            source_json=str(json_path.relative_to(Path.cwd() if json_path.is_absolute() else Path('.'))),
            conv_type=conv_type,
            message_count=message_count,
            generated_at=datetime.now(UTC).isoformat(timespec='seconds')
        )
    ]

    for date in sorted_dates:
        weekday = datetime.strptime(date, '%Y-%m-%d').strftime('%A')
        parts.append(DATE_HEADER_FMT.format(date=date, weekday=weekday))
        # Sort lines by ts numeric
        day_lines = sorted(grouped[date], key=lambda x: float(x[0]))
        for _, line in day_lines:
            parts.append(line)
        parts.append("")  # blank line after each date

    content = "\n".join(parts).rstrip() + "\n"
    with out_file.open('w', encoding='utf-8') as f:
        f.write(content)

    return out_file, len(messages)


def discover_conversations(root: Path):
    for sub in SUBDIRS:
        p = root / sub
        if not p.exists():
            continue
        for json_file in p.glob('*.json'):
            yield json_file


def main():
    parser = argparse.ArgumentParser(description='Generate markdown transcripts from Slack export JSON.')
    parser.add_argument('--exports-dir', default=str(EXPORT_ROOT), help='Path to exports root directory (default: exports)')
    parser.add_argument('--output-dir', default=str(MD_ROOT), help='Path to output markdown root (default: markdown)')
    parser.add_argument('--limit', type=int, default=None, help='Only process first N conversations (debug)')
    args = parser.parse_args()

    export_root = Path(args.exports_dir)
    output_root = Path(args.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    conversations = list(discover_conversations(export_root))
    if args.limit:
        conversations = conversations[:args.limit]

    total = len(conversations)
    print(f"Found {total} conversations to process.")

    success = 0
    for idx, json_path in enumerate(conversations, start=1):
        try:
            out_file, count = process_conversation(json_path, output_root)
            print(f"[{idx}/{total}] ✓ {json_path.name} -> {out_file.relative_to(output_root)} ({count} msgs)")
            success += 1
        except Exception as e:
            print(f"[{idx}/{total}] ✗ Failed {json_path.name}: {e}")

    print(f"Done. {success}/{total} conversations converted.")


if __name__ == '__main__':
    main()
