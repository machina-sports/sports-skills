"""Polymarket trading via the py-clob-client-v2 Python SDK.

Uses ``py_clob_client_v2`` — Polymarket's CLOB **v2** client. The original
``py_clob_client`` was archived after the late-April-2026 CLOB v2 migration and
now fails every order with ``order_version_mismatch`` ("invalid order version,
please use the latest clob-client"), so trading must go through v2. Install::

    pip install sports-skills[polymarket]

Trading requires local wallet credentials configured outside any agent chat.
Do not paste private keys or seed phrases into an agent transcript.
"""
from __future__ import annotations

import functools
import os

# ============================================================
# Configuration (wallet / authentication)
# ============================================================

_CONFIG: dict = {}
_client_instance = None

# Mapping from human-readable names to clob-client integer signature codes.
_SIG_TYPE_MAP = {
    "eoa": 0,
    "poly_gnosis_safe": 1,
    "poly_proxy": 2,
    # Legacy aliases from the old CLI wrapper:
    "proxy": 2,
    "gnosis-safe": 1,
}


def configure(
    *,
    private_key: str | None = None,
    signature_type: str | int | None = None,
    funder: str | None = None,
) -> dict:
    """Configure wallet metadata for trading commands.

    Credentials must be supplied through a secure local environment or secret
    manager outside the agent transcript. Do not paste private keys into chat.

    Args:
        private_key: Polygon wallet private key, if supplied programmatically by
            trusted application code rather than an agent prompt.
        signature_type: Signature type — 0 / "eoa" (default), 1 / "gnosis-safe",
            or 2 / "proxy".
        funder: Funding address (the wallet holding collateral). Required for
            proxy / email (Magic) wallets where the signer differs from the
            funds holder; defaults to the signing address for EOA wallets.
    """
    global _client_instance
    if private_key is not None:
        _CONFIG["private_key"] = private_key
        _client_instance = None  # force re-init
    if funder is not None:
        _CONFIG["funder"] = funder
        _client_instance = None
    if signature_type is not None:
        if isinstance(signature_type, str):
            resolved = _SIG_TYPE_MAP.get(signature_type.lower())
            if resolved is None:
                return _error(
                    f"Unknown signature_type '{signature_type}'. "
                    f"Use one of: {', '.join(_SIG_TYPE_MAP.keys())} or an int 0-2."
                )
            signature_type = resolved
        _CONFIG["signature_type"] = signature_type
        _client_instance = None
    return _success(
        {"configured": list(_CONFIG.keys())},
        "Wallet configured for this session.",
    )


# ============================================================
# Response Helpers (match _connector.py pattern)
# ============================================================


def _success(data, message=""):
    return {"status": True, "data": data, "message": message}


def _error(message, data=None):
    return {"status": False, "data": data, "message": message}


def _wrap_required_params(fn):
    """Catch TypeError from missing required keyword args and return error dict."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except TypeError as e:
            err_msg = str(e)
            if "missing" in err_msg and "required" in err_msg:
                return _error(err_msg)
            raise
    return wrapper


# ============================================================
# Client Initialization (lazy)
# ============================================================

CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137


def _get_client():
    """Lazily initialize and return an authenticated v2 ClobClient instance."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    try:
        from py_clob_client_v2 import ClobClient
    except ImportError:
        return None

    key = _CONFIG.get("private_key") or os.environ.get("POLYMARKET_PRIVATE_KEY")
    if not key:
        return None

    sig_type = _CONFIG.get("signature_type", 0)
    funder = _CONFIG.get("funder") or os.environ.get("POLYMARKET_FUNDER_ADDRESS")

    client = ClobClient(
        host=CLOB_HOST,
        chain_id=CHAIN_ID,
        key=key,
        signature_type=sig_type,
        funder=funder,
    )
    # Derive (or look up) the L2 API credentials and attach them.
    client.set_api_creds(client.create_or_derive_api_key())
    _client_instance = client
    return _client_instance


def is_cli_available() -> bool:
    """Check whether the py_clob_client_v2 package is installed."""
    try:
        import py_clob_client_v2  # noqa: F401
        return True
    except ImportError:
        return False


