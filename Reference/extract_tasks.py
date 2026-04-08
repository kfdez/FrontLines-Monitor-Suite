#!/usr/bin/env python3
"""
Extract task setup information from Stellar Bot export file,
stripping out all sensitive data (profiles, accounts, payment info, etc.)
"""

import json
import os
import glob
from datetime import datetime
import sys

# Try to find Stellar AIO export folder
def find_latest_stellar_export():
    """Find the latest stellar-export-YYYY-MM-DD.json in StellarAIO appdata folder."""

    # Check common locations
    possible_paths = [
        os.path.join(os.environ.get('APPDATA', ''), 'StellarAIO'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'StellarAIO'),
        os.path.join(os.environ.get('ProgramData', ''), 'StellarAIO'),
    ]

    # First try to find by glob in each base path
    for base_path in possible_paths:
        if not base_path or not os.path.exists(base_path):
            continue

        # Look for stellar-export-YYYY-MM-DD.json files (not _tasks_only)
        pattern = os.path.join(base_path, 'stellar-export-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json')
        matches = glob.glob(pattern)

        if matches:
            # Sort by modification time, get latest
            latest = max(matches, key=os.path.getmtime)
            return latest

    return None

def get_default_input_file():
    """Get the default input file - latest export or fallback."""
    latest = find_latest_stellar_export()
    if latest:
        return latest

    # Fallback to local reference folder
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_pattern = os.path.join(script_dir, 'stellar-export-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json')
    local_matches = glob.glob(local_pattern)
    if local_matches:
        return max(local_matches, key=os.path.getmtime)

    # Final fallback
    return "stellar-export-2026-03-02.json"

