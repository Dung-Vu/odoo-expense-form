# Odoo Expense Submission Form

A simple web form for employees to submit business expenses directly to Odoo.

## Why this exists

Previously, employees submitted expenses by sending emails to a shared mailbox (e.g., `expense@your-tenant.odoo.com`). However, because Odoo could not determine which company the expense belonged to, records were frequently created under the wrong company and required manual correction.

This web form solves the routing problem by allowing users to explicitly select the correct company and employee when submitting an expense.

## Features

- **Company Selection:** Choose the correct company before submitting.
- **Employee Dropdown:** Select the submitter's name (filtered automatically based on the chosen company).
- **Category & Currency:** Select the expense type (category) and specify the amount.
- **Payment Method & Vendor:** Choose whether the expense is paid by the employee or by the company (requires selecting a vendor).
- **Receipt Upload:** Attach a receipt (image or PDF) directly to the expense.
- **Direct Link:** Provides a direct link to view the submitted expense in Odoo.

## Quick Start

### 1. Configure the environment
Copy `.env.example` to `.env` and fill in the required variables:
```env
ODOO_URL=https://your-tenant.odoo.com
ODOO_DB=your-db-name
ODOO_UID=your_uid
ODOO_API_KEY=your_odoo_api_key
```

### 2. Run the application
Start the service using Docker:
```bash
docker compose up -d --build
```

### 3. Access the form
Open your browser and navigate to:
- Local address: `http://localhost:5055`
- Public address: `https://chiphi.bonstu.site`