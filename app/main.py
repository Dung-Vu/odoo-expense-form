"""Flask app for Odoo expense submission.

Routes:
    GET  /         - render form with dropdowns
    POST /submit   - create + submit expense via Odoo JSON-RPC
    GET  /health   - liveness probe
"""

import base64
import logging
import os
import time
from datetime import date
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from .odoo_client import OdooClient, OdooError

load_dotenv()


def _int_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip().lstrip("-").isdigit()]


# Whitelist configuration (overridable via .env)
COMPANY_IDS = _int_list(os.environ.get("COMPANY_IDS", "1,11"))
EMPLOYEE_NAME_KEYWORDS = [w.strip() for w in os.environ.get("EMPLOYEE_NAME_KEYWORDS", "Phước,Thành,Công,Biên,Chinh").split(",") if w.strip()]
# Whitelisted expense category IDs (product.product). Use Odoo IDs — stable and
# unambiguous. See test_categories.py or run:
#   python -c "from app.odoo_client import OdooClient; ..."
CATEGORY_IDS = _int_list(os.environ.get(
    "CATEGORY_IDS",
    "26807,26758,157600,26808,27054,148975,172089,119083,170275",
))
# Allowed currency codes (res.currency.name). If only 1 matches, the form
# hides the currency dropdown and submits it as a hidden field.
CURRENCY_CODES = [w.strip() for w in os.environ.get("CURRENCY_CODES", "VND").split(",") if w.strip()]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("odoo-expense-form")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

_STATE_LABELS = {
    "draft": "Nháp",
    "submitted": "Đã gửi",
    "approved": "Đã duyệt",
    "refused": "Từ chối",
    "posted": "Đã ghi sổ",
    "in_payment": "Đang thanh toán",
    "paid": "Đã thanh toán",
}


@app.template_filter("state_label")
def _state_label(state: str) -> str:
    return _STATE_LABELS.get(state, state)


odoo = OdooClient(
    url=os.environ["ODOO_URL"],
    db=os.environ["ODOO_DB"],
    api_key=os.environ["ODOO_API_KEY"],
    uid=os.environ["ODOO_UID"],
)

PUBLIC_ODOO_DOMAIN = urlparse(os.environ["ODOO_URL"]).netloc or "odoo.com"

# Dropdown cache (5 min)
_cache = {"data": None, "expires": 0}
CACHE_TTL = 300


def _last_word(name: str) -> str:
    """Return the last whitespace-delimited token of `name`, lowercased.
    Used to match Vietnamese names by given name (the last word)."""
    parts = (name or "").strip().split()
    return parts[-1].lower() if parts else ""


def get_dropdowns():
    """Load dropdown data from Odoo with 5-min in-memory cache."""
    now = time.time()
    if _cache["data"] and _cache["expires"] > now:
        return _cache["data"]

    log.info(
        "Refreshing dropdown cache: companies=%s, employees_keywords=%s, category_ids=%s, currencies=%s",
        COMPANY_IDS, EMPLOYEE_NAME_KEYWORDS, CATEGORY_IDS, CURRENCY_CODES,
    )

    # Companies: only whitelisted IDs
    companies = odoo.search_read(
        "res.company", [("id", "in", COMPANY_IDS)], ["id", "name"], order="name"
    )
    company_ids = [c["id"] for c in companies]

    # Employees: fetch ALL (no company filter so we see Ordinaire),
    # then filter in Python by last-word match against EMPLOYEE_NAME_KEYWORDS.
    # This handles multi-company duplicates (same person in Bonario + Ordinaire)
    # AND avoids the `filter_for_expense` field which is not consistently set.
    all_employees = odoo.search_read(
        "hr.employee",
        [("company_id", "in", company_ids)],
        ["id", "name", "company_id"],
        order="company_id, name",
    )
    keywords_lower = {k.lower() for k in EMPLOYEE_NAME_KEYWORDS}
    employees = [
        e for e in all_employees
        if _last_word(e["name"]) in keywords_lower
    ]

    # Categories: filter by exact product.product IDs from CATEGORY_IDS.
    # Simple, fast, unambiguous — the complex OR-of-keywords domain didn't
    # behave well for Odoo's Polish-notation parser at scale.
    categories = odoo.search_read(
        "product.product",
        [("can_be_expensed", "=", True), ("id", "in", CATEGORY_IDS)],
        ["id", "name", "default_code"],
        order="default_code, name",
    )

    data = {
        "companies": companies,
        "employees": employees,
        "categories": categories,
        "currencies": odoo.search_read(
            "res.currency",
            [("active", "=", True), ("name", "in", CURRENCY_CODES)],
            ["id", "name", "symbol"],
            order="name",
        ),
        "vendors": odoo.search_read(
            "res.partner",
            [("supplier_rank", ">", 0), ("company_id", "in", company_ids)],
            ["id", "name", "company_id"],
            order="name",
        ),
    }
    log.info(
        "Dropdown cache: %d companies, %d employees, %d categories, %d currencies, %d vendors",
        len(companies), len(employees), len(categories), len(data["currencies"]), len(data["vendors"]),
    )
    _cache["data"] = data
    _cache["expires"] = now + CACHE_TTL
    return data


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/")
def index():
    dropdowns = get_dropdowns()
    return render_template(
        "index.html",
        dropdowns=dropdowns,
        today=date.today().isoformat(),
    )


