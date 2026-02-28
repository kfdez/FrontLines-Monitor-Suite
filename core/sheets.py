"""Google Sheets integration for products."""
import os
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build


class SheetsManager:
    def __init__(self, credentials_path: str = "credentials.json"):
        self.credentials_path = credentials_path
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticate with Google Sheets API."""
        if not os.path.exists(self.credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_path}")

        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly',
                    'https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=credentials)

    def get_products(self, spreadsheet_id: str, range_name: str = "A:Z") -> List[Dict[str, Any]]:
        """Read products from Google Sheets.

        Expected columns: SKU, Name, URL, RoleID, Platform
        Returns list of dicts with product data.
        """
        if not spreadsheet_id:
            return []

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()

            values = result.get('values', [])
            if not values:
                return []

            # First row is headers - normalize by removing spaces and special chars
            headers = [v.strip().lower().replace(" ", "").replace("/", "").replace("(", "").replace(")", "").replace("-", "") for v in values[0]]
            # Map common header variations to standard names
            header_map = {}
            for h in headers:
                if h == 'sku':
                    header_map[h] = 'sku'
                elif h == 'sku2':
                    header_map[h] = 'sku2'
                elif h == 'name':
                    header_map[h] = 'name'
                elif h in ['url', 'link', 'offerid', 'offeridifapplicable']:
                    header_map[h] = 'url'
                elif 'roleid' in h:
                    header_map[h] = 'roleid'
                elif h == 'role':
                    header_map[h] = 'role'
                elif h in ['platform', 'sitestore', 'store']:
                    header_map[h] = 'platform'
                # Skip: monitor, checkout, stellarinput, lastchecked, track, limit, qty
            products = []

            # Track row index (starting at row 2 since row 1 is headers)
            row_idx = 2
            for row in values[1:]:
                if not row or not row[0]:
                    row_idx += 1
                    continue

                product = {'_row': row_idx}  # Store row index for updates
                for i, header in enumerate(headers):
                    if i < len(row):
                        # Use mapped header name if available
                        key = header_map.get(header, header)
                        product[key] = row[i].strip()
                    else:
                        key = header_map.get(header, header)
                        product[key] = ""

                # Normalize SKU to uppercase
                if 'sku' in product:
                    product['sku'] = product['sku'].upper()

                products.append(product)
                row_idx += 1

            return products

        except Exception as e:
            print(f"Error reading from Google Sheets: {e}")
            return []

    def get_products_dict(self, spreadsheet_id: str) -> Dict[str, Dict[str, Any]]:
        """Get products as a dictionary keyed by SKU."""
        products = self.get_products(spreadsheet_id)
        return {p['sku']: p for p in products if 'sku' in p}

    def write_products(
        self,
        spreadsheet_id: str,
        range_name: str,
        products: List[Dict[str, Any]]
    ) -> bool:
        """Write products to Google Sheets."""
        if not spreadsheet_id or not products:
            return False

        try:
            # Prepare headers
            headers = ["SKU", "Name", "URL", "RoleID", "Platform"]
            values = [headers]

            # Prepare rows
            for p in products:
                values.append([
                    p.get('sku', ''),
                    p.get('name', ''),
                    p.get('url', ''),
                    p.get('roleid', ''),
                    p.get('platform', '')
                ])

            body = {
                'values': values
            }

            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return True

        except Exception as e:
            print(f"Error writing to Google Sheets: {e}")
            return False

    def append_product(
        self,
        spreadsheet_id: str,
        sheet_range: str,
        sku: str,
        name: str,
        url: str = "",
        role_id: str = "",
        platform: str = ""
    ) -> bool:
        """Append a single product to the sheet."""
        if not spreadsheet_id:
            return False

        try:
            # First get the next empty row
            result = self.service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=sheet_range
            ).execute()

            values = result.get('values', [])
            next_row = len(values) + 1

            body = {
                'values': [[sku, name, url, role_id, platform]]
            }

            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"A{next_row}:E{next_row}",
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return True

        except Exception as e:
            print(f"Error appending to Google Sheets: {e}")
            return False

    def update_product(
        self,
        spreadsheet_id: str,
        row_index: int,
        sku: str,
        sku2: str = "",
        name: str = "",
        url: str = "",
        platform: str = "",
        role_id: str = "",
        role: str = ""
    ) -> bool:
        """Update a product at a specific row."""
        if not spreadsheet_id:
            return False

        try:
            body = {
                'values': [[sku, sku2, name, url, platform, "", role_id, role]]
            }

            self.service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"A{row_index}:H{row_index}",
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()

            return True

        except Exception as e:
            print(f"Error updating Google Sheets: {e}")
            return False
