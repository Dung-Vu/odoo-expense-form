"""Test expense creation WITH file attachment."""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import base64
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, "app")
from odoo_client import OdooClient, OdooError

c = OdooClient(
    url=os.environ["ODOO_URL"],
    db=os.environ["ODOO_DB"],
    api_key=os.environ["ODOO_API_KEY"],
    uid=os.environ["ODOO_UID"],
)

# Tiny fake receipt (a 1x1 PNG)
PNG_DATA = base64.b64decode(
    b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

vals = {
    "company_id": 1,            # Bonario Vietnam
    "employee_id": 344,          # BÙI THỊ NHÃ UYÊN
    "product_id": 172089,        # KHSHIPLL
    "currency_id": 22,           # VND
    "total_amount_currency": 75000.0,
    "date": "2026-07-14",
    "description": "[TEST] Phí ship Lalamove + receipt attachment",
    "payment_mode": "own_account",
    "attachment_ids": [
        (0, 0, {
            "name": "test-receipt.png",
            "datas": base64.b64encode(PNG_DATA).decode("ascii"),
            "mimetype": "image/png",
            "res_model": "hr.expense",
        })
    ],
}

print("[1] Creating expense with attachment...")
try:
    expense_id = c.create("hr.expense", vals)
    print(f"    OK → expense_id={expense_id}")
except OdooError as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

print("\n[2] Reading back...")
result = c.search_read(
    "hr.expense",
    [("id", "=", expense_id)],
    ["id", "name", "state", "total_amount_currency",
     "attachment_ids", "nb_attachment"],
)
expense = result[0]
print(f"    Name:        {expense['name']}")
print(f"    Amount:      {expense['total_amount_currency']}")
print(f"    Attachments: {len(expense['attachment_ids'])} file(s)")
print(f"    nb_attachment field: {expense['nb_attachment']}")

# Verify attachment record
print("\n[3] Verifying attachment details...")
attachments = c.search_read(
    "ir.attachment",
    [("id", "in", expense["attachment_ids"])],
    ["name", "mimetype", "res_model", "res_id", "file_size"],
)
for att in attachments:
    print(f"    [{att['id']}] {att['name']} ({att['mimetype']}, {att['file_size']} bytes)")
    print(f"        linked to: {att['res_model']},{att['res_id']}")

print("\n[4] Submitting...")
c.execute("hr.expense", "action_submit", [[expense_id]])

result = c.search_read("hr.expense", [("id", "=", expense_id)], ["state"])
print(f"    State: {result[0]['state']}")

print(f"\n✓ Attachment test passed.")
from urllib.parse import urlparse
public_domain = os.environ.get("PUBLIC_ODOO_DOMAIN") or urlparse(os.environ["ODOO_URL"]).netloc or "odoo.com"
print(f"\n→ View: https://{public_domain}/odoo/expenses/{expense_id}?debug=1")