@app.route("/submit", methods=["POST"])
def submit():
    try:
        company_id = int(request.form["company_id"])
        employee_id = int(request.form["employee_id"])
        product_id = int(request.form["product_id"])
        currency_id = int(request.form["currency_id"])
        total_amount = float(request.form["total_amount"])
        date_str = request.form["date"]
        description = request.form.get("description", "").strip()
        payment_mode = request.form.get("payment_mode", "own_account")
        vendor_id = request.form.get("vendor_id")

        if total_amount <= 0:
            raise ValueError("Amount must be positive")
        if payment_mode not in ("own_account", "company_account"):
            raise ValueError(f"Invalid payment_mode: {payment_mode}")
        if payment_mode == "company_account":
            if not vendor_id:
                raise ValueError("Vendor is required when payment_mode = company_account")
            vendor_id = int(vendor_id)
        else:
            vendor_id = False

        # Build attachment command (Command.create: (0, 0, {...}))
        attachment_cmds = []
        if "receipt" in request.files:
            f = request.files["receipt"]
            if f and f.filename:
                datas = base64.b64encode(f.read()).decode("ascii")
                attachment_cmds.append(
                    (
                        0,
                        0,
                        {
                            "name": f.filename,
                            "datas": datas,
                            "mimetype": f.mimetype or "application/octet-stream",
                            "res_model": "hr.expense",
                        },
                    )
                )

        # Mirrors mail.alias.message_new pattern: pass company_id explicitly so
        # _compute_tax_ids / _compute_account_id / _compute_payment_method_line_id
        # pick the right records. (We can't call .with_company() from JSON-RPC.)
        vals = {
            "company_id": company_id,
            "employee_id": employee_id,
            "product_id": product_id,
            "currency_id": currency_id,
            "total_amount_currency": total_amount,
            "date": date_str,
            "description": description,
            "payment_mode": payment_mode,
        }
        if vendor_id:
            vals["vendor_id"] = vendor_id
        if attachment_cmds:
            vals["attachment_ids"] = attachment_cmds

        log.info(
            "Creating expense: company=%s employee=%s product=%s amount=%s %s payment=%s",
            company_id,
            employee_id,
            product_id,
            total_amount,
            currency_id,
            payment_mode,
        )
        expense_id = odoo.create("hr.expense", vals)
        log.info("Created expense id=%s, submitting...", expense_id)

        # action_submit requires broker to be in group_hr_expense_manager
        # (see hr.expense.action_submit line 1132 in Odoo 19 source).
        odoo.execute("hr.expense", "action_submit", [[expense_id]])

        # Read back for confirmation
        result = odoo.search_read(
            "hr.expense",
            [("id", "=", expense_id)],
            [
                "id",
                "name",
                "state",
                "employee_id",
                "company_id",
                "total_amount_currency",
                "currency_id",
                "date",
            ],
        )
        expense = result[0] if result else {"id": expense_id, "name": "?", "state": "submitted"}
        log.info("Success: expense id=%s state=%s", expense_id, expense.get("state"))

        return render_template(
            "_success.html",
            expense=expense,
            odoo_domain=PUBLIC_ODOO_DOMAIN,
        )

    except OdooError as e:
        log.exception("Odoo error during submit")
        return render_template("_error.html", error=str(e)), 400
    except (ValueError, KeyError) as e:
        log.exception("Validation error during submit")
        return render_template("_error.html", error=f"Invalid form data: {e}"), 400
    except Exception as e:
        log.exception("Unexpected error during submit")
        return render_template("_error.html", error=f"Unexpected error: {e}"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)