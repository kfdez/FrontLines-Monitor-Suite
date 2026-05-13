"""SQLite database manager for the application."""
import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from core.runtime_paths import get_db_path


class ClosingConnection(sqlite3.Connection):
    """SQLite connection that closes after context-manager use."""

    def __exit__(self, exc_type, exc_value, traceback):
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


class Database:
    def __init__(self, db_path: str = None):
        import sys
        if db_path is None:
            if os.environ.get("FRONTLINES_DATA_DIR"):
                db_path = get_db_path()
            elif getattr(sys, 'frozen', False):
                # Running as bundled exe
                db_path = os.path.join(os.path.dirname(sys.executable), "skutto.db")
            else:
                db_path = "skutto.db"
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, factory=ClosingConnection)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Emails table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    discord_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Pending SKUs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_skus (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    url TEXT,
                    role_id TEXT,
                    platform TEXT,
                    submitted_by INTEGER,
                    status TEXT DEFAULT 'pending',
                    reviewed_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP
                )
            """)

            # Add sku2 column if it doesn't exist (for existing databases)
            cursor.execute("PRAGMA table_info(pending_skus)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'sku2' not in columns:
                cursor.execute("ALTER TABLE pending_skus ADD COLUMN sku2 TEXT DEFAULT ''")
            # Add role column if it doesn't exist
            if 'role' not in columns:
                cursor.execute("ALTER TABLE pending_skus ADD COLUMN role TEXT DEFAULT ''")

            # App config table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Platform to Site mapping table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS platform_sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT UNIQUE NOT NULL,
                    site_url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert default platform mappings if empty
            cursor.execute("SELECT COUNT(*) FROM platform_sites")
            if cursor.fetchone()[0] == 0:
                defaults = [
                    ("walmart", "https://www.walmart.com"),
                    ("gamestop", "https://www.gamestop.com"),
                    ("amazon", "https://www.amazon.com"),
                    ("costco", "https://www.costco.com"),
                    ("bestbuy", "https://www.bestbuy.com"),
                    ("popmart", "https://www.popmart.com"),
                    ("queueit", "https://queue-it.net"),
                    ("indigo", "https://www.indigo.ca"),
                ]
                cursor.executemany(
                    "INSERT INTO platform_sites (platform, site_url) VALUES (?, ?)",
                    defaults
                )

            conn.commit()

    # ============ EMAIL OPERATIONS ============

    def add_email(self, email: str, discord_id: int) -> bool:
        """Add an email linked to a Discord ID. Returns True if successful."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO emails (email, discord_id) VALUES (?, ?)",
                    (email.lower(), discord_id)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def remove_email(self, email: str, discord_id: int) -> bool:
        """Remove an email for a specific Discord ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM emails WHERE email = ? AND discord_id = ?",
                (email.lower(), discord_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_emails_by_discord_id(self, discord_id: int) -> List[Dict[str, Any]]:
        """Get all emails for a Discord user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, email, discord_id, created_at FROM emails WHERE discord_id = ?",
                (discord_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_emails(self) -> List[Dict[str, Any]]:
        """Get all emails in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, email, discord_id, created_at FROM emails")
            return [dict(row) for row in cursor.fetchall()]

    def get_discord_id_by_email(self, email: str) -> Optional[int]:
        """Get Discord ID by email."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT discord_id FROM emails WHERE email = ?",
                (email.lower(),)
            )
            result = cursor.fetchone()
            return result['discord_id'] if result else None

    def email_exists(self, email: str) -> bool:
        """Check if an email exists in the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM emails WHERE email = ?", (email.lower(),))
            return cursor.fetchone() is not None

    # ============ PENDING SKU OPERATIONS ============

    def add_pending_sku(
        self,
        sku: str,
        name: str,
        url: str,
        platform: str,
        submitted_by: int,
        role_id: str = None,
        sku2: str = None
    ) -> int:
        """Add a pending SKU for admin approval. Returns the ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO pending_skus
                   (sku, sku2, name, url, role_id, platform, submitted_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (sku.upper(), sku2 or '', name, url, role_id or '', platform, submitted_by)
            )
            conn.commit()
            return cursor.lastrowid

    def get_pending_skus(self) -> List[Dict[str, Any]]:
        """Get all pending SKUs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, sku, sku2, name, url, role_id, role, platform,
                   submitted_by, status, created_at
                   FROM pending_skus WHERE status = 'pending'
                   ORDER BY created_at DESC"""
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_pending_skus(self) -> List[Dict[str, Any]]:
        """Get all pending SKUs (including reviewed)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT id, sku, sku2, name, url, role_id, role, platform,
                   submitted_by, status, reviewed_by, created_at, reviewed_at
                   FROM pending_skus ORDER BY created_at DESC"""
            )
            return [dict(row) for row in cursor.fetchall()]

    def approve_sku(self, sku_id: int, reviewed_by: int) -> bool:
        """Approve a pending SKU."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE pending_skus
                   SET status = 'approved', reviewed_by = ?, reviewed_at = ?
                   WHERE id = ?""",
                (reviewed_by, datetime.now().isoformat(), sku_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_pending_sku(self, sku_id: int, platform: str = None, role_id: str = None, sku2: str = None, role: str = None) -> bool:
        """Update a pending SKU's fields."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params = []
            if platform is not None:
                updates.append("platform = ?")
                params.append(platform)
            if role_id is not None:
                updates.append("role_id = ?")
                params.append(role_id)
            if sku2 is not None:
                updates.append("sku2 = ?")
                params.append(sku2)
            if role is not None:
                updates.append("role = ?")
                params.append(role)

            if not updates:
                return False

            params.append(sku_id)
            cursor.execute(
                f"""UPDATE pending_skus SET {', '.join(updates)} WHERE id = ?""",
                params
            )
            conn.commit()
            return cursor.rowcount > 0

    def reject_sku(self, sku_id: int, reviewed_by: int) -> bool:
        """Reject a pending SKU."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE pending_skus
                   SET status = 'rejected', reviewed_by = ?, reviewed_at = ?
                   WHERE id = ?""",
                (reviewed_by, datetime.now().isoformat(), sku_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_sku_by_id(self, sku_id: int) -> Optional[Dict[str, Any]]:
        """Get a pending SKU by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pending_skus WHERE id = ?",
                (sku_id,)
            )
            result = cursor.fetchone()
            return dict(result) if result else None

    # ============ CONFIG OPERATIONS ============

    def set_config(self, key: str, value: str):
        """Set a config value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def get_config(self, key: str, default: str = None) -> Optional[str]:
        """Get a config value."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
            result = cursor.fetchone()
            return result['value'] if result else default

    def get_all_config(self) -> Dict[str, str]:
        """Get all config as a dictionary."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM config")
            return {row['key']: row['value'] for row in cursor.fetchall()}

    # ============ EMAIL LOOKUP ============

    def get_email_lookup_dict(self) -> Dict[str, int]:
        """Get email lookup dictionary for bot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT email, discord_id FROM emails")
            return {row['email']: row['discord_id'] for row in cursor.fetchall()}

    # ============ PLATFORM-SITE MAPPING ============

    def get_all_platform_sites(self) -> List[Dict[str, Any]]:
        """Get all platform-site mappings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, platform, site_url, created_at FROM platform_sites ORDER BY platform")
            return [dict(row) for row in cursor.fetchall()]

    def add_platform_site(self, platform: str, site_url: str) -> int:
        """Add a platform-site mapping. Returns the ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO platform_sites (platform, site_url) VALUES (?, ?)",
                (platform.lower(), site_url)
            )
            conn.commit()
            return cursor.lastrowid

    def update_platform_site(self, platform_id: int, platform: str, site_url: str) -> bool:
        """Update a platform-site mapping."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE platform_sites SET platform = ?, site_url = ? WHERE id = ?",
                (platform.lower(), site_url, platform_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_platform_site(self, platform_id: int) -> bool:
        """Delete a platform-site mapping."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM platform_sites WHERE id = ?", (platform_id,))
            conn.commit()
            return cursor.rowcount > 0
