"""Remote WordPress API client for Pusula Lite."""

from __future__ import annotations

import json
import pathlib
import uuid
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, List, Optional

SETTINGS_PATH = pathlib.Path(__file__).with_name("data") / "api_settings.json"
DEFAULT_TIMEOUT = 15


class ApiError(Exception):
    """Raised when the API returns an error."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def load_settings() -> Dict[str, str]:
    """Load saved API settings (base_url, api_key, device_id)."""
    if SETTINGS_PATH.exists():
        try:
            with SETTINGS_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    # Ensure stable device id
    if "device_id" not in data or not data["device_id"]:
        data["device_id"] = uuid.uuid4().hex

    return {
        "base_url": data.get("base_url", "").rstrip("/"),
        "api_key": data.get("api_key", ""),
        "device_id": data["device_id"],
    }


def save_settings(base_url: str, api_key: str, device_id: Optional[str] = None) -> None:
    """Persist API settings to disk."""
    SETTINGS_PATH.parent.mkdir(exist_ok=True)
    data = {
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "device_id": device_id or load_settings().get("device_id") or uuid.uuid4().hex,
    }
    with SETTINGS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _build_url(path: str, params: Optional[Dict[str, Any]] = None) -> str:
    settings = load_settings()
    base = settings["base_url"]
    if not base:
        raise ApiError(400, "API URL is not configured.")
    url = f"{base}/{path.lstrip('/')}"
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query:
            url = f"{url}?{query}"
    return url


def _request(method: str, path: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Any:
    settings = load_settings()
    url = _build_url(path, params)

    api_key = settings.get("api_key", "")
    if not api_key:
        raise ApiError(401, "API anahtarı ayarlanmadı. Lütfen Ayarlar sekmesinden ekleyin.")

    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Device-Id": settings.get("device_id", ""),
    }

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return None
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw
    except urllib.error.HTTPError as e:
        try:
            payload = e.read().decode("utf-8")
            msg = json.loads(payload).get("message", payload)
        except Exception:
            msg = str(e)
        if e.code == 401:
            msg = "Yetkisiz: API anahtarı hatalı veya eksik."
        elif e.code == 404:
            msg = "Kayıt bulunamadı."
        elif not msg:
            msg = "Sunucu hatası."
        raise ApiError(e.code, msg) from e
    except urllib.error.URLError as e:
        raise ApiError(0, f"Bağlantı hatası: {e.reason}") from e


def test_connection() -> bool:
    """Simple ping by fetching the customer list."""
    _request("GET", "/customers", params=None)
    return True


# ---------------------------------------------------------------------------
# Customers & Contacts
# ---------------------------------------------------------------------------
def list_customers(
    search: str | None = None,
    with_contacts: bool = False,
    *,
    cid: int | None = None,
    name: str | None = None,
    phone: str | None = None,
    address: str | None = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {
        "search": search,
        "id": cid,
        "name": name,
        "phone": phone,
        "address": address,
        "limit": limit,
    }
    if with_contacts:
        params["with"] = "contacts"
    return _request("GET", "/customers", params=params) or []


def get_customer(customer_id: int) -> Optional[Dict[str, Any]]:
    return _request("GET", f"/customers/{customer_id}")


def save_customer(customer: Dict[str, Any], contacts: List[Dict[str, Any]] | None = None) -> int:
    payload = dict(customer)
    if contacts is not None:
        payload["contacts"] = contacts

    if customer.get("id"):
        cid = int(customer["id"])
        try:
            _request("PUT", f"/customers/{cid}", data=payload)
            return cid
        except ApiError as e:
            if e.status != 404:
                raise
            # Fall back to create when not found
            payload.pop("id", None)

    res = _request("POST", "/customers", data=payload)
    return int(res.get("id"))


def get_contacts(customer_id: int) -> List[Dict[str, Any]]:
    return _request("GET", f"/customers/{customer_id}/contacts") or []


def replace_contacts(customer_id: int, contacts: List[Dict[str, Any]]) -> None:
    _request("PUT", f"/customers/{customer_id}/contacts", data=contacts)


def delete_customer(customer_id: int) -> None:
    _request("DELETE", f"/customers/{customer_id}")


# ---------------------------------------------------------------------------
# Sales & Installments
# ---------------------------------------------------------------------------
def list_sales(customer_id: int | None = None, start: str | None = None, end: str | None = None, with_installments: bool = False) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"customer_id": customer_id, "start": start, "end": end}
    if with_installments:
        params["with"] = "installments"
    return _request("GET", "/sales", params=params) or []


def get_sale(sale_id: int) -> Optional[Dict[str, Any]]:
    return _request("GET", f"/sales/{sale_id}")


def save_sale(sale: Dict[str, Any]) -> int:
    if sale.get("id"):
        sid = int(sale["id"])
        _request("PUT", f"/sales/{sid}", data=sale)
        return sid
    res = _request("POST", "/sales", data=sale)
    return int(res.get("id"))


def delete_sale(sale_id: int) -> None:
    _request("DELETE", f"/sales/{sale_id}")


def list_installments(sale_id: int | None = None) -> List[Dict[str, Any]]:
    return _request("GET", "/installments", params={"sale_id": sale_id}) or []


def save_installment(inst: Dict[str, Any]) -> int:
    if inst.get("id"):
        iid = int(inst["id"])
        _request("PUT", f"/installments/{iid}", data=inst)
        return iid
    res = _request("POST", "/installments", data=inst)
    return int(res.get("id"))


# ---------------------------------------------------------------------------
# Locking
# ---------------------------------------------------------------------------
def acquire_lock(record_type: str, record_id: int, mode: str = "write") -> None:
    _request("POST", "/locks", data={"record_type": record_type, "record_id": record_id, "mode": mode})


def release_lock(record_type: str, record_id: int) -> None:
    _request("POST", "/locks/release", data={"record_type": record_type, "record_id": record_id})
