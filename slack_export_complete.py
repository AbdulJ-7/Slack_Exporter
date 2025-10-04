import os
import json
import time
import requests
from datetime import datetime
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import http.client
from urllib.error import URLError
import socket
from dotenv import load_dotenv
import urllib.parse

load_dotenv()

class SlackCompleteExporter:
    def __init__(self, token):
        self.client = WebClient(token=token)
        self.token = token
        self.base_dir = Path("exports")
        self.users_cache = {}
        self.files_downloaded = set()
        self.download_stats = {
            'attempted': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
    def setup_directories(self):
        """Create the export directory structure"""
        directories = [
            self.base_dir / "channels",
            self.base_dir / "ims", 
            self.base_dir / "groups",
            self.base_dir / "files" / "uploaded_docs",
            self.base_dir / "files" / "images", 
            self.base_dir / "files" / "videos",
            self.base_dir / "files" / "audio",
            self.base_dir / "files" / "other"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def get_users(self):
        """Get all users to resolve user IDs to names"""
        try:
            cursor = None
            while True:
                response = self.robust_api_call('users_list', cursor=cursor, limit=200)
                
                for user in response['members']:
                    self.users_cache[user['id']] = {
                        'name': user.get('name', 'unknown'),
                        'real_name': user.get('real_name', ''),
                        'display_name': user.get('profile', {}).get('display_name', ''),
                        'deleted': user.get('deleted', False),
                        'is_bot': user.get('is_bot', False)
                    }
                
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
                    
            print(f"✓ Loaded {len(self.users_cache)} users")
        except Exception as e:
            print(f"Error fetching users: {e}")
            
    def resolve_user_name(self, user_id):
        """Convert user ID to readable name"""
        if user_id in self.users_cache:
            user = self.users_cache[user_id]
            return user.get('display_name') or user.get('real_name') or user.get('name')
        return user_id

    def robust_api_call(self, api_method, max_retries=5, **kwargs):
        """Make API calls with retry logic for network errors"""
        for attempt in range(max_retries):
            try:
                if api_method == 'conversations_history':
                    return self.client.conversations_history(**kwargs)
                elif api_method == 'conversations_list':
                    return self.client.conversations_list(**kwargs)
                elif api_method == 'conversations_open':
                    return self.client.conversations_open(**kwargs)
                elif api_method == 'users_list':
                    return self.client.users_list(**kwargs)
                    
            except (http.client.IncompleteRead, URLError, socket.error, ConnectionError) as e:
                wait_time = (2 ** attempt) + 1  # Exponential backoff
                print(f"    Network error (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"    Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
                
            except SlackApiError as e:
                if e.response['error'] == 'rate_limited':
                    retry_after = int(e.response.get('headers', {}).get('Retry-After', 60))
                    print(f"    Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue
                else:
                    # Other Slack API errors shouldn't be retried
                    raise e
                    
        # If we get here, all retries failed
        raise Exception(f"Failed to complete {api_method} after {max_retries} attempts")

    def robust_file_download(self, url, max_retries=3):
        """Download file with retry logic"""
        headers = {
            'Authorization': f'Bearer {self.token}',
            'User-Agent': 'SlackExporter/2.0'
        }
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, stream=True, timeout=30)
                if response.status_code == 200:
                    return response
                elif response.status_code == 404:
                    return None  # File not found, don't retry
                else:
                    print(f"      HTTP {response.status_code} (attempt {attempt + 1})")
                    
            except (requests.exceptions.RequestException, socket.error) as e:
                wait_time = (2 ** attempt) + 1
                print(f"      Download error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    print(f"      Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                continue
                
        return None

    def download_file(self, file_info, conversation_name="unknown"):
        """Download a single file with robust error handling"""
        self.download_stats['attempted'] += 1
        
        try:
            file_url = file_info.get('url_private')
            if not file_url:
                self.download_stats['skipped'] += 1
                return None
                
            file_id = file_info.get('id', 'unknown')
            if file_id in self.files_downloaded:
                self.download_stats['skipped'] += 1
                return f"files/already_downloaded/{file_info.get('name', 'unknown')}"
            
            # Get file response
            response = self.robust_file_download(file_url)
            if not response:
                self.download_stats['failed'] += 1
                return None
            
            # Determine file category and create safe filename
            filename = file_info.get('name', f"file_{file_id}")
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
            if not filename:
                filename = f"file_{file_id}"
            
            # Categorize files
            filetype = file_info.get('filetype', '').lower()
            mimetype = file_info.get('mimetype', '').lower()
            
            if filetype in ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'xls', 'xlsx', 'ppt', 'pptx'] or 'document' in mimetype:
                category = 'uploaded_docs'
            elif filetype in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp'] or 'image' in mimetype:
                category = 'images'
            elif filetype in ['mp4', 'mov', 'avi', 'mkv', 'webm'] or 'video' in mimetype:
                category = 'videos'
            elif filetype in ['mp3', 'wav', 'flac', 'aac', 'm4a'] or 'audio' in mimetype:
                category = 'audio'
            else:
                category = 'other'
            
            # Create subdirectory for conversation
            safe_conv_name = "".join(c for c in conversation_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            if not safe_conv_name:
                safe_conv_name = "unknown"
                
            file_dir = self.base_dir / "files" / category / safe_conv_name
            file_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = file_dir / filename
            
            # Handle duplicate filenames
            counter = 1
            original_path = file_path
            while file_path.exists():
                name_parts = original_path.stem, counter, original_path.suffix
                file_path = original_path.parent / f"{name_parts[0]}_{name_parts[1]}{name_parts[2]}"
                counter += 1
            
            # Download and save file
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            self.files_downloaded.add(file_id)
            relative_path = file_path.relative_to(self.base_dir)
            
            # Print progress every 10 files
            if self.download_stats['successful'] % 10 == 0:
                print(f"      Downloaded: {filename} -> {relative_path}")
            
            self.download_stats['successful'] += 1
            return str(relative_path)
            
        except Exception as e:
            print(f"      Error downloading file {file_info.get('name', 'unknown')}: {e}")
            self.download_stats['failed'] += 1
            return None

    def get_all_messages(self, channel_id, channel_name):
        """Get ALL message history for a conversation with file download"""
        all_messages = []
        cursor = None
        batch_count = 0
        
        try:
            while True:
                batch_count += 1
                print(f"      Batch {batch_count} (cursor: {'None' if not cursor else cursor[:10]+'...'})")
                
                response = self.robust_api_call(
                    'conversations_history',
                    channel=channel_id,
                    cursor=cursor,
                    limit=100,
                    inclusive=True
                )
                
                messages = response.get('messages', [])
                
                if not messages:
                    print(f"      No messages in batch {batch_count}")
                    break
                
                # Process messages
                for msg in messages:
                    processed_msg = {
                        'timestamp': msg.get('ts'),
                        'datetime': datetime.fromtimestamp(float(msg.get('ts', 0))).isoformat(),
                        'user': self.resolve_user_name(msg.get('user', 'unknown')),
                        'user_id': msg.get('user'),
                        'text': msg.get('text', ''),
                        'type': msg.get('type'),
                        'subtype': msg.get('subtype')
                    }
                    
                    # Handle thread information
                    if 'thread_ts' in msg:
                        processed_msg['thread_ts'] = msg['thread_ts']
                        processed_msg['reply_count'] = msg.get('reply_count', 0)
                        processed_msg['is_thread_parent'] = msg.get('ts') == msg.get('thread_ts')
                        
                    # Handle files and download them
                    if 'files' in msg:
                        processed_msg['files'] = []
                        files_in_message = len(msg['files'])
                        
                        if files_in_message > 0:
                            print(f"      Found {files_in_message} file(s) in message from {processed_msg['user']}")
                        
                        for file_info in msg['files']:
                            file_data = {
                                'id': file_info.get('id'),
                                'name': file_info.get('name'),
                                'title': file_info.get('title'),
                                'filetype': file_info.get('filetype'),
                                'size': file_info.get('size'),
                                'mimetype': file_info.get('mimetype'),
                                'url': file_info.get('url_private')
                            }
                            
                            # Download the file
                            local_path = self.download_file(file_info, channel_name)
                            if local_path:
                                file_data['local_path'] = local_path
                                file_data['downloaded'] = True
                            else:
                                file_data['downloaded'] = False
                                
                            processed_msg['files'].append(file_data)
                    
                    # Handle reactions
                    if 'reactions' in msg:
                        processed_msg['reactions'] = msg['reactions']
                    
                    all_messages.append(processed_msg)
                
                print(f"      Processed {len(messages)} messages (total: {len(all_messages)})")
                
                # Check for more messages
                if not response.get('has_more'):
                    break
                    
                cursor = response.get('response_metadata', {}).get('next_cursor')
                time.sleep(1)  # Rate limiting between batches
                
            print(f"    ✓ Found {len(all_messages)} total messages in {batch_count} batches")
            
        except Exception as e:
            print(f"    ⚠️  Error fetching history for {channel_name}: {e}")
            print(f"    ⚠️  Partial export: got {len(all_messages)} messages before error")
            
        return all_messages

    def get_all_conversations(self):
        """Get ALL conversations (channels, groups, DMs) that the user has access to"""
        all_conversations = {
            'channels': [],
            'groups': [],
            'ims': []
        }
        
        conversation_types = [
            ("public_channel", "channels"),
            ("private_channel", "channels"), 
            ("mpim", "groups"),
            ("im", "ims")
        ]
        
        for conv_type, category in conversation_types:
            print(f"🔍 Finding all {conv_type} conversations...")
            cursor = None
            
            try:
                while True:
                    response = self.robust_api_call(
                        'conversations_list',
                        types=conv_type,
                        cursor=cursor,
                        limit=200,
                        exclude_archived=False
                    )
                    
                    conversations = response.get('channels', [])
                    
                    for conv in conversations:
                        conv_info = {
                            'id': conv['id'],
                            'name': conv.get('name', f"{conv_type}_{conv['id']}"),
                            'type': conv_type,
                            'is_archived': conv.get('is_archived', False),
                            'is_private': conv.get('is_private', False)
                        }
                        
                        if conv_type == 'im':
                            user_id = conv.get('user')
                            if user_id and user_id in self.users_cache:
                                user_info = self.users_cache[user_id]
                                conv_info['user_id'] = user_id
                                conv_info['user_name'] = self.resolve_user_name(user_id)
                                conv_info['name'] = conv_info['user_name']
                                
                                if user_info.get('deleted', False):
                                    print(f"    Skipping deleted user: {conv_info['user_name']}")
                                    continue
                        
                        all_conversations[category].append(conv_info)
                    
                    cursor = response.get('response_metadata', {}).get('next_cursor')
                    if not cursor:
                        break
                        
                print(f"  ✓ Found {len(all_conversations[category])} {conv_type} conversations")
                
            except Exception as e:
                print(f"  ⚠️  Error fetching {conv_type}: {e}")
        
        return all_conversations

    def find_additional_dms(self):
        """Try to find DMs with users who might not have open conversations"""
        print("🔍 Looking for additional DM conversations...")
        additional_dms = []
        
        try:
            response = self.robust_api_call('conversations_list', types="im", limit=1000)
            existing_dm_users = set()
            for im in response.get('channels', []):
                if 'user' in im:
                    existing_dm_users.add(im['user'])
        except Exception:
            existing_dm_users = set()
        
        user_count = 0
        for user_id, user_info in self.users_cache.items():
            if user_id in existing_dm_users:
                continue
                
            if user_info.get('is_bot', False) or user_info.get('deleted', False):
                continue
                
            user_count += 1
            if user_count % 10 == 0:
                print(f"    Checked {user_count} users...")
                
            try:
                response = self.robust_api_call('conversations_open', users=[user_id])
                conversation_id = response['channel']['id']
                
                history_check = self.robust_api_call(
                    'conversations_history',
                    channel=conversation_id,
                    limit=1
                )
                
                if history_check.get('messages'):
                    additional_dms.append({
                        'id': conversation_id,
                        'user_id': user_id,
                        'user_name': self.resolve_user_name(user_id),
                        'name': self.resolve_user_name(user_id),
                        'type': 'im',
                        'is_archived': False,
                        'is_private': True
                    })
                    print(f"    Found DM with: {self.resolve_user_name(user_id)}")
                    
                time.sleep(0.5)
                
            except Exception as e:
                if "cannot_dm_bot" not in str(e).lower() and "user_not_found" not in str(e).lower():
                    if user_count <= 5:
                        print(f"    Couldn't check {self.resolve_user_name(user_id)}: {e}")
                continue
        
        print(f"  ✓ Found {len(additional_dms)} additional DM conversations")
        return additional_dms

    def export_conversations(self, conversations, export_type):
        """Export a list of conversations with file downloads"""
        export_dir = self.base_dir / export_type
        
        for i, conv in enumerate(conversations):
            conv_name = conv['name']
            conv_id = conv['id']
            
            print(f"📥 Exporting {export_type} ({i+1}/{len(conversations)}): {conv_name}")
            
            if conv.get('is_archived'):
                print(f"    (archived conversation)")
            
            try:
                # Reset download stats for this conversation
                old_stats = self.download_stats.copy()
                
                messages = self.get_all_messages(conv_id, conv_name)
                
                if not messages:
                    print(f"    No messages found, skipping")
                    continue
                
                # Calculate files downloaded for this conversation
                files_this_conv = self.download_stats['successful'] - old_stats['successful']
                if files_this_conv > 0:
                    print(f"    📎 Downloaded {files_this_conv} files from this conversation")
                
                # Prepare export data
                export_data = {
                    'conversation_info': conv,
                    'messages': messages,
                    'export_date': datetime.now().isoformat(),
                    'message_count': len(messages),
                    'files_downloaded_count': files_this_conv
                }
                
                # Create safe filename
                safe_name = "".join(c for c in conv_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                if not safe_name:
                    safe_name = f"{export_type}_{conv_id}"
                
                if export_type == "ims":
                    safe_name += "_dm"
                
                # Save JSON
                json_file = export_dir / f"{safe_name}.json"
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                
                print(f"    ✅ Exported {len(messages)} messages to {json_file.name}")
                
            except Exception as e:
                print(f"    ❌ Failed to export {conv_name}: {e}")
                print(f"    Continuing with next conversation...")
                continue

    def create_export_summary(self):
        """Create a comprehensive summary of the export"""
        summary = {
            'export_date': datetime.now().isoformat(),
            'total_conversations': 0,
            'total_messages': 0,
            'file_download_stats': self.download_stats.copy(),
            'breakdown': {}
        }
        
        for export_type in ['channels', 'ims', 'groups']:
            export_dir = self.base_dir / export_type
            if not export_dir.exists():
                continue
                
            json_files = list(export_dir.glob('*.json'))
            conversation_count = len(json_files)
            message_count = 0
            files_count = 0
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        message_count += data.get('message_count', 0)
                        files_count += data.get('files_downloaded_count', 0)
                except:
                    continue
            
            summary['breakdown'][export_type] = {
                'conversations': conversation_count,
                'messages': message_count,
                'files_downloaded': files_count
            }
            summary['total_conversations'] += conversation_count
            summary['total_messages'] += message_count
        
        # Count actual downloaded files
        files_dir = self.base_dir / "files"
        if files_dir.exists():
            all_files = list(files_dir.rglob('*'))
            actual_file_count = len([f for f in all_files if f.is_file()])
            summary['actual_files_on_disk'] = actual_file_count
        
        # Save summary
        with open(self.base_dir / 'export_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        return summary

    def run_export(self):
        """Run the complete export with file downloads"""
        print("🚀 Starting comprehensive Slack export with file downloads...")
        
        self.setup_directories()
        print("✓ Created export directories")
        
        self.get_users()
        
        all_conversations = self.get_all_conversations()
        additional_dms = self.find_additional_dms()
        all_conversations['ims'].extend(additional_dms)
        
        print(f"\n📊 Found conversations:")
        print(f"  Channels: {len(all_conversations['channels'])}")
        print(f"  Direct Messages: {len(all_conversations['ims'])}")
        print(f"  Group Messages: {len(all_conversations['groups'])}")
        
        print(f"\n🔄 Starting exports with file downloads...")
        
        if all_conversations['channels']:
            self.export_conversations(all_conversations['channels'], 'channels')
            
        if all_conversations['ims']:
            self.export_conversations(all_conversations['ims'], 'ims')
            
        if all_conversations['groups']:
            self.export_conversations(all_conversations['groups'], 'groups')
        
        summary = self.create_export_summary()
        
        print(f"\n🎉 Export completed!")
        print(f"📈 Summary:")
        print(f"  Total Conversations: {summary['total_conversations']}")
        print(f"  Total Messages: {summary['total_messages']}")
        print(f"  📎 File Downloads:")
        print(f"    Attempted: {self.download_stats['attempted']}")
        print(f"    Successful: {self.download_stats['successful']}")
        print(f"    Failed: {self.download_stats['failed']}")
        print(f"    Skipped: {self.download_stats['skipped']}")
        print(f"  📁 Files organized in: {self.base_dir}/files/")
        print(f"\n📊 Detailed breakdown:")
        for export_type, data in summary['breakdown'].items():
            print(f"  {export_type.capitalize()}: {data['conversations']} conversations, {data['messages']} messages, {data.get('files_downloaded', 0)} files")

if __name__ == "__main__":
    SLACK_TOKEN = os.getenv('SLACK_TOKEN') or input("Enter your Slack token: ").strip()
    if not SLACK_TOKEN:
        print("❌ Please provide a valid Slack token")
        exit(1)
        
    print("📋 This will export ALL available messages AND download files from:")
    print("  • All channels (public & private)")
    print("  • All direct messages (including hidden ones)")
    print("  • All group messages")
    print("  • Including archived conversations")
    print("\n📎 File downloads will be organized by type and conversation")
    print("⚠️  This may take considerable time depending on file count and sizes")
    
    confirm = input("\nContinue? (y/N): ").strip().lower()
    
    if confirm != 'y':
        print("Export cancelled.")
        exit(0)
        
    exporter = SlackCompleteExporter(SLACK_TOKEN)
    exporter.run_export()