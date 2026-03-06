"""Pending SKUs tab for admin approval."""
import tkinter as tk
from tkinter import ttk, messagebox


class PendingTab(ttk.Frame):
    """Tab for managing pending SKU submissions."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._tooltip_window = None
        self._tooltip_timer = None
        self._tooltip_event = None
        self._tooltip_tree = None
        self._last_tooltip_item = None
        self._create_ui()

    def _show_tooltip(self, event, tree):
        """Show tooltip on hover with delay."""
        # Get current item
        item = tree.identify_row(event.y)

        # If tooltip is showing for a different item, hide it immediately
        if self._tooltip_window and item != self._last_tooltip_item:
            if self._tooltip_window:
                self._tooltip_window.destroy()
                self._tooltip_window = None
            self._last_tooltip_item = None

        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None

        if not item:
            return

        self._tooltip_event = event
        self._tooltip_tree = tree
        self._tooltip_event_item = item

        self._tooltip_timer = self.after(600, lambda: self._display_tooltip(tree))

    def _display_tooltip(self, tree):
        """Display the tooltip after delay."""
        event = self._tooltip_event
        if not event:
            return

        item = tree.identify_row(event.y)
        if not item:
            return

        # Check if we're still on the same item
        if hasattr(self, '_tooltip_event_item') and item != self._tooltip_event_item:
            return

        column = tree.identify_column(event.x)
        if not column:
            return

        values = tree.item(item, "values")
        col_idx = int(column[1:]) - 1
        if col_idx < 0 or col_idx >= len(values):
            return

        value = values[col_idx]
        if not value:
            return

        self._tooltip_window = tk.Toplevel(tree)
        self._tooltip_window.wm_overrideredirect(True)
        x = tree.winfo_rootx() + event.x + 15
        y = tree.winfo_rooty() + event.y + 10
        self._tooltip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(self._tooltip_window, text=value, background="#ffffe0", relief="solid", borderwidth=1, padx=5, pady=2)
        label.pack()

        self._last_tooltip_item = item

    def _hide_tooltip(self, event=None):
        """Hide tooltip."""
        if self._tooltip_timer:
            self.after_cancel(self._tooltip_timer)
            self._tooltip_timer = None
        self._tooltip_event = None
        self._tooltip_tree = None
        if hasattr(self, '_tooltip_event_item'):
            self._tooltip_event_item = None
        self._last_tooltip_item = None

        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None
            self._tooltip_window = None

    def _create_ui(self):
        """Create the pending tab UI."""
        # Control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Edit Selected",
            command=self.edit_sku
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Approve Selected",
            command=self.approve_sku
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Reject Selected",
            command=self.reject_sku
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(control_frame, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(
            control_frame,
            text="Refresh",
            command=self.load_pending
        ).pack(side=tk.LEFT, padx=5)

        # Filter by status
        ttk.Label(control_frame, text="Status:").pack(side=tk.LEFT, padx=5)
        self.status_filter = ttk.Combobox(
            control_frame,
            values=["All", "pending", "approved", "rejected"],
            state="readonly",
            width=12
        )
        self.status_filter.set("pending")
        self.status_filter.pack(side=tk.LEFT, padx=5)
        self.status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_pending())

        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("ID", "SKU", "SKU2", "Name", "URL", "Platform", "RoleID", "Role", "Submitted By", "Status"),
            show="headings"
        )
        for col in ("ID", "SKU", "SKU2", "Name", "URL", "Platform", "RoleID", "Role", "Submitted By", "Status"):
            self.tree.heading(col, text=col)

        self.tree.column("ID", width=40)
        self.tree.column("SKU", width=100)
        self.tree.column("SKU2", width=80)
        self.tree.column("Name", width=150)
        self.tree.column("URL", width=200)
        self.tree.column("Platform", width=80)
        self.tree.column("RoleID", width=100)
        self.tree.column("Role", width=80)
        self.tree.column("Submitted By", width=100)
        self.tree.column("Status", width=80)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Tooltip bindings
        self.tree.bind("<Motion>", lambda e: self._show_tooltip(e, self.tree))
        self.tree.bind("<Leave>", self._hide_tooltip)

    def load_pending(self):
        """Load pending SKUs from database."""
        status_filter = self.status_filter.get()

        if status_filter == "All":
            skus = self.app.db.get_all_pending_skus()
        else:
            skus = self.app.db.get_all_pending_skus()
            skus = [s for s in skus if s['status'] == status_filter]

        self.tree.delete(*self.tree.get_children())
        for s in skus:
            self.tree.insert("", tk.END, values=(
                s['id'],
                s['sku'],
                s.get('sku2', ''),
                s['name'],
                s.get('url', ''),
                s.get('platform', ''),
                s.get('role_id', ''),
                s.get('role', ''),
                s['submitted_by'],
                s['status']
            ))

    def approve_sku(self):
        """Approve selected SKU."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to approve.")
            return

        item = self.tree.item(selection[0])
        sku_id = item['values'][0]
        print(f"DEBUG approve_sku: sku_id={sku_id}, values={item['values']}")
        status = item['values'][9]  # Updated index for Status column
        print(f"DEBUG approve_sku: status='{status}'")

        if status != "pending":
            messagebox.showwarning("Already Reviewed", "This SKU has already been reviewed.")
            return

        # Get SKU data
        sku_data = self.app.db.get_sku_by_id(sku_id)
        print(f"DEBUG approve_sku: sku_data={sku_data}")
        if sku_data:
            # Validate platform and role_id
            platform = sku_data.get('platform', '').strip()
            role_id = sku_data.get('role_id', '').strip()
            print(f"DEBUG approve_sku: platform='{platform}', role_id='{role_id}'")

            if not platform or not role_id:
                messagebox.showwarning(
                    "Missing Fields",
                    f"Cannot approve SKU without Platform and Role ID.\n\n"
                    f"Platform: {'Missing' if not platform else platform}\n"
                    f"Role ID: {'Missing' if not role_id else role_id}\n\n"
                    f"Click 'Edit Selected' button to add Platform and Role ID, "
                    f"then try approving again."
                )
                return

            # Ask for confirmation
            if not messagebox.askyesno("Confirm Approve", f"Approve SKU {sku_data['sku']}?"):
                return

            # Approve
            self.app.db.approve_sku(sku_id, 0)
            self.load_pending()
            self.app.log_message(f"✅ Approved SKU: {sku_data['sku']} ({sku_data['name']})")
            messagebox.showinfo("Approved", f"SKU {sku_data['sku']} has been approved!")

            # Add to products sheet
            self._add_approved_to_products(sku_data)

    def reject_sku(self):
        """Reject selected SKU."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to reject.")
            return

        item = self.tree.item(selection[0])
        sku_id = item['values'][0]
        status = item['values'][9]  # Status column index

        if status != "pending":
            messagebox.showwarning("Already Reviewed", "This SKU has already been reviewed.")
            return

        sku_data = self.app.db.get_sku_by_id(sku_id)
        if sku_data:
            if messagebox.askyesno("Confirm Reject", f"Reject SKU {sku_data['sku']}?"):
                self.app.db.reject_sku(sku_id, 0)
                self.load_pending()
                self.app.log_message(f"❌ Rejected SKU: {sku_data['sku']} ({sku_data['name']})")

    def edit_sku(self):
        """Edit selected pending SKU."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to edit.")
            return

        item = self.tree.item(selection[0])
        sku_id = item['values'][0]
        status = item['values'][9]

        if status != "pending":
            messagebox.showwarning("Already Reviewed", "This SKU has already been reviewed and cannot be edited.")
            return

        sku_data = self.app.db.get_sku_by_id(sku_id)
        if not sku_data:
            return

        # Create edit dialog
        dialog = tk.Toplevel(self)
        dialog.title(f"Edit SKU: {sku_data['sku']}")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()

        # Fields
        ttk.Label(dialog, text="Platform:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        platform_var = tk.StringVar(value=sku_data.get('platform', ''))
        platform_combo = ttk.Combobox(dialog, textvariable=platform_var, width=30,
                                       values=["walmart", "gamestop", "amazon", "costco", "bestbuy", "popmart", "queueit", "indigo"])
        platform_combo.grid(row=0, column=1, padx=10, pady=5)

        ttk.Label(dialog, text="Role ID:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        roleid_var = tk.StringVar(value=sku_data.get('role_id', ''))
        ttk.Entry(dialog, textvariable=roleid_var, width=32).grid(row=1, column=1, padx=10, pady=5)

        ttk.Label(dialog, text="SKU2 (optional):").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        sku2_var = tk.StringVar(value=sku_data.get('sku2', ''))
        ttk.Entry(dialog, textvariable=sku2_var, width=32).grid(row=2, column=1, padx=10, pady=5)

        ttk.Label(dialog, text="Role (optional):").grid(row=3, column=0, sticky='w', padx=10, pady=5)
        role_var = tk.StringVar(value=sku_data.get('role', ''))
        ttk.Entry(dialog, textvariable=role_var, width=32).grid(row=3, column=1, padx=10, pady=5)

        def save():
            platform = platform_var.get().strip()
            role_id = roleid_var.get().strip()
            sku2 = sku2_var.get().strip()
            role = role_var.get().strip()

            if not platform:
                messagebox.showwarning("Required", "Platform is required.")
                return
            if not role_id:
                messagebox.showwarning("Required", "Role ID is required.")
                return

            # Update in database (role field stored in pending_skus for future use)
            self.app.db.update_pending_sku(sku_id, platform=platform, role_id=role_id, sku2=sku2, role=role)
            self.load_pending()
            self.app.log_message(f"✏️ Updated SKU: {sku_data['sku']} - Platform: {platform}, Role ID: {role_id}")
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Save", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def _add_approved_to_products(self, sku_data):
        """Add approved SKU to products sheet."""
        spreadsheet_id = self.app.db.get_config("google_sheets_id", "")
        if spreadsheet_id:
            try:
                self.app.sheets.append_product(
                    spreadsheet_id,
                    sku_data['sku'],
                    sku_data.get('sku2', ''),
                    sku_data['name'],
                    sku_data.get('url', ''),
                    sku_data.get('platform', ''),
                    sku_data.get('role_id', ''),
                    sku_data.get('role', '')
                )
                self.app.log_message(f"✅ Added {sku_data['sku']} to Google Sheets")
            except Exception as e:
                self.app.log_message(f"⚠️ Failed to add to sheets: {e}")

        # Also add to local products tab
        self.app.products_tab.sku_data[sku_data['sku'].upper()] = {
            'sku': sku_data['sku'].upper(),
            'sku2': sku_data.get('sku2', ''),
            'name': sku_data['name'],
            'url': sku_data.get('url', ''),
            'platform': sku_data.get('platform', ''),
            'roleid': sku_data.get('role_id', ''),
            'role': sku_data.get('role', '')
        }
        self.app.products_tab._populate_products_tree()
        self.app.log_message(f"✅ Added {sku_data['sku']} to local products")