def _require_client():
    """Return (client, None) or (None, error_dict)."""
    client = _get_client()
    if client is not None:
        return client, None

    if not is_cli_available():
        return None, _error(
            "py_clob_client_v2 not installed. Install with: "
            "pip install sports-skills[polymarket]"
        )
    return None, _error(
        "No private key configured. Configure Polymarket wallet credentials "
        "outside the agent transcript via a secure local environment or secret manager."
    )


def _order_type(name: str):
    """Resolve a string order-type to the v2 OrderType enum (default GTC)."""
    from py_clob_client_v2 import OrderType

    return {
        "GTC": OrderType.GTC,
        "FOK": OrderType.FOK,
        "FAK": OrderType.FAK,
        "GTD": OrderType.GTD,
    }.get(name.upper(), OrderType.GTC)


def _side(name: str):
    from py_clob_client_v2 import Side

    return Side.BUY if name.lower() == "buy" else Side.SELL


# ============================================================
# Trading Commands (authenticated — requires wallet)
# ============================================================


@_wrap_required_params
def create_order(
    *,
    token_id: str,
    side: str,
    price: str,
    size: str,
    order_type: str = "GTC",
) -> dict:
    """Place a limit order.

    Args:
        token_id: Market token ID.
        side: Order side — "buy" or "sell".
        price: Limit price (0.01–0.99).
        size: Number of shares.
        order_type: Order type — "GTC" (default), "FOK", "FAK", or "GTD".
    """
    client, err = _require_client()
    if err:
        return err

    from py_clob_client_v2 import OrderArgs, PartialCreateOrderOptions

    try:
        order_args = OrderArgs(
            token_id=token_id,
            price=float(price),
            size=float(size),
            side=_side(side),
        )
        resp = client.create_and_post_order(
            order_args=order_args,
            options=PartialCreateOrderOptions(tick_size=str(client.get_tick_size(token_id))),
            order_type=_order_type(order_type),
        )
        return _success(resp, "Order placed successfully.")
    except Exception as e:
        return _error(f"Failed to create order: {e}")


@_wrap_required_params
def market_order(*, token_id: str, side: str, amount: str) -> dict:
    """Place a market order (Fill-or-Kill).

    Args:
        token_id: Market token ID.
        side: Order side — "buy" or "sell".
        amount: For a buy, USDC to spend; for a sell, number of shares.
    """
    client, err = _require_client()
    if err:
        return err

    from py_clob_client_v2 import MarketOrderArgs, OrderType, PartialCreateOrderOptions

    try:
        mo_args = MarketOrderArgs(
            token_id=token_id,
            amount=float(amount),
            side=_side(side),
            order_type=OrderType.FOK,
        )
        resp = client.create_and_post_market_order(
            order_args=mo_args,
            options=PartialCreateOrderOptions(tick_size=str(client.get_tick_size(token_id))),
            order_type=OrderType.FOK,
        )
        return _success(resp, "Market order placed successfully.")
    except Exception as e:
        return _error(f"Failed to place market order: {e}")


@_wrap_required_params
def cancel_order(*, order_id: str) -> dict:
    """Cancel a specific order.

    Args:
        order_id: The ID (hash) of the order to cancel.
    """
    client, err = _require_client()
    if err:
        return err

    try:
        resp = client.cancel_orders([order_id])
        return _success(resp, "Order cancelled.")
    except Exception as e:
        return _error(f"Failed to cancel order: {e}")


def cancel_all_orders() -> dict:
    """Cancel all open orders."""
    client, err = _require_client()
    if err:
        return err

    try:
        resp = client.cancel_all()
        return _success(resp, "All orders cancelled.")
    except Exception as e:
        return _error(f"Failed to cancel orders: {e}")


def get_orders(*, market: str | None = None) -> dict:
    """View open orders.

    Args:
        market: Optional condition-ID to filter by.
    """
    client, err = _require_client()
    if err:
        return err

    try:
        from py_clob_client_v2 import OpenOrderParams

        params = OpenOrderParams(market=market) if market else OpenOrderParams()
        resp = client.get_open_orders(params)
        return _success(resp, "Open orders retrieved.")
    except Exception as e:
        return _error(f"Failed to get orders: {e}")


def get_user_trades() -> dict:
    """View your recent trades."""
    client, err = _require_client()
    if err:
        return err

    try:
        resp = client.get_trades()
        return _success(resp, "Trades retrieved.")
    except Exception as e:
        return _error(f"Failed to get trades: {e}")
