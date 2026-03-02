"""Emails tab for managing email-Discord ID mappings."""
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.filedialog as fd
import csv


class EmailsTab(ttk.Frame):
    """Tab for managing email lookups."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._create_ui()

    def _create_ui(self):
        """Create the emails tab UI."""
        # Control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Add Email",
            command=self.add_email
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Edit Email",
            command=self.edit_email
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Delete Email",
            command=self.delete_email
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(
            control_frame,
            text="Import CSV",
            command=self.import_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Export CSV",
            command=self.export_csv
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(
            control_frame,
            text="Refresh",
            command=self.load_emails
        ).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add('write', self.filter_emails)
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("ID", "Email", "Discord ID", "Created"),
            show="headings"
        )
        self.tree.heading("ID", text="ID")
        self.tree.heading("Email", text="Email")
        self.tree.heading("Discord ID", text="Discord ID")
        self.tree.heading("Created", text="Created")

        self.tree.column("ID", width=50)
        self.tree.column("Email", width=250)
        self.tree.column("Discord ID", width=150)
        self.tree.column("Created", width=150)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

    def load_emails(self):
        """Load emails from database."""
        emails = self.app.db.get_all_emails()
        self._populate_tree(emails)
        print(f"[OK] Loaded {len(emails)} emails")

    def _populate_tree(self, emails, filter_text=""):
        """Populate treeview with emails."""
        self.tree.delete(*self.tree.get_children())
        filter_text = filter_text.lower()

        for e in emails:
            if filter_text:
                if filter_text not in e['email'].lower():
                    if filter_text not in str(e['discord_id']):
                        continue

            self.tree.insert("", tk.END, values=(
                e['id'],
                e['email'],
                e['discord_id'],
                e.get('created_at', '')[:19]
            ))

    def filter_emails(self, *args):
        """Filter emails based on search text."""
        emails = self.app.db.get_all_emails()
        self._populate_tree(emails, self.filter_var.get())

    def add_email(self):
        """Add a new email."""
        dialog = EmailDialog(self, "Add Email")
        if dialog.result:
            if self.app.db.add_email(dialog.result['email'], dialog.result['discord_id']):
                self.load_emails()
                # Refresh bot's email lookup if bot is running
                if self.app.bot.is_running():
                    self.app.bot.refresh_data()
                self.app.log_message(f"✅ Added email: {dialog.result['email']} (Discord: {dialog.result['discord_id']})")
            else:
                messagebox.showerror("Error", "Email already exists.")

    def edit_email(self):
        """Edit selected email."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an email to edit.")
            return

        item = self.tree.item(selection[0])
        current = {
            'email': item['values'][1],
            'discord_id': item['values'][2]
        }

        dialog = EmailDialog(self, "Edit Email", current)
        if dialog.result:
            # Remove old and add new
            self.app.db.remove_email(current['email'], current['discord_id'])
            if self.app.db.add_email(dialog.result['email'], dialog.result['discord_id']):
                self.load_emails()
                # Refresh bot's email lookup if bot is running
                if self.app.bot.is_running():
                    self.app.bot.refresh_data()
                self.app.log_message(f"✏️ Updated email: {current['email']} -> {dialog.result['email']}")
            else:
                # Restore old
                self.app.db.add_email(current['email'], current['discord_id'])
                messagebox.showerror("Error", "Email already exists.")

    def delete_email(self):
        """Delete selected email."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an email to delete.")
            return

        item = self.tree.item(selection[0])
        email = item['values'][1]
        discord_id = item['values'][2]

        if messagebox.askyesno("Confirm Delete", f"Delete email {email}?"):
            if self.app.db.remove_email(email, discord_id):
                self.load_emails()
                # Refresh bot's email lookup if bot is running
                if self.app.bot.is_running():
                    self.app.bot.refresh_data()
                self.app.log_message(f"🗑️ Deleted email: {email}")
            else:
                messagebox.showerror("Error", "Failed to delete email.")

    def import_csv(self):
        """Import emails from CSV file."""
        path = fd.askopenfilename(
            title="Select Email CSV",
            filetypes=[("CSV Files", "*.csv")]
        )
        if not path:
            return

        try:
            count = 0
            with open(path, newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    email = row.get("Email", "").strip().lower()
                    discord_id = row.get("DiscordID", "").strip()
                    if email and discord_id:
                        try:
                            discord_id = int(discord_id)
                            if self.app.db.add_email(email, discord_id):
                                count += 1
                        except ValueError:
                            pass

            self.load_emails()
            self.app.log_message(f"📥 Imported {count} emails from CSV")
            messagebox.showinfo("Import Complete", f"Imported {count} emails.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import: {e}")

    def export_csv(self):
        """Export emails to CSV file."""
        path = fd.asksaveasfilename(
            title="Save Email CSV",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")]
        )
        if not path:
            return

        try:
            emails = self.app.db.get_all_emails()
            with open(path, 'w', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=["Email", "DiscordID"])
                writer.writeheader()
                for e in emails:
                    writer.writerow({
                        "Email": e['email'],
                        "DiscordID": e['discord_id']
                    })

            self.app.log_message(f"📤 Exported {len(emails)} emails to CSV")
            messagebox.showinfo("Export Complete", f"Exported {len(emails)} emails.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")


class EmailDialog(tk.Toplevel):
    """Dialog for adding/editing emails."""

    def __init__(self, parent, title, current=None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.transient(parent)

        current = current or {}

        ttk.Label(self, text="Email:").grid(
            row=0, column=0, sticky='w', padx=5, pady=5)
        self.email_var = tk.StringVar(value=current.get('email', ''))
        ttk.Entry(self, textvariable=self.email_var, width=40).grid(
            row=0, column=1, padx=5, pady=5)

        ttk.Label(self, text="Discord ID:").grid(
            row=1, column=0, sticky='w', padx=5, pady=5)
        self.discord_var = tk.StringVar(value=current.get('discord_id', ''))
        ttk.Entry(self, textvariable=self.discord_var, width=40).grid(
            row=1, column=1, padx=5, pady=5)

        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.grab_set()

    def save(self):
        email = self.email_var.get().strip()
        try:
            discord_id = int(self.discord_var.get().strip())
        except ValueError:
            messagebox.showwarning("Invalid", "Discord ID must be a number.")
            return

        if not email:
            messagebox.showwarning("Required", "Email is required.")
            return

        self.result = {'email': email, 'discord_id': discord_id}
        self.destroy()
