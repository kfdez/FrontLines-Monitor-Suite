"""Tasks manager for Stellar Bot task extraction."""
import os
import json
import shutil
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from core.database import Database


class TasksManager:
    """Manages Stellar tasks data extraction and loading."""

    def __init__(self, db: Database, log_callback=None):
        self.db = db
        self.log_callback = log_callback
        self.tasks_data: Optional[Dict[str, Any]] = None
        self.platforms: List[str] = []
        self.last_processed_file: Optional[str] = None
        self._scheduler_timer: Optional[threading.Timer] = None
        self._is_running = False

        # Data folder path
        self.data_folder = "skutto_data"
        self.tasks_file = os.path.join(self.data_folder, "tasks.json")

        # Ensure data folder exists
        os.makedirs(self.data_folder, exist_ok=True)

    def log(self, message: str):
        """Log a message via callback."""
        if self.log_callback:
            self.log_callback(message)
        print(f"[TasksManager] {message}")

    def _get_config(self, key: str, default: str = None) -> Optional[str]:
        """Get config value."""
        return self.db.get_config(key, default)

    def _set_config(self, key: str, value: str):
        """Set config value."""
        self.db.set_config(key, value)

    def get_stellar_export_path(self) -> Optional[str]:
        """Get the auto-detected Stellar export file path."""
        import re

        # Always auto-detect from AppData - StellarAIO
        appdata_path = os.path.expandvars(r"%APPDATA%\StellarAIO")
        if os.path.exists(appdata_path):
            # Find the most recent stellar-export-YYYY-MM-DD.json file
            json_files = []
            for f in os.listdir(appdata_path):
                # Match stellar-export-YYYY-MM-DD.json pattern
                if re.match(r'stellar-export-\d{4}-\d{2}-\d{2}\.json', f):
                    full_path = os.path.join(appdata_path, f)
                    json_files.append((full_path, os.path.getmtime(full_path)))

            if json_files:
                # Return the most recent file
                json_files.sort(key=lambda x: x[1], reverse=True)
                return json_files[0][0]

        return None

    def process_tasks(self, force: bool = False) -> bool:
        """Process tasks from Stellar export file. Returns True if new data was processed."""
        source_file = self.get_stellar_export_path()

        if not source_file:
            self.log("No Stellar export file found")
            return False

        source_mtime = os.path.getmtime(source_file)

        # Check if file is newer than last processed (skip if force=True)
        if not force:
            last_processed = self._get_config("tasks_last_processed_mtime", "0")

            try:
                last_mtime = float(last_processed)
            except (ValueError, TypeError):
                last_mtime = 0

            if source_mtime <= last_mtime:
                self.log(f"No newer tasks file found (current: {os.path.basename(source_file)})")
                return False

        # Read and parse the tasks file
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except Exception as e:
            self.log(f"Error reading tasks file: {e}")
            return False


        # Transform the data structure
        transformed_data = self._transform_tasks(raw_data, source_file)

        # Save to our data folder
        try:
            with open(self.tasks_file, 'w', encoding='utf-8') as f:
                json.dump(transformed_data, f, indent=2)
        except Exception as e:
            self.log(f"Error saving tasks file: {e}")
            return False

        # Update last processed timestamp
        self._set_config("tasks_last_processed_mtime", str(source_mtime))

        # Load the data
        self.tasks_data = transformed_data
        self.platforms = self._extract_platforms(transformed_data)
        self.last_processed_file = os.path.basename(source_file)

        self.log(f"Processing tasks from {os.path.basename(source_file)}")
        self.log(f"Loaded {len(self.platforms)} platforms: {', '.join(self.platforms)}")
        return True

    def _transform_tasks(self, raw_data: Dict, source_file: str) -> Dict[str, Any]:
        """Transform raw Stellar export data to our format."""
        # Use file's modification time as the source timestamp
        source_mtime = os.path.getmtime(source_file)
        extracted_at = datetime.fromtimestamp(source_mtime).strftime("%Y-%m-%d %H:%M:%S")

        transformed = {
            "extracted_at": extracted_at,
            "source_file": os.path.basename(source_file),
            "task_groups": []
        }

        # Handle Stellar export format - dict with sessionGroups, profiles, etc.
        if isinstance(raw_data, dict):
            # Try sessionGroups first (most likely for monitors)
            if 'sessionGroups' in raw_data:
                session_groups = raw_data['sessionGroups']
                self.log(f"DEBUG: Found sessionGroups with {len(session_groups)} items")
                if session_groups:
                    self.log(f"DEBUG: First sessionGroup: {session_groups[0]}")

                # Build profile lookup by id - include nested profiles
                profile_lookup = {}
                for profile in raw_data.get('profiles', []):
                    # Add parent profile id
                    profile_id = profile.get('id')
                    for np in profile.get('profiles', []):
                        nested_id = np.get('id')
                        email = np.get('email', '')
                        profile_name = np.get('profileName', '')
                        if nested_id and email:
                            profile_lookup[nested_id] = {'email': email, 'name': profile_name}

                # Build session lookup by site and by id (for AmazonV3)
                session_by_site = {}
                session_by_id = {}
                for s in raw_data.get('sessions', []):
                    site = s.get('site', '')
                    email = s.get('email', '')
                    name = s.get('name', '')
                    session_id = s.get('id', '')
                    if site and email:
                        if site not in session_by_site:
                            session_by_site[site] = []
                        session_by_site[site].append({'email': email, 'name': name})
                    if session_id and email:
                        session_by_id[session_id] = {'email': email, 'name': name}

                # Extract tasks from root "tasks" key
                for task_group in raw_data.get('tasks', []):
                    site = task_group.get('taskGroupSite', 'Unknown')
                    task_group_name = task_group.get('taskGroupName', '')

                    # Get nested tasks
                    simplified_tasks = []
                    for task in task_group.get('tasks', []):
                        profile_id = task.get('profileId', '')
                        profile_info = profile_lookup.get(profile_id, {})
                        profile_email = profile_info.get('email', '')
                        profile_name = profile_info.get('name', '')

                        # Always prioritize session email if sessionId exists in the task
                        details = task.get('details', {})
                        session_id = details.get('sessionId', '')

                        if session_id and session_id in session_by_id:
                            # Use session email (from sessionId)
                            profile_email = session_by_id[session_id].get('email', '')
                            profile_name = session_by_id[session_id].get('name', '')
                        elif not profile_email:
                            # No sessionId - try session lookup by site
                            task_site = task.get('site', site)
                            if task_site in session_by_site:
                                profile_email = session_by_site[task_site][0].get('email', '')
                                profile_name = session_by_site[task_site][0].get('name', '')
                            # Try without V3 suffix (AmazonV3 -> Amazon)
                            elif site.replace('V3', '') in session_by_site:
                                profile_email = session_by_site[site.replace('V3', '')][0].get('email', '')
                                profile_name = session_by_site[site.replace('V3', '')][0].get('name', '')

                        # Get task name: name -> identifier -> task_group_name
                        task_name = task.get('name', '')
                        if not task_name:
                            # Try identifier field first (pipe-separated labels)
                            identifier = task.get('identifier', '')
                            if identifier:
                                # Show all pipe-separated values, comma-separated for readability
                                parts = identifier.split('|')
                                task_name = ', '.join(parts) if len(parts) > 1 else identifier
                            # Try details.inputList labels
                            if not task_name:
                                details = task.get('details', {})
                                input_list = details.get('inputList', []) if details else []
                                if input_list:
                                    task_name = input_list[0].get('label', '')
                            # Try details.items
                            if not task_name:
                                details = task.get('details', {})
                                items = details.get('items', []) if details else []
                                if items:
                                    first_item = items[0]
                                    task_name = first_item.get('input', '') or first_item.get('sku', '')
                                    # Clean up URL
                                    if task_name and task_name.startswith('http'):
                                        task_name = task_name.split('/')[-1].replace('-', ' ').replace('.html', '').replace('.com', '')
                        # Final fallback to task_group_name
                        if not task_name:
                            task_name = task_group_name

                        simplified_tasks.append({
                            'name': task_name,
                            'site': task.get('site', site),
                            'profile_email': profile_email,
                            'profile_name': profile_name,
                            'mode': task.get('mode', ''),
                            'task_group_name': task_group_name,
                        })

                    self.log(f"DEBUG: Group '{site}' ({task_group_name}) has {len(simplified_tasks)} tasks")

                    platform = self._map_site_to_platform(site)
                    transformed["task_groups"].append({
                        "site": site,
                        "platform": platform,
                        "task_group_name": task_group_name,
                        "tasks": simplified_tasks
                    })

            # Also check profiles as fallback
            elif 'profiles' in raw_data:
                profiles = raw_data['profiles']
                self.log(f"DEBUG: Found profiles with {len(profiles)} items")

        return transformed

    def _map_site_to_platform(self, site: str) -> str:
        """Map Stellar site name to SKUtto platform."""
        site_lower = site.lower()

        # Get existing platforms from database
        platform_sites = self.db.get_all_platform_sites()

        # Try to match by site URL
        for ps in platform_sites:
            ps_url = ps.get('site_url', '').lower()
            ps_platform = ps.get('platform', '').lower()
            if ps_url and ps_url in site_lower:
                return ps_platform
            if ps_platform and ps_platform in site_lower:
                return ps_platform

        # Default: use a cleaned version of the site name
        return site_lower.replace('https://', '').replace('www.', '').split('.')[0]

    def _extract_platforms(self, tasks_data: Dict) -> List[str]:
        """Extract unique platforms from tasks data."""
        platforms = set()
        for group in tasks_data.get("task_groups", []):
            if group.get("platform"):
                platforms.add(group["platform"])
        return sorted(list(platforms))

    def load_tasks(self) -> bool:
        """Load tasks from saved JSON file."""
        if not os.path.exists(self.tasks_file):
            return False

        # Prevent loading our own tasks.json as a source file (recursion prevention)
        source_file = self.get_stellar_export_path()
        if source_file and os.path.abspath(source_file) == os.path.abspath(self.tasks_file):
            self.log("Prevented loading own tasks.json as source")
            return False

        try:
            with open(self.tasks_file, 'r', encoding='utf-8') as f:
                self.tasks_data = json.load(f)
                self.platforms = self._extract_platforms(self.tasks_data)
                self.last_processed_file = self.tasks_data.get("source_file", "unknown")
            self.log(f"Loaded tasks from file: {len(self.platforms)} platforms ({', '.join(self.platforms)})")
            return True
        except Exception as e:
            self.log(f"Error loading tasks file: {e}")
            return False

    def get_user_tasks(self, discord_id: int, platform: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get tasks for a specific Discord user, optionally filtered by platform."""
        if not self.tasks_data:
            return []

        # Get user's emails
        user_emails = self.db.get_emails_by_discord_id(discord_id)
        email_set = {e['email'].lower() for e in user_emails}

        self.log(f"DEBUG get_user_tasks: discord_id={discord_id}, emails={email_set}")

        if not email_set:
            return []

        # Filter tasks
        user_tasks = []

        for group in self.tasks_data.get("task_groups", []):
            # Filter by platform if specified
            if platform and group.get("platform", "").lower() != platform.lower():
                continue

            for task in group.get("tasks", []):
                # Skip monitor mode tasks
                task_mode = task.get("mode", "").lower()
                if task_mode == "monitor":
                    continue

                # Check if task belongs to user via email
                profile_email = task.get("profile_email", "").lower()
                if profile_email and profile_email in email_set:
                    task_copy = dict(task)
                    task_copy["platform"] = group.get("platform", "")
                    task_copy["site"] = group.get("site", "")
                    task_copy["task_group_name"] = task.get("task_group_name", group.get("task_group_name", ""))
                    user_tasks.append(task_copy)

        self.log(f"DEBUG: Returning {len(user_tasks)} tasks after filtering")
        return user_tasks

    def get_all_platforms(self) -> List[str]:
        """Get all available platforms."""
        return self.platforms

    def start_auto_refresh(self):
        """Start auto-refresh scheduler."""
        if self._is_running:
            return

        interval_minutes = int(self._get_config("tasks_auto_refresh_interval", "0"))
        if interval_minutes <= 0:
            self.log("Auto-refresh is disabled (interval set to 0)")
            return

        self._is_running = True
        self.log(f"Starting auto-refresh every {interval_minutes} minutes")

        # Initial load
        self.load_tasks()
        self.process_tasks()

        # Schedule periodic refresh
        self._schedule_next_refresh(interval_minutes)

    def _schedule_next_refresh(self, interval_minutes: int):
        """Schedule the next refresh."""
        if not self._is_running:
            return

        # Cancel existing timer
        if self._scheduler_timer:
            self._scheduler_timer.cancel()

        # Schedule next refresh
        interval_ms = interval_minutes * 60 * 1000
        self._scheduler_timer = threading.Timer(
            interval_ms / 1000,
            self._auto_refresh_callback,
            args=[interval_minutes]
        )
        self._scheduler_timer.daemon = True
        self._scheduler_timer.start()

    def _auto_refresh_callback(self, interval_minutes: int):
        """Callback for auto-refresh."""
        # Process tasks (will only process if newer file exists)
        self.process_tasks()

        # Schedule next refresh
        if self._is_running:
            self._schedule_next_refresh(interval_minutes)

    def stop_auto_refresh(self):
        """Stop auto-refresh scheduler."""
        self._is_running = False
        if self._scheduler_timer:
            self._scheduler_timer.cancel()
            self._scheduler_timer = None
        self.log("Auto-refresh stopped")

    def refresh_schedule(self):
        """Refresh the auto-refresh schedule (call after config change)."""
        self.stop_auto_refresh()
        self.start_auto_refresh()
