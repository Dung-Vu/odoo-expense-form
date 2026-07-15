"""Quick connectivity test against Odoo testing1307."""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, "app")
from odoo_client import OdooClient, OdooError

print(f"ODOO_URL  = {os.environ['ODOO_URL']}")
print(f"ODOO_DB   = {os.environ['ODOO_DB']}")
print(f"ODOO_UID  = {os.environ['ODOO_UID']}")
print(f"API_KEY   = {os.environ['ODOO_API_KEY'][:8]}...{os.environ['ODOO_API_KEY'][-4:]}")
print()

c = OdooClient(
    url=os.environ["ODOO_URL"],
    db=os.environ["ODOO_DB"],
    api_key=os.environ["ODOO_API_KEY"],
    uid=os.environ["ODOO_UID"],
)

# Test 1: authenticate
print("[1] Authenticating...")
try:
    uid = c.authenticate()
    print(f"    OK -> uid={uid}")
except OdooError as e:
    print(f"    FAIL: {e}")
    sys.exit(1)

# Test 2: read companies
print("\n[2] Fetching res.company...")
companies = c.search_read("res.company", [], ["id", "name"])
for co in companies:
    print(f"    [{co['id']}] {co['name']}")

# Test 3: read employees (filter_for_expense)
print("\n[3] Fetching hr.employee (filter_for_expense=True)...")
employees = c.search_read(
    "hr.employee",
    [("filter_for_expense", "=", True)],
    ["id", "name", "company_id"],
    limit=10,
)
for emp in employees:
    co = emp["company_id"][1] if emp["company_id"] else "-"
    print(f"    [{emp['id']}] {emp['name']} ({co})")
print(f"    ... ({len(employees)} shown, may be more)")

# Test 4: read expense categories
print("\n[4] Fetching product.product (can_be_expensed=True)...")
cats = c.search_read(
    "product.product",
    [("can_be_expensed", "=", True)],
    ["id", "name", "default_code"],
    order="default_code, name",
)
for cat in cats:
    code = cat["default_code"] or "-"
    print(f"    [{cat['id']}] {code} - {cat['name']}")
print(f"    ... ({len(cats)} shown)")

# Test 5: read currencies
print("\n[5] Fetching active res.currency...")
curs = c.search_read(
    "res.currency", [("active", "=", True)], ["id", "name", "symbol"], order="name"
)
for cur in curs:
    print(f"    [{cur['id']}] {cur['name']} ({cur['symbol']})")

# Test 6: read vendors
print("\n[6] Fetching vendors (supplier_rank > 0)...")
vendors = c.search_read(
    "res.partner",
    [("supplier_rank", ">", 0)],
    ["id", "name"],
    order="name",
    limit=10,
)
for v in vendors:
    print(f"    [{v['id']}] {v['name']}")
print(f"    ... ({len(vendors)} shown)")

# Test 7: check broker groups
print("\n[7] Checking broker's groups...")
try:
    user_data = c.search_read(
        "res.users",
        [("id", "=", uid)],
        ["name", "group_ids"],
    )
    if user_data:
        user_groups = user_data[0]["group_ids"]
        print(f"    User: {user_data[0]['name']}")
        # Check for hr_expense groups
        group_data = c.search_read(
            "res.groups",
            [("id", "in", user_groups)],
            ["name", "full_name"],
        )
        print(f"    HR Expense groups:")
        expense_groups = []
        for g in group_data:
            name = g.get("full_name") or g.get("name") or ""
            if "expense" in name.lower() or "chi phí" in name.lower():
                expense_groups.append(name)
                print(f"      - {name}")
        is_manager = any("Manager" in name or "Administrator" in name or "Quản trị" in name for name in expense_groups)
        print(f"    Has 'Manager' role: {is_manager}")
except Exception as e:
    print(f"    Could not read group details: {e}")

print("\nAll connectivity tests passed.")