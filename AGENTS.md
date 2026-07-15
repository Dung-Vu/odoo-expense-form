# Odoo Expense Submission Form

A tiny web form that submits expenses to **Odoo SaaS** via JSON-RPC, replacing the email-to-`expense@` workflow. Solves the multi-company routing problem by letting the user explicitly pick the company in the form.

> **One-paragraph context for future agents:** The company uses Odoo 19 SaaS with 2 companies. The old workflow was email-based: employees sent receipts to `expense@your-tenant.odoo.com` with a category code in the subject (e.g. `[KHSHIPLL]`). The problem — a shared mailbox meant Odoo couldn't tell which company the expense belonged to, so records were often created under the wrong company and had to be fixed manually. This form fixes that by making the user pick the company explicitly before submitting.

---

## Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12 + Flask 3 | Smallest viable HTTP server. ~200 LOC total. |
| HTTP client | httpx | Used to call Odoo JSON-RPC. |
| Templates | Jinja2 (built-in) | Server-rendered HTML. |
| Frontend JS | **HTMX 2.x** (CDN) | Form submit without page reload. No build step. |
| Styling | Plain CSS | Single `style.css`. No framework. |
| Server | Gunicorn (2 workers) | Production-ready WSGI. |
| Container | Docker + docker-compose | User's hosting choice: Windows machine 24/7. |
| External | Odoo 19 SaaS via JSON-RPC | `https://<tenant>.odoo.com/jsonrpc` |

**No database.** No frontend framework. No build step. No Node.js. Just Python + HTML.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (HTMX, ~14KB)                                       │
│  GET /            → render form                              │
│  POST /submit     → HTMX swap success/error partial         │
└─────────────────────────────────────────────────────────────┘
                          │  (HTTP only)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Flask app (Docker, :5000)                                   │
│  • reads .env → ODOO_URL, ODOO_DB, ODOO_UID, ODOO_API_KEY    │
│  • GET /: loads dropdowns from Odoo, caches 5 min          │
│  • POST /submit: calls hr.expense.create + action_submit    │
└─────────────────────────────────────────────────────────────┘
                          │  (JSON-RPC, server-to-server)
                          ▼  ODOO_API_KEY in .env (browser never sees it)
