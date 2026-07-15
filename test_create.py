"""Full create + submit test against testing1307."""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

load_dotenv()

# Safety check: Only run on test environments to prevent cluttering production data
odoo_url = os.environ.get("ODOO_URL", "")
odoo_db = os.environ.get("ODOO_DB", "")
if "testing" not in odoo_url.lower() and "testing" not in odoo_db.lower():
    print("ERROR: Test scripts are restricted to Odoo TEST servers (e.g. testing1307.odoo.com).")
    print(f"Current ODOO_URL: {odoo_url}")
    print("Aborting execution to protect production database.")
    sys.exit(1)

sys.path.insert(0, "app")
from odoo_client import OdooClient, OdooError

c = OdooClient(
    url=os.environ["ODOO_URL"],
    db=os.environ["ODOO_DB"],
    api_key=os.environ["ODOO_API_KEY"],
    uid=os.environ["ODOO_UID"],
)

# Test inputs
COMPANY_ID = 1       # Bonario Vietnam
EMPLOYEE_ID = 344     # BÙI THỊ NHÃ UYÊN
PRODUCT_ID = 172089   # KHSHIPLL · [KH]-Phí ship Lalamove
CURRENCY_ID = 22      # VND
AMOUNT = 50000.0
DATE = "2026-07-14"
DESCRIPTION = "[TEST] Phí ship Lalamove - automated test"

vals = {
    "company_id": COMPANY_ID,
    "employee_id": EMPLOYEE_ID,
    "product_id": PRODUCT_ID,
    "currency_id": CURRENCY_ID,
    "total_amount_currency": AMOUNT,
    "date": DATE,
    "description": DESCRIPTION,
    "payment_mode": "own_account",
}

print("[1] Creating draft expense...")
try:
    expense_id = c.create("hr.expense", vals)
    print(f"    OK → expense_id={expense_id}")
except OdooError as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

print("\n[2] Reading back the draft expense...")
result = c.search_read(
    "hr.expense",
    [("id", "=", expense_id)],
    ["id", "name", "state", "company_id", "employee_id", "total_amount_currency",
     "currency_id", "product_id", "payment_mode", "date", "create_uid"],
)
expense = result[0]
print(f"    ID:           {expense['id']}")
print(f"    Name:         {expense['name']}")
print(f"    State:        {expense['state']}")
print(f"    Company:      {expense['company_id'][1] if expense['company_id'] else '—'}")
print(f"    Employee:     {expense['employee_id'][1] if expense['employee_id'] else '—'}")
print(f"    Product:      {expense['product_id'][1] if expense['product_id'] else '—'}")
print(f"    Amount:       {expense['total_amount_currency']} {expense['currency_id'][1]}")
print(f"    Payment mode: {expense['payment_mode']}")
print(f"    Date:         {expense['date']}")
print(f"    Create UID:   {expense['create_uid'][1] if expense['create_uid'] else '—'}")

print("\n[3] Calling action_submit()...")
try:
    c.execute("hr.expense", "action_submit", [[expense_id]])
    print("    OK")
except OdooError as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

print("\n[4] Re-reading to verify state changed...")
result = c.search_read(
    "hr.expense",
    [("id", "=", expense_id)],
    ["id", "state", "approval_state", "manager_id", "message_follower_ids"],
)
expense = result[0]
print(f"    State:          {expense['state']}")
print(f"    Approval state: {expense['approval_state']}")
print(f"    Manager:        {expense['manager_id'][1] if expense['manager_id'] else '(empty - will auto-set)'}")
print(f"    Followers:      {len(expense['message_follower_ids'])} persons")

print(f"\n✓ Full test passed.")
from urllib.parse import urlparse
public_domain = os.environ.get("PUBLIC_ODOO_DOMAIN") or urlparse(os.environ["ODOO_URL"]).netloc or "odoo.com"
print(f"\n→ View in Odoo: https://{public_domain}/odoo/expenses/{expense_id}?debug=1")