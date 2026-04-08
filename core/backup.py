"""Backup and restore functionality for FrontLines Monitor Suite."""

import json
import os
import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


def get_app_data_dir():
    """Get the directory where app data is stored.

    When running as installed app, data is in the app directory.
    When running in development, data is in the project root.
    """
    if getattr(sys, 'frozen', False):
        # Running as bundled exe - use the exe directory
        return os.path.dirname(sys.executable)
    else:
        # Running in development - use current directory
        return os.getcwd()


class BackupManager:
    """Manages backup and restore of all application data."""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = get_app_data_dir()
        self.base_dir = base_dir

    def create_backup(self, backup_path: str = None) -> str:
        """Create a backup of all application data.

        Args:
            backup_path: Path for the backup file. If None, generates one with timestamp.

        Returns:
            Path to the created backup file.
        """
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.base_dir, f"frontlines_backup_{timestamp}.flb")

        # Create a temporary directory for the backup
        import tempfile
        temp_dir = tempfile.mkdtemp()

        try:
            # 1. Backup database
            db_path = os.path.join(self.base_dir, "skutto.db")
            if os.path.exists(db_path):
                shutil.copy2(db_path, os.path.join(temp_dir, "skutto.db"))

            # 2. Backup HV Monitor data
            hv_dir = os.path.join(self.base_dir, "hv_monitor_data")
            if os.path.exists(hv_dir):
                hv_backup = os.path.join(temp_dir, "hv_monitor_data")
                shutil.copytree(hv_dir, hv_backup)

            # 3. Backup Shopify Monitor data
            shopify_dir = os.path.join(self.base_dir, "shopify_monitor_data")
            if os.path.exists(shopify_dir):
                shopify_backup = os.path.join(temp_dir, "shopify_monitor_data")
                shutil.copytree(shopify_dir, shopify_backup)

            # 4. Backup skutto data (tasks)
            skutto_dir = os.path.join(self.base_dir, "skutto_data")
            if os.path.exists(skutto_dir):
                skutto_backup = os.path.join(temp_dir, "skutto_data")
                shutil.copytree(skutto_dir, skutto_backup)

            # 5. Create backup manifest
            manifest = {
                "version": "3.0",
                "created_at": datetime.now().isoformat(),
                "files": [
                    "skutto.db",
                    "hv_monitor_data",
                    "shopify_monitor_data",
                    "skutto_data"
                ]
            }
            with open(os.path.join(temp_dir, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2)

            # 6. Create zip archive
            shutil.make_archive(backup_path.replace(".flb", ""), "zip", temp_dir)

            # Rename to .flb extension
            zip_path = backup_path.replace(".flb", "") + ".zip"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(zip_path, backup_path)

            return backup_path

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def restore_backup(self, backup_path: str) -> bool:
        """Restore application data from a backup.

        Args:
            backup_path: Path to the backup file (.flb or .zip)

        Returns:
            True if restore was successful, False otherwise.
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Create temporary directory for extraction
        import tempfile
        temp_dir = tempfile.mkdtemp()

        try:
            # Extract the backup
            shutil.unpack_archive(backup_path, temp_dir)

            # Verify manifest exists
            manifest_path = os.path.join(temp_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                raise ValueError("Invalid backup file - no manifest found")

            with open(manifest_path, "r") as f:
                manifest = json.load(f)

            # Restore database
            db_backup = os.path.join(temp_dir, "skutto.db")
            if os.path.exists(db_backup):
                db_path = os.path.join(self.base_dir, "skutto.db")
                # Create backup of current db first
                if os.path.exists(db_path):
                    shutil.copy2(db_path, db_path + ".bak")
                shutil.copy2(db_backup, db_path)

            # Restore HV Monitor data
            hv_backup = os.path.join(temp_dir, "hv_monitor_data")
            if os.path.exists(hv_backup):
                hv_dir = os.path.join(self.base_dir, "hv_monitor_data")
                if os.path.exists(hv_dir):
                    shutil.rmtree(hv_dir)
                shutil.copytree(hv_backup, hv_dir)

            # Restore Shopify Monitor data
            shopify_backup = os.path.join(temp_dir, "shopify_monitor_data")
            if os.path.exists(shopify_backup):
                shopify_dir = os.path.join(self.base_dir, "shopify_monitor_data")
                if os.path.exists(shopify_dir):
                    shutil.rmtree(shopify_dir)
                shutil.copytree(shopify_backup, shopify_dir)

            # Restore skutto data
            skutto_backup = os.path.join(temp_dir, "skutto_data")
            if os.path.exists(skutto_backup):
                skutto_dir = os.path.join(self.base_dir, "skutto_data")
                if os.path.exists(skutto_dir):
                    shutil.rmtree(skutto_dir)
                shutil.copytree(skutto_backup, skutto_dir)

            return True

        except Exception as e:
            print(f"Restore failed: {e}")
            return False

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def get_backup_info(self, backup_path: str) -> dict:
        """Get information about a backup file.

        Args:
            backup_path: Path to the backup file

        Returns:
            Dictionary with backup information
        """
        if not os.path.exists(backup_path):
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        import tempfile
        temp_dir = tempfile.mkdtemp()

        try:
            shutil.unpack_archive(backup_path, temp_dir)

            manifest_path = os.path.join(temp_dir, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r") as f:
                    return json.load(f)

            return {"version": "unknown", "created_at": "unknown"}

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
