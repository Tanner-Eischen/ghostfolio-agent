"""Populate a local Ghostfolio instance with sample portfolio data.

Uses GHOSTFOLIO_API_URL and GHOSTFOLIO_ACCESS_TOKEN from the project .env.
Creates one account if none exist, then adds sample BUY/SELL/DIVIDEND activities.

API URL must be the Ghostfolio origin only (no path):
  - Correct:   http://localhost:3333   or   https://ghostfolio.io
  - Wrong:     http://localhost:3333/api   or   .../api/v1
The script appends /api/v1/... to the base URL.

Run from project root (so .env is found):
  python scripts/populate_ghostfolio_local.py

Requires: httpx (pip install httpx), Ghostfolio running at GHOSTFOLIO_API_URL.
"""

import sys
from pathlib import Path

import httpx


def _load_env() -> dict[str, str]:
    """Read .env from project root (no pydantic)."""
    root = Path(__file__).resolve().parent.parent
    env_file = root / ".env"
    out = {}
    if not env_file.exists():
        return out
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        val = v.strip().strip('"').strip("'").strip()
        out[key] = val
    return out


def check_api_url(base_url: str) -> None:
    """Verify the base URL reaches Ghostfolio (optional health check)."""
    # Ghostfolio Docker healthcheck uses /api/v1/health
    url = f"{base_url.rstrip('/')}/api/v1/health"
    try:
        r = httpx.get(url, timeout=5.0)
        if r.status_code == 200:
            return
        # 401 is OK here (health might require auth on some setups)
        if r.status_code == 401:
            return
    except httpx.ConnectError as e:
        raise SystemExit(
            f"Cannot reach Ghostfolio at {base_url}. "
            f"Check GHOSTFOLIO_API_URL in .env (use origin only, e.g. http://localhost:3333). Error: {e}"
        ) from e
    except Exception as e:
        raise SystemExit(f"Failed to check Ghostfolio at {base_url}: {e}") from e


