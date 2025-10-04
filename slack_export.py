import os
import json
import time
from datetime import datetime
from pathlib import Path
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import http.client
from urllib.error import URLError
import socket
from dotenv import load_dotenv

load_dotenv()

class SlackMessageExporter:
    def __init__(self, token):
        self.client = WebClient(token=token)
        self.base_dir = Path("exports")
        self.users_cache = {}
        
    def setup_directories(self):
        """Create the export directory structure"""
        directories = [
            self.base_dir / "channels",
            self.base_dir / "ims",
            self.base_dir / "groups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def get_users(self):
        """Get all users to resolve user IDs to names"""
        try:
            cursor = None
            while True:
                response = self.client.users_list(cursor=cursor, limit=200)
                
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
        except SlackApiError as e:
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
                wait_time = (2 ** attempt) + 1  # Exponential backoff: 3, 5, 9, 17, 33 seconds
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

    def get_all_messages(self, channel_id, channel_name):
        """Get ALL message history for a conversation with robust error handling"""
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
                    limit=100,  # Reduced batch size to avoid large responses
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
                        
                    # Include file references (but don't download)
                    if 'files' in msg:
                        processed_msg['files'] = []
                        for file_info in msg['files']:
                            processed_msg['files'].append({
                                'name': file_info.get('name'),
                                'title': file_info.get('title'),
                                'filetype': file_info.get('filetype'),
                                'size': file_info.get('size'),
                                'url': file_info.get('url_private')
                            })
                    
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
            # Return what we have so far
            
        return all_messages

    def get_all_conversations(self):
        """Get ALL conversations (channels, groups, DMs) that the user has access to"""
        all_conversations = {
            'channels': [],
            'groups': [],
            'ims': []
        }
        
        # Get all conversation types
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
                        limit=200,  # Smaller batches
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
                        
                        # For DMs, get the user info
                        if conv_type == 'im':
                            user_id = conv.get('user')
                            if user_id and user_id in self.users_cache:
                                user_info = self.users_cache[user_id]
                                conv_info['user_id'] = user_id
                                conv_info['user_name'] = self.resolve_user_name(user_id)
                                conv_info['name'] = conv_info['user_name']
                                
                                # Skip deleted users and bots if you want
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
        
        # Get existing IM conversation user IDs
        try:
            response = self.robust_api_call('conversations_list', types="im", limit=1000)
            existing_dm_users = set()
            for im in response.get('channels', []):
                if 'user' in im:
                    existing_dm_users.add(im['user'])
        except Exception:
            existing_dm_users = set()
        
        # Try to open conversations with users we don't have DMs with
        user_count = 0
        for user_id, user_info in self.users_cache.items():
            if user_id in existing_dm_users:
                continue
                
            # Skip bots and deleted users
            if user_info.get('is_bot', False) or user_info.get('deleted', False):
                continue
                
            user_count += 1
            if user_count % 10 == 0:
                print(f"    Checked {user_count} users...")
                
            try:
                # Try to open conversation
                response = self.robust_api_call('conversations_open', users=[user_id])
                conversation_id = response['channel']['id']
                
                # Quick check if there are any messages
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
                    
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                # Expected for users you can't DM
                if "cannot_dm_bot" not in str(e).lower() and "user_not_found" not in str(e).lower():
                    if user_count <= 5:  # Only show first few errors
                        print(f"    Couldn't check {self.resolve_user_name(user_id)}: {e}")
                continue
        
        print(f"  ✓ Found {len(additional_dms)} additional DM conversations")
        return additional_dms

    def export_conversations(self, conversations, export_type):
        """Export a list of conversations with better error handling"""
        export_dir = self.base_dir / export_type
        
        for i, conv in enumerate(conversations):
            conv_name = conv['name']
            conv_id = conv['id']
            
            print(f"📥 Exporting {export_type} ({i+1}/{len(conversations)}): {conv_name}")
            
            if conv.get('is_archived'):
                print(f"    (archived conversation)")
            
            try:
                messages = self.get_all_messages(conv_id, conv_name)
                
                if not messages:
                    print(f"    No messages found, skipping")
                    continue
                
                # Prepare export data
                export_data = {
                    'conversation_info': conv,
                    'messages': messages,
                    'export_date': datetime.now().isoformat(),
                    'message_count': len(messages)
                }
                
                # Create safe filename
                safe_name = "".join(c for c in conv_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                if not safe_name:
                    safe_name = f"{export_type}_{conv_id}"
                
                # Add suffix for different types
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
        """Create a summary of what was exported"""
        summary = {
            'export_date': datetime.now().isoformat(),
            'total_conversations': 0,
            'total_messages': 0,
            'breakdown': {}
        }
        
        for export_type in ['channels', 'ims', 'groups']:
            export_dir = self.base_dir / export_type
            if not export_dir.exists():
                continue
                
            json_files = list(export_dir.glob('*.json'))
            conversation_count = len(json_files)
            message_count = 0
            
            # Count total messages
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        message_count += data.get('message_count', 0)
                except:
                    continue
            
            summary['breakdown'][export_type] = {
                'conversations': conversation_count,
                'messages': message_count
            }
            summary['total_conversations'] += conversation_count
            summary['total_messages'] += message_count
        
        # Save summary
        with open(self.base_dir / 'export_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        return summary

    def run_export(self):
        """Run the complete message export"""
        print("🚀 Starting comprehensive Slack message export...")
        
        self.setup_directories()
        print("✓ Created export directories")
        
        self.get_users()
        
        # Get all conversations
        all_conversations = self.get_all_conversations()
        
        # Find additional DMs
        additional_dms = self.find_additional_dms()
        all_conversations['ims'].extend(additional_dms)
        
        print(f"\n📊 Found conversations:")
        print(f"  Channels: {len(all_conversations['channels'])}")
        print(f"  Direct Messages: {len(all_conversations['ims'])}")
        print(f"  Group Messages: {len(all_conversations['groups'])}")
        
        # Export everything
        print(f"\n🔄 Starting exports...")
        
        if all_conversations['channels']:
            self.export_conversations(all_conversations['channels'], 'channels')
            
        if all_conversations['ims']:
            self.export_conversations(all_conversations['ims'], 'ims')
            
        if all_conversations['groups']:
            self.export_conversations(all_conversations['groups'], 'groups')
        
        # Create summary
        summary = self.create_export_summary()
        
        print(f"\n🎉 Export completed!")
        print(f"📈 Summary:")
        print(f"  Total Conversations: {summary['total_conversations']}")
        print(f"  Total Messages: {summary['total_messages']}")
        print(f"  Channels: {summary['breakdown'].get('channels', {}).get('conversations', 0)} conversations, {summary['breakdown'].get('channels', {}).get('messages', 0)} messages")
        print(f"  DMs: {summary['breakdown'].get('ims', {}).get('conversations', 0)} conversations, {summary['breakdown'].get('ims', {}).get('messages', 0)} messages")
        print(f"  Groups: {summary['breakdown'].get('groups', {}).get('conversations', 0)} conversations, {summary['breakdown'].get('groups', {}).get('messages', 0)} messages")
        print(f"\n📁 Check the '{self.base_dir}' directory for your exports!")

if __name__ == "__main__":
    SLACK_TOKEN = os.getenv('SLACK_TOKEN') or input("Enter your Slack token: ").strip()    
    if not SLACK_TOKEN:
        print("❌ Please provide a valid Slack token")
        exit(1)
        
    print("📋 This will export ALL available messages from:")
    print("  • All channels (public & private)")
    print("  • All direct messages (including hidden ones)")
    print("  • All group messages")
    print("  • Including archived conversations")
    print("\n⚠️  With robust error handling and retry logic for network issues")
    
    confirm = input("\nContinue? (y/N): ").strip().lower()
    
    if confirm != 'y':
        print("Export cancelled.")
        exit(0)
        
    exporter = SlackMessageExporter(SLACK_TOKEN)
    exporter.run_export()