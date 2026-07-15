# Odoo Expense Submission Form

Web form → Odoo SaaS via JSON-RPC. Replaces the email-to-`expense@` workflow and fixes multi-company routing.

> **Full project context, architecture, Odoo integration notes, and gotchas: see [`AGENTS.md`](./AGENTS.md).**

## Quick start

```bash
# 1. Configure
cp .env.example .env
# edit .env with your ODOO_URL, ODOO_DB, ODOO_USER, ODOO_API_KEY, PUBLIC_ODOO_DOMAIN

# 2. Run
docker compose up -d --build

# 3. Open
open http://localhost:5050
```

> **Port 5050** (not 5000) — chosen to avoid conflicts with macOS Control Center which occupies :5000.

## Requirements

- Docker + docker-compose
- An Odoo user with:
  - API key generated (Settings → My Profile → Account Security → API Keys)
  - `group_hr_expense_manager` group (Expense / Administrator) — required for `action_submit()` to work for other employees
  - Access to all target companies (Settings → Users → Allowed Companies)

## Test

```bash
curl -X POST http://localhost:5050/submit \
  -F "company_id=1" \
  -F "employee_id=42" \
  -F "product_id=15" \
  -F "currency_id=21" \
  -F "total_amount=150000" \
  -F "date=2026-07-14" \
  -F "description=Test"
```

Or open in browser, fill, submit.

## Health

```bash
curl http://localhost:5050/health
```

## Logs

```bash
docker compose logs -f web
```