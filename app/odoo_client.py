"""Minimal JSON-RPC client for Odoo.

Usage:
    from app.odoo_client import OdooClient
    c = OdooClient(url, db, api_key, uid)
    uid = c.authenticate()
    expense_id = c.create('hr.expense', {...})
    c.execute('hr.expense', 'action_submit', [[expense_id]])
"""

from typing import Any, Dict, List, Optional, Union
import httpx


class OdooError(Exception):
    """Raised on any Odoo RPC error."""


class OdooClient:
    """Wrapper around Odoo's JSON-RPC endpoint (`/jsonrpc`)."""

    def __init__(
        self,
        url: str,
        db: str,
        api_key: str,
        uid: Union[int, str],
        timeout: float = 30.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.db = db
        self.api_key = api_key
        self._uid = int(uid)
        self._client = httpx.Client(timeout=timeout)

    def _call(self, service: str, method: str, args: list) -> Any:
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

    def authenticate(self) -> int:
        """Return the configured broker UID."""
        return self._uid

    def execute(
        self,
        model: str,
        method: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
    ) -> Any:
        """Call an execute_kw method on an Odoo model."""
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

    def create(self, model: str, vals: Union[Dict[str, Any], List[Dict[str, Any]]]) -> int:
        """Create record(s) on `model` and return the newly created ID."""
        if isinstance(vals, dict):
            vals = [vals]
        result = self.execute(model, "create", [vals])
        if not result:
            raise OdooError(f"create() on {model} returned no ID")
        return result[0] if isinstance(result, list) else result

    def write(self, model: str, ids: Union[int, List[int]], vals: Dict[str, Any]) -> bool:
        """Update record(s) with `vals`."""
        target_ids = [ids] if isinstance(ids, int) else ids
        return self.execute(model, "write", [target_ids, vals])

    def search_read(
        self,
        model: str,
        domain: list,
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        order: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Perform search_read on `model` with domain, fields, and ordering."""
        kwargs: Dict[str, Any] = {}
        if fields:
            kwargs["fields"] = fields
        if limit is not None:
            kwargs["limit"] = limit
        if offset is not None:
            kwargs["offset"] = offset
        if order:
            kwargs["order"] = order
        return self.execute(model, "search_read", [domain], kwargs)