def extract_task_setup(input_file, output_file=None, output_dir=None):
    """Extract only task setup data from Stellar export."""

    # If output_dir specified, use it instead of input file's directory
    if output_dir and not output_file:
        base_name = os.path.basename(input_file)
        name, ext = os.path.splitext(base_name)
        output_file = os.path.join(output_dir, f"{name}_tasks_only{ext}")

    print(f"Reading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Build output structure with only task-related info
    output = {
        "extracted_at": datetime.now().isoformat(),
        "source_file": os.path.basename(input_file),
        "task_groups": [],
        "summary": {
            "total_task_groups": 0,
            "total_tasks": 0,
            "by_site": {},
            "by_mode": {}
        }
    }

    # Extract task groups and tasks
    task_groups = data.get('tasks', [])

    # Build profile ID to name/email mapping (for reference only, not including full profile)
    profiles = data.get('profiles', [])
    profile_id_to_name = {}
    profile_id_to_email = {}
    profile_set_id_to_name = {}
    for pg in profiles:
        profile_set_id_to_name[pg.get('id')] = pg.get('name')
        for sp in pg.get('profiles', []):
            profile_id_to_name[sp.get('id')] = sp.get('profileName')
            profile_id_to_email[sp.get('id')] = sp.get('email', '')

    # Get monitor sets info
    monitor_sets = data.get('config', {}).get('monitorSets', [])
    monitor_set_info = {}
    for ms in monitor_sets:
        monitor_set_info[ms.get('id')] = ms.get('name', 'Unnamed')

    # Get checkout sets info
    checkout_sets = data.get('config', {}).get('checkoutSets', [])
    checkout_set_info = {}
    for cs in checkout_sets:
        checkout_set_info[cs.get('id')] = cs.get('name', 'Unnamed')

    # Process each task group
    for tg in task_groups:
        group_data = {
            "id": tg.get('id'),
            "name": tg.get('taskGroupName'),
            "site": tg.get('taskGroupSite'),
            "created": tg.get('created'),
            "is_favorite": tg.get('isFavorite'),
            "tasks": []
        }

        tasks = tg.get('tasks', [])
        for task in tasks:
            task_data = {
                "id": task.get('id'),
                "name": task.get('name'),
                "mode": task.get('mode'),
                "site": task.get('site'),
                "identifier": task.get('identifier'),
                "profile_set_id": task.get('profileSetId'),
                "profile_set_name": profile_set_id_to_name.get(task.get('profileSetId'), 'Unknown'),
                "profile_id": task.get('profileId'),
                "profile_name": profile_id_to_name.get(task.get('profileId'), 'Unknown'),
                "profile_email": profile_id_to_email.get(task.get('profileId'), ''),
                "monitor_set_id": task.get('monitorSetId'),
                "monitor_set_name": monitor_set_info.get(task.get('monitorSetId'), ''),
                "checkout_set_id": task.get('checkoutSetId'),
                "checkout_set_name": checkout_set_info.get(task.get('checkoutSetId'), ''),
                "details": task.get('details', {})
            }
            group_data["tasks"].append(task_data)

        output["task_groups"].append(group_data)

    # Calculate summary statistics
    output["summary"]["total_task_groups"] = len(output["task_groups"])
    output["summary"]["total_tasks"] = sum(len(tg["tasks"]) for tg in output["task_groups"])

    # Count by site
    site_counts = {}
    for tg in output["task_groups"]:
        site = tg["site"]
        site_counts[site] = site_counts.get(site, 0) + len(tg["tasks"])
    output["summary"]["by_site"] = dict(sorted(site_counts.items(), key=lambda x: -x[1]))

    # Count by mode
    mode_counts = {}
    for tg in output["task_groups"]:
        for task in tg["tasks"]:
            mode = task["mode"]
            mode_counts[mode] = mode_counts.get(mode, 0) + 1
    output["summary"]["by_mode"] = dict(sorted(mode_counts.items(), key=lambda x: -x[1]))

    # Collect unique emails for discord mapping
    unique_emails = set()
    for tg in output["task_groups"]:
        for task in tg["tasks"]:
            email = task.get("profile_email", "")
            if email:
                unique_emails.add(email)

    # Add discord mapping template
    output["discord_mapping_template"] = {
        "description": "Fill in Discord User IDs for each email. The script will use these to map tasks to Discord users.",
        "instructions": "Replace null values with Discord user IDs (e.g., '123456789012345678'). Leave as null if no mapping needed.",
        "mappings": {email: None for email in sorted(unique_emails)}
    }

    # Generate output filename if not provided
    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_tasks_only{ext}"

    # Write output
    print(f"Writing to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\nDone! Extracted:")
    print(f"  - {output['summary']['total_task_groups']} task groups")
    print(f"  - {output['summary']['total_tasks']} total tasks")
    print(f"  - {len(profile_set_id_to_name)} profile sets (names only)")
    print(f"  - {len(profile_id_to_name)} individual profiles (names only)")
    print(f"\nOutput saved to: {output_file}")

    return output


def apply_discord_mapping(data, mapping_file):
    """Apply discord user ID mapping to extracted task data."""

    print(f"Loading mapping from {mapping_file}...")
    with open(mapping_file, 'r', encoding='utf-8') as f:
        mapping_data = json.load(f)

    # Get the mappings dict
    mappings = mapping_data.get('mappings', {})

    # Apply mapping to each task
    tasks_mapped = 0
    for tg in data.get('task_groups', []):
        for task in tg.get('tasks', []):
            email = task.get('profile_email', '')
            if email and email in mappings:
                discord_id = mappings[email]
                if discord_id:
                    task['discord_user_id'] = discord_id
                    tasks_mapped += 1

    print(f"Mapped {tasks_mapped} tasks to Discord users")

    # Update the mapping section to show it's been applied
    if 'discord_mapping_template' in data:
        data['discord_mapping_template']['applied'] = True
        data['discord_mapping_template']['mapping_count'] = tasks_mapped

    return data


def save_mapping_template(data, output_file):
    """Save just the discord mapping template to a separate file."""

    template = data.get('discord_mapping_template', {})
    template_file = output_file.replace('.json', '_discord_mapping.json')

    # Create a clean mapping file
    mapping_output = {
        "_instructions": "Fill in Discord User IDs for each email below.",
        "_how_to_get_user_id": "Enable Developer Mode in Discord, right-click user, 'Copy User ID'",
        "mappings": template.get('mappings', {})
    }

    with open(template_file, 'w', encoding='utf-8') as f:
        json.dump(mapping_output, f, indent=2, ensure_ascii=False)

    print(f"Discord mapping template saved to: {template_file}")
    return template_file


if __name__ == "__main__":
    input_file = None
    output_file = None
    output_dir = None
    discord_mapping_file = None
    template_only = False

    # Parse arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ['--latest', '-l']:
            # Explicitly find latest from StellarAIO folder
            input_file = find_latest_stellar_export()
            if not input_file:
                print("Error: Could not find any Stellar export files in AppData")
                sys.exit(1)
            print(f"Found latest export: {input_file}")
        elif arg in ['--output-dir', '-o']:
            if i + 1 < len(sys.argv):
                output_dir = sys.argv[i + 1]
                i += 1
            else:
                print("Error: --output-dir requires a path")
                sys.exit(1)
        elif arg in ['--discord-mapping', '-m']:
            if i + 1 < len(sys.argv):
                discord_mapping_file = sys.argv[i + 1]
                i += 1
            else:
                print("Error: --discord-mapping requires a mapping file")
                sys.exit(1)
        elif arg == '--template-only':
            template_only = True
        elif arg == '--help' or arg == '-h':
            print("Usage: python extract_tasks.py [options]")
            print()
            print("Options:")
            print("  -l, --latest            Find latest export from AppData/StellarAIO")
            print("  -o, --output-dir DIR    Output directory for extracted file")
            print("  -m, --discord-mapping   Apply Discord user ID mapping from file")
            print("  --template-only         Only extract the discord mapping template")
            print("  input_file              Input file (optional, auto-detects if not specified)")
            print("  output_file             Output file (optional, defaults to input_tasks_only.json)")
            print()
            print("Examples:")
            print("  python extract_tasks.py                                    # Auto-detect latest")
            print("  python extract_tasks.py -l                                 # Explicit latest from AppData")
            print("  python extract_tasks.py -l -o ./output                     # Latest, save to ./output")
            print("  python extract_tasks.py -m mapping.json                    # Apply discord mapping")
            print("  python extract_tasks.py input.json output.json             # Custom files")
            print()
            print("Discord Mapping:")
            print("  The extracted file includes a 'discord_mapping_template' section with all")
            print("  unique profile emails. Fill in Discord User IDs in a separate file, then")
            print("  use -m to apply the mapping.")
            sys.exit(0)
        else:
            # Assume it's the input file
            input_file = arg

        i += 1

    # Auto-detect input if not set
    if not input_file:
        input_file = get_default_input_file()
        print(f"Auto-detected input file: {input_file}")

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        sys.exit(1)

    # Default output to current directory if input is from AppData
    if not output_file and not output_dir:
        # If running from Reference folder, default to saving there
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(script_dir) == 'Reference':
            output_dir = script_dir

    # Generate output filename if not provided
    if output_file is None and output_dir:
        base_name = os.path.basename(input_file)
        name, ext = os.path.splitext(base_name)
        output_file = os.path.join(output_dir, f"{name}_tasks_only{ext}")
    elif output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_tasks_only{ext}"

    # Run extraction
    data = extract_task_setup(input_file, output_file, output_dir)

    # Handle template-only option
    if template_only:
        save_mapping_template(data, output_file)
        sys.exit(0)

    # Handle discord mapping
    if discord_mapping_file:
        if not os.path.exists(discord_mapping_file):
            print(f"Error: Mapping file not found: {discord_mapping_file}")
            sys.exit(1)

        data = apply_discord_mapping(data, discord_mapping_file)

        # Save the updated data
        print(f"Writing mapped data to {output_file}...")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Done! Mapped tasks saved to: {output_file}")
