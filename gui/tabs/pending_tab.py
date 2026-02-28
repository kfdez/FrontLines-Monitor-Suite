"""Pending SKUs tab for admin approval."""
import tkinter as tk
from tkinter import ttk, messagebox


class PendingTab(ttk.Frame):
    """Tab for managing pending SKU submissions."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._create_ui()

    def _create_ui(self):
        """Create the pending tab UI."""
        # Control frame
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

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
            columns=("ID", "SKU", "Name", "URL", "Platform", "Submitted By", "Status", "Reviewed By"),
            show="headings"
        )
        for col in ("ID", "SKU", "Name", "URL", "Platform", "Submitted By", "Status", "Reviewed By"):
            self.tree.heading(col, text=col)

        self.tree.column("ID", width=40)
        self.tree.column("SKU", width=100)
        self.tree.column("Name", width=150)
        self.tree.column("URL", width=200)
        self.tree.column("Platform", width=80)
        self.tree.column("Submitted By", width=100)
        self.tree.column("Status", width=80)
        self.tree.column("Reviewed By", width=100)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

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
            reviewed_by = s.get('reviewed_by', '')
            if reviewed_by:
                try:
                    reviewed_by = int(reviewed_by)
                except (ValueError, TypeError):
                    pass

            self.tree.insert("", tk.END, values=(
                s['id'],
                s['sku'],
                s['name'],
                s.get('url', ''),
                s.get('platform', ''),
                s['submitted_by'],
                s['status'],
                reviewed_by
            ))

    def approve_sku(self):
        """Approve selected SKU."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to approve.")
            return

        item = self.tree.item(selection[0])
        sku_id = item['values'][0]
        status = item['values'][6]

        if status != "pending":
            messagebox.showwarning("Already Reviewed", "This SKU has already been reviewed.")
            return

        # Get SKU data
        sku_data = self.app.db.get_sku_by_id(sku_id)
        if sku_data:
            # Approve
            self.app.db.approve_sku(sku_id, 0)  # 0 = admin ID (could be from bot)
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
        status = item['values'][6]

        if status != "pending":
            messagebox.showwarning("Already Reviewed", "This SKU has already been reviewed.")
            return

        sku_data = self.app.db.get_sku_by_id(sku_id)
        if sku_data:
            if messagebox.askyesno("Confirm Reject", f"Reject SKU {sku_data['sku']}?"):
                self.app.db.reject_sku(sku_id, 0)
                self.load_pending()
                self.app.log_message(f"❌ Rejected SKU: {sku_data['sku']} ({sku_data['name']})")

    def _add_approved_to_products(self, sku_data):
        """Add approved SKU to products sheet."""
        spreadsheet_id = self.app.db.get_config("spreadsheet_id", "")
        if spreadsheet_id:
            try:
                self.app.sheets.append_product(
                    spreadsheet_id,
                    "A:E",
                    sku_data['sku'],
                    sku_data['name'],
                    sku_data.get('url', ''),
                    sku_data.get('role_id', ''),
                    sku_data.get('platform', '')
                )
                print(f"✅ Added {sku_data['sku']} to products sheet")
            except Exception as e:
                print(f"⚠️ Failed to add to sheets: {e}")