def get_bearer_token(base_url: str, access_token: str) -> str:
    """Authenticate with Ghostfolio and return bearer token."""
    url = f"{base_url.rstrip('/')}/api/v1/auth/anonymous"
    r = httpx.post(
        url,
        json={"accessToken": access_token},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    token = data.get("token") or data.get("authToken")
    if not token:
        raise RuntimeError("No token in auth response")
    return token


def get_accounts(base_url: str, bearer: str) -> list[dict]:
    """List accounts. Returns list of account dicts with at least 'id'."""
    url = f"{base_url.rstrip('/')}/api/v1/account"
    r = httpx.get(
        url,
        headers={"Authorization": f"Bearer {bearer}"},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list):
        return data
    return data.get("accounts", [])


def create_account(base_url: str, bearer: str, name: str = "Brokerage", currency: str = "USD") -> dict:
    """Create an account. Returns created account with id."""
    url = f"{base_url.rstrip('/')}/api/v1/account"
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
        json={"name": name, "currency": currency},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def create_order(
    base_url: str,
    bearer: str,
    *,
    account_id: str,
    symbol: str,
    type: str,
    date: str,
    quantity: float,
    unit_price: float,
    currency: str = "USD",
    data_source: str = "YAHOO",
    fee: float = 0.0,
) -> dict:
    """Create one order/activity."""
    url = f"{base_url.rstrip('/')}/api/v1/order"
    payload = {
        "accountId": account_id,
        "currency": currency,
        "dataSource": data_source,
        "symbol": symbol,
        "type": type,
        "date": date,
        "quantity": quantity,
        "unitPrice": unit_price,
        "fee": fee,
    }
    r = httpx.post(
        url,
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
        json=payload,
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


# Sample activities to import (same idea as MOCK_ORDERS in ghostfolio.py)
SAMPLE_ACTIVITIES = [
    {"symbol": "AAPL", "type": "BUY", "date": "2024-01-15", "quantity": 20, "unit_price": 170.0},
    {"symbol": "AAPL", "type": "BUY", "date": "2024-02-10", "quantity": 30, "unit_price": 175.0},
    {"symbol": "AAPL", "type": "DIVIDEND", "date": "2024-02-15", "quantity": 50, "unit_price": 0.24},
    {"symbol": "MSFT", "type": "BUY", "date": "2024-01-20", "quantity": 25, "unit_price": 390.0},
    {"symbol": "VTI", "type": "BUY", "date": "2024-01-05", "quantity": 100, "unit_price": 225.0},
    {"symbol": "GOOGL", "type": "BUY", "date": "2024-01-12", "quantity": 15, "unit_price": 140.0},
    {"symbol": "GOOGL", "type": "SELL", "date": "2024-03-01", "quantity": 5, "unit_price": 145.0},
]


def main() -> None:
    env = _load_env()
    base_url = (env.get("GHOSTFOLIO_API_URL") or "").strip() or "http://localhost:3333"
    base_url = base_url.rstrip("/")
    token = (env.get("GHOSTFOLIO_ACCESS_TOKEN") or "").strip()
    if not token:
        print("Error: GHOSTFOLIO_ACCESS_TOKEN is not set in .env")
        sys.exit(1)

    print(f"Using Ghostfolio at {base_url} (API: {base_url}/api/v1/...)")
    print("Checking connection...")
    check_api_url(base_url)
    print("Authenticating...")
    bearer = get_bearer_token(base_url, token)
    print("OK")

    accounts = get_accounts(base_url, bearer)
    if not accounts:
        print("No accounts found. Creating 'Brokerage' account...")
        acc = create_account(base_url, bearer, name="Brokerage", currency="USD")
        account_id = acc.get("id") or acc.get("accountId")
        if not account_id:
            print("Error: Created account has no id:", acc)
            sys.exit(1)
        accounts = [acc]
        print(f"Created account id={account_id}")
    else:
        account_id = accounts[0].get("id") or accounts[0].get("accountId")
        print(f"Using existing account id={account_id} ({accounts[0].get('name', '')})")

    print(f"Creating {len(SAMPLE_ACTIVITIES)} sample activities...")
    for i, act in enumerate(SAMPLE_ACTIVITIES):
        try:
            create_order(
                base_url,
                bearer,
                account_id=account_id,
                symbol=act["symbol"],
                type=act["type"],
                date=act["date"],
                quantity=act["quantity"],
                unit_price=act["unit_price"],
                currency="USD",
                data_source="YAHOO",
                fee=0.0,
            )
            print(f"  {i+1}. {act['type']} {act['quantity']} {act['symbol']} @ {act['unit_price']}")
        except httpx.HTTPStatusError as e:
            print(f"  {i+1}. {act['symbol']} {act['type']} failed: {e.response.status_code} {e.response.text[:200]}")
        except Exception as e:
            print(f"  {i+1}. {act['symbol']} {act['type']} error: {e}")

    # Verify: fetch portfolio via API (same token = same user)
    print("\nVerifying via API...")
    try:
        details_url = f"{base_url}/api/v1/portfolio/details"
        r = httpx.get(
            details_url,
            headers={"Authorization": f"Bearer {bearer}"},
            params={"range": "max"},
            timeout=15.0,
        )
        r.raise_for_status()
        data = r.json()
        summary = data.get("summary") or {}
        total = summary.get("currentValueInBaseCurrency") or summary.get("totalValueInBaseCurrency") or 0
        holdings = data.get("holdings") or {}
        n_holdings = len(holdings) if isinstance(holdings, dict) else 0
        print(f"  Portfolio (API): total value = {total:.2f}, holdings = {n_holdings}")
        if total == 0 and n_holdings == 0:
            print("  (API shows 0 — activities may be drafts or still processing.)")
    except Exception as e:
        print(f"  Could not fetch portfolio: {e}")

    print("\n" + "=" * 60)
    print("To see the data in the Ghostfolio website:")
    print("  1. Open", base_url, "and LOG IN with the SAME user who created")
    print("     the access token in your .env (Settings > Security).")
    print("  2. Set date range to 'Max' or '1Y' (data is from 2024).")
    print("  3. Hard refresh: Ctrl+Shift+R (or Cmd+Shift+R on Mac).")
    print("=" * 60)


if __name__ == "__main__":
    main()
