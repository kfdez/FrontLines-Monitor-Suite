"""Products tab with in-app editing and pending SKUs."""
import tkinter as tk
from tkinter import ttk, messagebox
import tkinter.filedialog as fd


class ProductsTab(ttk.Frame):
    """Products tab with sub-tabs for Products and Pending SKUs."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._tooltip_window = None
        self._tooltip_timer = None
        self._tooltip_event = None
        self._tooltip_tree = None
        self._last_tooltip_item = None

        # SKU data dictionary
        self.sku_data = {}

        # Create notebook for sub-tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Products sub-tab
        self.products_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.products_frame, text="SKUs")

        # Pending sub-tab
        self.pending_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.pending_frame, text="Pending SKUs")

        # Platform Mapping sub-tab
        self.platforms_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.platforms_frame, text="Platforms")

        # Create UI for each tab
        self._create_products_ui()
        self._create_pending_ui()
        self._create_platforms_ui()

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

    def _create_products_ui(self):
        """Create products sub-tab UI."""
        # Control frame
        control_frame = ttk.Frame(self.products_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Spreadsheet ID:").pack(side=tk.LEFT)
        self.spreadsheet_id_var = tk.StringVar()
        self.spreadsheet_id_entry = ttk.Entry(
            control_frame,
            textvariable=self.spreadsheet_id_var,
            width=40
        )
        self.spreadsheet_id_entry.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Load from Sheets",
            command=self.load_products
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Add Product",
            command=self.add_product
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Edit Product",
            command=self.edit_product
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Delete Product",
            command=self.delete_product
        ).pack(side=tk.LEFT, padx=5)

        # Filter
        filter_frame = ttk.Frame(self.products_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add('write', self.filter_products)
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # Treeview
        tree_frame = ttk.Frame(self.products_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("SKU", "SKU2", "Name", "URL", "Platform", "RoleID", "Role"),
            show="headings",
            height=15
        )
        # Add sorting
        self.sort_col = "SKU"
        self.sort_reverse = False

        for col in ("SKU", "SKU2", "Name", "URL", "Platform", "RoleID", "Role"):
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_treeview(c))
            self.tree.column(col, width=150)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Tooltip bindings
        self.tree.bind("<Motion>", lambda e: self._show_tooltip(e, self.tree))
        self.tree.bind("<Leave>", self._hide_tooltip)

        # Load saved spreadsheet ID
        saved_id = self.app.db.get_config("spreadsheet_id", "")
        self.spreadsheet_id_var.set(saved_id)

    def _create_pending_ui(self):
        """Create pending SKUs sub-tab UI."""
        # Control frame
        control_frame = ttk.Frame(self.pending_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Edit Selected",
            command=self.edit_pending_sku
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
        ttk.Label(control_frame, text="Status:").pack(side=tk.LEFT, padx=10)
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
        tree_frame = ttk.Frame(self.pending_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.pending_tree = ttk.Treeview(
            tree_frame,
            columns=("ID", "SKU", "SKU2", "Name", "URL", "Platform", "RoleID", "Role", "Submitted By", "Status"),
            show="headings"
        )
        for col in ("ID", "SKU", "SKU2", "Name", "URL", "Platform", "RoleID", "Role", "Submitted By", "Status"):
            self.pending_tree.heading(col, text=col)

        self.pending_tree.column("ID", width=40)
        self.pending_tree.column("SKU", width=100)
        self.pending_tree.column("SKU2", width=80)
        self.pending_tree.column("Name", width=150)
        self.pending_tree.column("URL", width=200)
        self.pending_tree.column("Platform", width=80)
        self.pending_tree.column("RoleID", width=100)
        self.pending_tree.column("Role", width=80)
        self.pending_tree.column("Submitted By", width=100)
        self.pending_tree.column("Status", width=80)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.pending_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.pending_tree.xview)
        self.pending_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.pending_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Tooltip bindings
        self.pending_tree.bind("<Motion>", lambda e: self._show_tooltip(e, self.pending_tree))
        self.pending_tree.bind("<Leave>", self._hide_tooltip)

    def load_products(self):
        """Load products from Google Sheets."""
        spreadsheet_id = self.spreadsheet_id_var.get().strip()
        if not spreadsheet_id:
            messagebox.showwarning("No Spreadsheet", "Please enter a spreadsheet ID.")
            return

        # Save spreadsheet ID
        self.app.db.set_config("google_sheets_id", spreadsheet_id)

        try:
            products = self.app.sheets.get_products(spreadsheet_id)
            self.sku_data = {p['sku']: p for p in products if 'sku' in p}
            self._populate_products_tree()
            self.app.log_message(f"✅ Loaded {len(products)} products from Sheets")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load products: {e}")

    def _populate_products_tree(self, filter_text=""):
        """Populate products treeview."""
        self.tree.delete(*self.tree.get_children())

        for sku, data in self._get_sorted_items(filter_text):
            self.tree.insert("", tk.END, values=(
                sku,
                data.get('sku2', ''),
                data.get('name', ''),
                data.get('url', ''),
                data.get('platform', ''),
                data.get('roleid', ''),
                data.get('role', '')
            ))

    def sort_treeview(self, col):
        """Sort treeview by column."""
        if self.sort_col == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_col = col
            self.sort_reverse = False

        # Re-sort and repopulate
        self._populate_products_tree(self.filter_var.get())

    def _get_sorted_items(self, filter_text=""):
        """Get sorted items from sku_data."""
        items = []
        filter_text = filter_text.lower()

        for sku, data in self.sku_data.items():
            if filter_text and filter_text not in sku.lower():
                if filter_text not in data.get('name', '').lower():
                    continue
            items.append((sku, data))

        # Sort
        def get_sort_key(item):
            sku, data = item
            if self.sort_col == "SKU":
                return sku.upper()
            elif self.sort_col == "SKU2":
                return data.get('sku2', '').upper()
            elif self.sort_col == "Name":
                return data.get('name', '').lower()
            elif self.sort_col == "URL":
                return data.get('url', '').lower()
            elif self.sort_col == "RoleID":
                return data.get('roleid', '').lower()
            elif self.sort_col == "Role":
                return data.get('role', '').lower()
            elif self.sort_col == "Platform":
                return data.get('platform', '').lower()
            return sku.upper()

        items.sort(key=get_sort_key, reverse=self.sort_reverse)
        return items

    def filter_products(self, *args):
        """Filter products based on search text."""
        self._populate_products_tree(self.filter_var.get())

    def add_product(self):
        """Add a new product."""
        dialog = ProductDialog(self, "Add Product")
        if dialog.result:
            sku = dialog.result['sku'].upper()
            self.sku_data[sku] = dialog.result
            self._populate_products_tree()

            # Save to sheets
            spreadsheet_id = self.spreadsheet_id_var.get()
            if spreadsheet_id:
                self.app.sheets.append_product(
                    spreadsheet_id,
                    "A:Z",
                    sku,
                    dialog.result['name'],
                    dialog.result.get('url', ''),
                    dialog.result.get('roleid', ''),
                    dialog.result.get('platform', '')
                )
                self.app.log_message(f"✅ Added product: {sku}")

    def edit_product(self):
        """Edit selected product."""
        try:
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a product to edit.")
                return

            item = self.tree.item(selection[0])
            sku = item['values'][0]

            current = self.sku_data.get(sku, {})
            row_index = current.get('_row', 0)

            dialog = ProductDialog(self, "Edit Product", current)
            self.wait_window(dialog)

            if dialog.result:
                new_sku = dialog.result['sku'].upper()

                # Update local data - preserve _row if it exists
                if new_sku != sku:
                    del self.sku_data[sku]

                dialog.result['_row'] = current.get('_row', 0)
                self.sku_data[new_sku] = dialog.result
                self._populate_products_tree()

                # Update Google Sheet
                spreadsheet_id = self.spreadsheet_id_var.get()
                if spreadsheet_id and row_index:
                    self.app.sheets.update_product(
                        spreadsheet_id,
                        row_index,
                        new_sku,
                        dialog.result.get('sku2', ''),
                        dialog.result.get('name', ''),
                        dialog.result.get('url', ''),
                        dialog.result.get('platform', ''),
                        dialog.result.get('roleid', ''),
                        dialog.result.get('role', '')
                    )
                    self.app.log_message(f"✏️ Updated: {new_sku}")
        except Exception as e:
            self.app.log_message(f"ERROR: {e}")

    def delete_product(self):
        """Delete selected product."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a product to delete.")
            return

        item = self.tree.item(selection[0])
        sku = item['values'][0]

        if messagebox.askyesno("Confirm Delete", f"Delete product {sku}?"):
            del self.sku_data[sku]
            self._populate_products_tree()
            self.app.log_message(f"🗑️ Deleted product: {sku}")

    # ============ PENDING SKU METHODS ============

    def load_pending(self):
        """Load pending SKUs."""
        status_filter = self.status_filter.get()

        if status_filter == "All":
            skus = self.app.db.get_all_pending_skus()
        else:
            skus = self.app.db.get_all_pending_skus()
            skus = [s for s in skus if s['status'] == status_filter]

        self.pending_tree.delete(*self.pending_tree.get_children())
        for s in skus:
            self.pending_tree.insert("", tk.END, values=(
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
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to approve.")
            return

        item = self.pending_tree.item(selection[0])
        sku_id = item['values'][0]
        status = item['values'][9]  # Status column index

        if status != "pending":
            messagebox.showwarning("Already Reviewed", "This SKU has already been reviewed.")
            return

        sku_data = self.app.db.get_sku_by_id(sku_id)
        if sku_data:
            # Validate platform and role_id
            platform = sku_data.get('platform', '').strip()
            role_id = sku_data.get('role_id', '').strip()

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

            if not messagebox.askyesno("Confirm Approve", f"Approve SKU {sku_data['sku']}?"):
                return

            self.app.db.approve_sku(sku_id, 0)
            self.load_pending()
            self.app.log_message(f"✅ Approved SKU: {sku_data['sku']} ({sku_data['name']})")
            messagebox.showinfo("Approved", f"SKU {sku_data['sku']} has been approved!")
            self._add_approved_to_products(sku_data)

    def reject_sku(self):
        """Reject selected SKU."""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to reject.")
            return

        item = self.pending_tree.item(selection[0])
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

    def edit_pending_sku(self):
        """Edit selected pending SKU."""
        selection = self.pending_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a SKU to edit.")
            return

        item = self.pending_tree.item(selection[0])
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
        dialog.geometry("400x320")
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
                self.app.log_message(f"📝 Added {sku_data['sku']} to products sheet")
            except Exception as e:
                self.app.log_message(f"⚠️ Failed to add to sheets: {e}")

        # Also add to local products
        self.sku_data[sku_data['sku'].upper()] = {
            'sku': sku_data['sku'].upper(),
            'sku2': sku_data.get('sku2', ''),
            'name': sku_data['name'],
            'url': sku_data.get('url', ''),
            'platform': sku_data.get('platform', ''),
            'roleid': sku_data.get('role_id', ''),
            'role': sku_data.get('role', '')
        }
        self._populate_products_tree()
        self.app.log_message(f"✅ Added {sku_data['sku']} to local products")

    # ============ PLATFORM MAPPING METHODS ============

    def _create_platforms_ui(self):
        """Create platform-site mapping sub-tab UI."""
        # Control frame
        control_frame = ttk.Frame(self.platforms_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Add Platform",
            command=self.add_platform
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Edit Platform",
            command=self.edit_platform
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Delete Platform",
            command=self.delete_platform
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            control_frame,
            text="Refresh",
            command=self.load_platforms
        ).pack(side=tk.LEFT, padx=5)

        # Treeview
        tree_frame = ttk.Frame(self.platforms_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.platforms_tree = ttk.Treeview(
            tree_frame,
            columns=("ID", "Platform", "Site URL"),
            show="headings"
        )
        for col in ("ID", "Platform", "Site URL"):
            self.platforms_tree.heading(col, text=col)

        self.platforms_tree.column("ID", width=40)
        self.platforms_tree.column("Platform", width=150)
        self.platforms_tree.column("Site URL", width=300)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.platforms_tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.platforms_tree.xview)
        self.platforms_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.platforms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # Tooltip bindings
        self.platforms_tree.bind("<Motion>", lambda e: self._show_tooltip(e, self.platforms_tree))
        self.platforms_tree.bind("<Leave>", self._hide_tooltip)

    def load_platforms(self):
        """Load platform-site mappings."""
        platforms = self.app.db.get_all_platform_sites()
        self.platforms_tree.delete(*self.platforms_tree.get_children())
        for p in platforms:
            self.platforms_tree.insert("", tk.END, values=(
                p['id'],
                p['platform'],
                p['site_url']
            ))

    def add_platform(self):
        """Add a new platform mapping."""
        dialog = PlatformDialog(self, "Add Platform")
        if dialog.result:
            self.app.db.add_platform_site(dialog.result['platform'], dialog.result['site_url'])
            self.load_platforms()
            self.app.log_message(f"✅ Added platform: {dialog.result['platform']} -> {dialog.result['site_url']}")

    def edit_platform(self):
        """Edit selected platform mapping."""
        selection = self.platforms_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a platform to edit.")
            return

        item = self.platforms_tree.item(selection[0])
        platform_id = item['values'][0]
        platform = item['values'][1]
        site_url = item['values'][2]

        current = {'id': platform_id, 'platform': platform, 'site_url': site_url}
        dialog = PlatformDialog(self, "Edit Platform", current)
        self.wait_window(dialog)

        if dialog.result:
            self.app.db.update_platform_site(
                platform_id,
                dialog.result['platform'],
                dialog.result['site_url']
            )
            self.load_platforms()
            self.app.log_message(f"✏️ Updated platform: {dialog.result['platform']} -> {dialog.result['site_url']}")

    def delete_platform(self):
        """Delete selected platform mapping."""
        selection = self.platforms_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a platform to delete.")
            return

        item = self.platforms_tree.item(selection[0])
        platform_id = item['values'][0]
        platform = item['values'][1]

        if messagebox.askyesno("Confirm Delete", f"Delete platform mapping for '{platform}'?"):
            self.app.db.delete_platform_site(platform_id)
            self.load_platforms()
            self.app.log_message(f"🗑️ Deleted platform: {platform}")


class ProductDialog(tk.Toplevel):
    """Dialog for adding/editing products."""

    def __init__(self, parent, title, current=None):
        super().__init__(parent)
        self.title(title)
        self.result = None

        # Center on screen after window is drawn
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        dialog_w = 450
        dialog_h = 300
        x = (screen_w - dialog_w) // 2
        y = (screen_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        self.resizable(False, False)

        current = current or {}

        # Fields
        ttk.Label(self, text="SKU:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.sku_var = tk.StringVar(value=current.get('sku', ''))
        ttk.Entry(self, textvariable=self.sku_var, width=40).grid(
            row=0, column=1, padx=5, pady=5)

        ttk.Label(self, text="SKU2:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.sku2_var = tk.StringVar(value=current.get('sku2', ''))
        ttk.Entry(self, textvariable=self.sku2_var, width=40).grid(
            row=1, column=1, padx=5, pady=5)

        ttk.Label(self, text="Name:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.name_var = tk.StringVar(value=current.get('name', ''))
        ttk.Entry(self, textvariable=self.name_var, width=40).grid(
            row=2, column=1, padx=5, pady=5)

        ttk.Label(self, text="URL:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.url_var = tk.StringVar(value=current.get('url', ''))
        ttk.Entry(self, textvariable=self.url_var, width=40).grid(
            row=3, column=1, padx=5, pady=5)

        ttk.Label(self, text="Platform:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.platform_var = tk.StringVar(value=current.get('platform', ''))
        ttk.Combobox(self, textvariable=self.platform_var, width=38,
                      values=["walmart", "gamestop", "amazon", "costco",
                              "bestbuy", "popmart", "queueit", "indigo"]).grid(
            row=4, column=1, padx=5, pady=5)

        ttk.Label(self, text="Role ID:").grid(row=5, column=0, sticky='w', padx=5, pady=5)
        self.roleid_var = tk.StringVar(value=current.get('roleid', ''))
        ttk.Entry(self, textvariable=self.roleid_var, width=40).grid(
            row=5, column=1, padx=5, pady=5)

        ttk.Label(self, text="Role:").grid(row=6, column=0, sticky='w', padx=5, pady=5)
        self.role_var = tk.StringVar(value=current.get('role', ''))
        ttk.Entry(self, textvariable=self.role_var, width=40).grid(
            row=6, column=1, padx=5, pady=5)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.grab_set()

    def save(self):
        if not self.sku_var.get().strip():
            messagebox.showwarning("Required", "SKU is required.")
            return
        self.result = {
            'sku': self.sku_var.get().strip(),
            'sku2': self.sku2_var.get().strip(),
            'name': self.name_var.get().strip(),
            'url': self.url_var.get().strip(),
            'roleid': self.roleid_var.get().strip(),
            'role': self.role_var.get().strip(),
            'platform': self.platform_var.get().strip()
        }
        self.destroy()


class PlatformDialog(tk.Toplevel):
    """Dialog for adding/editing platform mappings."""

    def __init__(self, parent, title, current=None):
        super().__init__(parent)
        self.title(title)
        self.result = None

        # Center on screen
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        dialog_w = 400
        dialog_h = 180
        x = (screen_w - dialog_w) // 2
        y = (screen_h - dialog_h) // 2
        self.geometry(f"{dialog_w}x{dialog_h}+{x}+{y}")
        self.resizable(False, False)

        current = current or {}

        # Fields
        ttk.Label(self, text="Platform Name:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.platform_var = tk.StringVar(value=current.get('platform', ''))
        ttk.Entry(self, textvariable=self.platform_var, width=35).grid(
            row=0, column=1, padx=5, pady=5)

        ttk.Label(self, text="Site URL:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.site_url_var = tk.StringVar(value=current.get('site_url', ''))
        ttk.Entry(self, textvariable=self.site_url_var, width=35).grid(
            row=1, column=1, padx=5, pady=5)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

        self.grab_set()

    def save(self):
        if not self.platform_var.get().strip():
            messagebox.showwarning("Required", "Platform name is required.")
            return
        if not self.site_url_var.get().strip():
            messagebox.showwarning("Required", "Site URL is required.")
            return
        self.result = {
            'platform': self.platform_var.get().strip(),
            'site_url': self.site_url_var.get().strip()
        }
        self.destroy()
