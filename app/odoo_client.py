"""Minimal JSON-RPC client for Odoo.

Usage:
    from odoo_client import OdooClient
    c = OdooClient(url, db, username, api_key)
    uid = c.authenticate()
    expense_id = c.create('hr.expense', {...})
    c.execute('hr.expense', 'action_submit', [[expense_id]])
"""

import httpx


class OdooError(Exception):
    """Raised on any Odoo RPC error."""


class OdooClient:
    def __init__(self, url, db, username, api_key, timeout=30.0):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.api_key = api_key
        self._uid = None
        self._client = httpx.Client(timeout=timeout)

    def _call(self, service, method, args):
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {"service": service, "method": method, "args": args},
            "id": 1,
        }
        resp = self._client.post(
            f"{self.url}/jsonrpc",
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            err = data["error"]
            msg = err.get("data", {}).get("message") or err.get("message") or str(err)
            raise OdooError(f"{method} failed: {msg} (code={err.get('code')})")
        return data.get("result")

    def authenticate(self):
        if self._uid is not None:
            return self._uid
        uid = self._call("common", "login", [self.db, self.username, self.api_key])
        if not uid:
            raise OdooError(
                f"Authentication failed for {self.username}@{self.db}. "
                "Check ODOO_USER, ODOO_API_KEY, and ODOO_DB."
            )
        self._uid = uid
        return uid

    def execute(self, model, method, args=None, kwargs=None):
        uid = self.authenticate()
        full_args = [
            self.db,
            uid,
            self.api_key,
            model,
            method,
            args or [],
            kwargs or {},
        ]
        return self._call("object", "execute_kw", full_args)

    def create(self, model, vals):
        if isinstance(vals, dict):
            vals = [vals]
        result = self.execute(model, "create", [vals])
        if not result:
            raise OdooError(f"create() on {model} returned no ID")
        return result[0] if isinstance(result, list) else result

    def write(self, model, ids, vals):
        return self.execute(model, "write", [[ids], vals])

    def search_read(self, model, domain, fields=None, limit=None, offset=None, order=None):
        kwargs = {}
        if fields:
            kwargs["fields"] = fields
        if limit is not None:
            kwargs["limit"] = limit
        if offset is not None:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order
        return self.execute(model, "search_read", [domain], kwargs)