┌─────────────────────────────────────────────────────────────┐
│  Odoo SaaS (https://<tenant>.odoo.com)                       │
│  execute_kw('hr.expense', 'create', [vals]) → expense_id    │
│  execute_kw('hr.expense', 'action_submit', [[id]])           │
│  execute_kw('ir.attachment', 'create', [attachment_vals])   │
└─────────────────────────────────────────────────────────────┘
```

### Why a tiny backend is required (not pure HTML+JS)

Odoo SaaS **does not allow custom modules**. The only way to push records in is the public JSON-RPC API. But:
- The API key must never live in browser JS (it would leak via View Source).
- Odoo SaaS CORS rejects cross-origin browser POSTs.
- File uploads need server-side base64 encoding before calling `ir.attachment.create`.

So we need a server-side proxy. Flask + Docker is the smallest possible one.

---

## File Structure

```
odoo-expense-form/
├── AGENTS.md                  ← you are here (onboarding for future agents)
├── README.md                  ← user-facing: how to run + test
├── Dockerfile                 ← python:3.12-slim + gunicorn
├── docker-compose.yml         ← single service, env_file: .env
├── requirements.txt           ← flask, httpx, gunicorn, python-dotenv
├── .env.example               ← template (NEVER commit real .env)
├── .env                       ← real config (gitignored, contains API key)
├── .gitignore
└── app/
    ├── __init__.py
    ├── main.py                ← Flask routes: GET /, POST /submit, GET /health
    │                            + cache, payment_mode/vendor_id parsing
    ├── odoo_client.py         ← JSON-RPC wrapper: authenticate, execute, create, search_read
    ├── templates/
    │   ├── base.html          ← layout, HTMX CDN
    │   ├── index.html         ← the form (company, employee, category, payment_mode, vendor, ...)
    │   ├── _success.html      ← HTMX partial: success message
    │   └── _error.html        ← HTMX partial: error message
    └── static/
        └── style.css
```

---

## How to Run

### Prerequisites
- Docker + docker-compose on Windows
- An Odoo user with API key (Settings → My Profile → Account Security → API Keys)
- That user must be in **at least one of these groups** for each target company:
  - `hr_expense.group_hr_expense_user` (Expense / Responsible) — minimum to create
  - `hr_expense.group_hr_expense_manager` (Expense / Administrator) — **required** for `action_submit()` to work on behalf of other employees

### First-time setup

1. Copy `.env.example` → `.env`
2. Fill in:
   ```
   ODOO_URL=https://testing1307.odoo.com   # or production URL
   ODOO_DB=testing1307                     # Odoo database name
   ODOO_UID=208                            # Broker user ID (admin)
   ODOO_API_KEY=xxxxxxxxxxxxxxxx           # API key from that user's profile
   ```
3. `docker compose up -d --build`
4. Open `http://<host>:5050` — **port 5050, not 5000** (5000 is occupied by macOS Control Center; on Windows any free port works)

### Verify health
```
curl http://localhost:5050/health
# → {"status":"ok"}
```

### Verify Odoo connectivity (without starting the container)
Three reference scripts in the project root test connectivity + full create flow:
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python test_connectivity.py   # auth + dropdowns (no creates)
.venv/bin/python test_create.py         # full create + submit
.venv/bin/python test_attachment.py     # create with attachment + submit
```

If `test_create.py` and `test_attachment.py` succeed, the Odoo side is wired correctly. The remaining risk is in the Flask layer (form rendering, HTMX swap) which is verified by opening `http://localhost:5050` in a browser.

---

## How to Test Record Creation

The form itself is the test UI. To test via API directly:

```bash
curl -X POST http://localhost:5000/submit \
  -F "company_id=1" \
  -F "employee_id=42" \
  -F "product_id=15" \
  -F "currency_id=21" \
  -F "total_amount=150000" \
  -F "date=2026-07-14" \
  -F "description=Test from curl"
```

Or open `http://<host>:5000` in a browser, fill the form, submit.

**Expected behavior on success:**
1. Response is an HTML partial showing "✓ Expense #XXXX created"
2. In Odoo: `Expenses → My Expenses` shows the new record in state **Submitted**
3. The chosen employee is auto-subscribed as follower (sees it in their "My Expenses")
4. The chosen company's manager gets an approval activity

**Verify in Odoo:**
- Navigate to Odoo → Expenses → search for the new ID
- Confirm `Company` field = the value selected in the form
- Confirm `Employee` field = the value selected in the form
- Confirm state = `Submitted` (not `Draft`)

---

## Odoo Integration: The Broker Pattern

**Critical context:** This system uses **one Odoo user's API key** (the company admin) to create expenses on behalf of other employees. This is called the "broker" pattern.

### Why broker works
- `hr.expense.create()` does NOT restrict `employee_id` to the current user. You can set it to any employee.
- `hr.expense.create()` does NOT restrict `company_id` to `env.company` — you can override.
- `hr.expense.action_submit()` **DOES** restrict: raises `UserError` unless `env.user.employee_id == expense.employee_id` OR `env.user.can_approve == True`.
- `can_approve == True` when the broker user is in `group_hr_expense_manager`.

→ **The broker MUST be in `group_hr_expense_manager`** (Expense / Administrator group). If not, `action_submit` will fail.

### Trade-offs of broker pattern
| Good | Bad |
|---|---|
| Zero per-user friction | `create_uid` = broker, not submitter |
| One key to manage | Audit chatter shows broker as creator |
| Simple auth model | Single point of failure (broker leaves company → form breaks) |
| | Reports by `employee_id` still correct (data field, not audit field) |

**About `create_uid` not being the submitter:** This is **consistent with how Odoo's own mail alias flow works** — when an email comes in via `expense@...@odoo.com`, Odoo's mail gateway runs in superuser mode (`env.su=True`), so `create_uid = SUPERUSER_ID (1)`, not the actual employee. Our broker approach has `create_uid = broker` which is the same kind of "system user" footprint. The **functional owner** is still the `employee_id` field, which drives approval, reporting, payment. Don't optimize for `create_uid` perfection.

If the broker ever loses admin status or leaves the company, **regenerate a new API key on a successor admin user** and update `.env`.

### Alternative: per-user login
Not implemented. Would require a login UI, session management, and per-user Odoo credentials. Not worth it for <5 users.

---

## Key Fields on `hr.expense` (Odoo 19)

From `addons/hr_expense/models/hr_expense.py`:

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Computed from `product_id.display_name` if empty |
| `date` | Date | Default today |
| `employee_id` | M2O `hr.employee` | **Required**. We pass this from the form. |
| `company_id` | M2O `res.company` | **Required, readonly at ORM level** but writable via `create()`. Default is `env.company`. |
| `product_id` | M2O `product.product` | Domain `[('can_be_expensed', '=', True)]`. This is the "category". |
| `total_amount_currency` | Monetary | For products WITHOUT cost (e.g. shipping fees). User input. |
| `currency_id` | M2O `res.currency` | Required. Defaults to company currency. |
| `payment_mode` | Selection | `own_account` (default, employee paid) or `company_account` (company paid). Form exposes this. |
| `vendor_id` | M2O `res.partner` | Required when `payment_mode='company_account'`. Form shows this field conditionally. |
| `description` | Text | Internal notes. |
| `attachment_ids` | O2M `ir.attachment` | Use `[(0, 0, {datas: base64, name: ..., mimetype: ...})]` on create. |

### State machine
```
draft → submitted → approved → posted → paid
                  ↘ refused
```
- After `create()`: state = `draft`
- After `action_submit()`: state = `submitted` (and approval activity scheduled for manager)

---

## Source Code Patterns (reference)

When refactoring this code, these patterns from the Odoo 19 source informed our design:

### `Environment.__call__` (odoo/orm/environments.py)
The way to switch user / company / context:
```python
new_env = env(user=new_uid, company=new_company)  # server-side only
records = records.with_user(target_user)            # common shortcut
records = records.with_company(target_company)      # common shortcut
records = records.sudo()                            # bypass access rights
records = records.with_context(key=value)           # set context key
```
**External JSON-RPC cannot use these** — `env` is fixed to the authenticated user. We mimic the effect by:
- Passing `company_id` explicitly in `vals` for `create()`
- Filtering dropdowns ahead of time (e.g. products, vendors per company)
- Not relying on `env.user` defaults — explicit `employee_id` in vals

### `hr.expense.message_new` (mail alias flow)
The canonical pattern Odoo itself uses for email-to-expense:
```python
@api.model
def message_new(self, msg_dict, custom_values=None):
    employee = self._get_employee_from_email(email_from)
    company = employee.company_id or self.env.company
    self = self.with_company(company)   # ← KEY: switch context BEFORE create
    vals = {'company_id': company.id, 'employee_id': employee.id, ...}
    return super().message_new(msg_dict, dict(custom_values or {}, **vals))
```
**We replicate the effect** (proper company on vals) but cannot replicate the internal `with_company` switch via JSON-RPC. The result is the same: correct tax accounts, correct product accounts, correct payment method lines all derived from the explicit `company_id`.

### `MailThread.create` auto-subscribe
```python
if not self.env.context.get('mail_create_nosubscribe') and ...:
    self.env['mail.followers']._insert_followers(
        threads._name, threads.ids,
        self.env.user.partner_id.ids,    # ← broker gets auto-subscribed
        ...
    )
```
This is why the broker ends up as a follower of every expense. The actual employee gets subscribed via `hr.expense._message_auto_subscribe_followers` which is called next. So both broker + employee end up as followers.

### `action_submit` permission check (hr.expense line 1128)
```python
def action_submit(self):
    user = self.env.user
    for expense in self:
        if user.employee_id != expense.employee_id and not expense.can_approve:
            raise UserError("You do not have the required permission to submit this expense.")
```
**This is why the broker MUST be in `group_hr_expense_manager`** — otherwise `can_approve=False` and submit fails.

---

## Gotchas (read before changing code)

1. **`action_submit` is gated.** If you ever switch the broker to a non-admin user, this will break silently with `UserError`. Always verify broker has `group_hr_expense_manager`.

2. **Attachment field is `attachment_ids` not `attachment_id`.** Plural. Pass as `[(0, 0, {...})]` (Command.create).

3. **`company_id` must be in the broker's allowed companies.** If you get `AccessError`, the broker doesn't have access to that company in `Settings → Users → Allowed Companies`.

4. **`hr.employee.filter_for_expense`** — when listing employees, filter by `[('filter_for_expense', '=', True)]` to match Odoo's own dropdown.

5. **Currency must be active.** Filter `[('active', '=', True)]` on `res.currency`.

6. **Cache the dropdowns.** Loading 4 search_read on every page load is wasteful. The 5-min in-memory cache is intentional.

7. **File upload max 16MB.** Set in `app.config['MAX_CONTENT_LENGTH']`. Larger receipts need chunked upload (not implemented).

8. **No CSRF protection.** Form is open and unauthenticated. Acceptable for internal tool with <5 trusted users. If exposing externally, add rate limiting + CAPTCHA.

---

## Common Tasks

### Add a new field to the form
1. Add the field to `app/templates/index.html`
2. Add parsing in `app/main.py` → `submit()` view
3. Add to `vals` dict passed to `hr.expense.create`

### Change styling
- Single file: `app/static/style.css`. No build step.

### Switch from testing1307 to production
1. Edit `.env`: change `ODOO_URL`, `ODOO_DB`, `PUBLIC_ODOO_DOMAIN`
2. `docker compose restart`

### Regenerate API key
1. Odoo → Settings → Users → [broker user] → Account Security → API Keys → New
2. Update `.env`'s `ODOO_API_KEY`
3. `docker compose restart`

### View logs
```bash
docker compose logs -f web
```

### Run a one-off Odoo query
```bash
docker compose exec web python -c "
c = OdooClient(os.environ['ODOO_URL'], os.environ['ODOO_DB'],
               os.environ['ODOO_API_KEY'], os.environ['ODOO_UID'])
print(c.search_read('hr.expense', [], ['name','state','employee_id','company_id','total_amount_currency'], limit=5))
"
```

---

## Environment Variables

| Variable | Required | Example | Purpose |
|---|---|---|---|
| `ODOO_URL` | yes | `https://testing1307.odoo.com` | Odoo base URL (no trailing slash) |
| `ODOO_DB` | yes | `testing1307` | Odoo database name |
| `ODOO_UID` | yes | `208` | Broker Odoo user ID |
| `ODOO_API_KEY` | yes | `abc123...` | Broker's API key |
| `COMPANY_IDS` | yes | `1,11` | Comma-separated `res.company` IDs shown in Company dropdown |
| `EMPLOYEE_NAME_KEYWORDS` | yes | `Phước,Thành,Công,Biên,Chinh` | Comma-separated name fragments. Matched against the **last whitespace-delimited word** of each employee name (Vietnamese given name). Case-insensitive. |
| `CATEGORY_IDS` | yes | `26807,26758,157600,...` | Comma-separated `product.product` IDs. Simple `id IN (...)` filter — fast and unambiguous. Find IDs in Odoo or via `search_read("product.product", [("can_be_expensed","=",True)], ["id","default_code","name"])`. |
| `FLASK_SECRET` | optional | random string | Reserved for future session-based auth |

### Whitelist behavior

- **Companies**: filtered by `id IN (COMPANY_IDS)`. Hardcode IDs — they're stable in Odoo.
- **Employees**: fetched with `company_id IN (COMPANY_IDS)`, then **filtered in Python** by last-word match against `EMPLOYEE_NAME_KEYWORDS`. This handles multi-company setups where the same person exists in both companies (e.g. one record in Bonario, one in Ordinaire, both named "ĐÀO VĂN PHƯỚC" — both shown, labeled with company).
  - Why not use the built-in `filter_for_expense` field? It is not consistently set across all employees in this tenant.
  - Why match by last word? To disambiguate names like "NGUYỄN THÀNH CÔNG" (last word: Công) from "NGUYỄN TẤN THÀNH" (last word: Thành).
- **Categories**: `id IN (CATEGORY_IDS)`. Simple and reliable — the earlier keyword-based approach hit Odoo Polish-notation parser limits at scale.
- **Vendors**: filtered by `company_id IN (COMPANY_IDS)`.

To add/remove an employee: edit `EMPLOYEE_NAME_KEYWORDS` in `.env` and restart the container. To add a new category: look up its `product.product` ID in Odoo and add to `CATEGORY_IDS`.

---

## What's NOT implemented (out of scope for v1)

- Per-user Odoo login
- Email confirmation step
- Rate limiting / CAPTCHA
- Expense editing / deletion via this UI
- Multi-receipt per submission
- i18n (currently Vietnamese-only labels but English fallback)
- Tests (manual testing only — project is small enough)
- CI/CD

---

## Quick Reference: Odoo JSON-RPC Calls Used

```python
# Authenticate (direct via ODOO_UID)
uid = client.authenticate()

# Create expense
expense_id = client.create('hr.expense', [{
    'company_id': 1,
    'employee_id': 42,
    'product_id': 15,
    'currency_id': 21,
    'total_amount_currency': 150000.0,
    'date': '2026-07-14',
    'description': 'Phí ship Lalamove',
    'attachment_ids': [(0, 0, {
        'name': 'receipt.pdf',
        'datas': base64_string,
        'mimetype': 'application/pdf',
    })],
}])

# Submit (requires broker to be admin)
client.execute('hr.expense', 'action_submit', [[expense_id]])

# Read back
result = client.search_read('hr.expense',
    [('id', '=', expense_id)],
    ['name', 'state', 'employee_id', 'company_id', 'total_amount_currency', 'currency_id']
)
```

---

## Project Status

- [x] Skeleton + Docker
- [x] JSON-RPC auth + create + submit
- [x] Form UI with company/employee/category/payment_mode/vendor dropdowns
- [x] File upload (single attachment)
- [x] payment_mode + vendor_id conditional logic
- [x] Source-code-aligned design (mirrors `hr.expense.message_new` pattern)
- [x] **Tested on testing1307** — 2 records created (5102, 5103), both submitted successfully
- [ ] Deploy to Windows host 24/7
- [ ] Migrate config to production `your-tenant.odoo.com`