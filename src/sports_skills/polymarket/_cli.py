"""Polymarket CLI subprocess wrapper.

Wraps the ``polymarket`` Rust binary as a JSON subprocess.  All commands are
invoked with ``-o json`` for structured output.  Install the CLI with::

    pip install sports-skills[polymarket]

Or via Homebrew::

    brew tap Polymarket/polymarket-cli https://github.com/Polymarket/polymarket-cli
    brew install polymarket

For trading commands, configure a wallet via one of:

    # Option 1 — environment variable
    export POLYMARKET_PRIVATE_KEY=0x...

    # Option 2 — Python SDK
    from sports_skills import polymarket
    polymarket.configure(private_key="0x...")

    # Option 3 — CLI config file
    polymarket wallet import <private-key>
"""

import functools
import json
import os
import shutil
import subprocess

# ============================================================
# Binary Discovery
# ============================================================

_BINARY_NAME = "polymarket"


def _find_binary() -> str | None:
    """Locate the polymarket binary on PATH. Returns path or None."""
    return shutil.which(_BINARY_NAME)


def is_cli_available() -> bool:
    """Check whether the polymarket CLI binary is installed and reachable."""
    return _find_binary() is not None


# ============================================================
# Configuration (wallet / authentication)
# ============================================================

_CONFIG: dict = {}


def configure(
    *,
    private_key: str | None = None,
    signature_type: str | None = None,
) -> dict:
    """Configure wallet credentials for trading commands.

    Credentials are passed to the CLI via environment variables (never
    exposed in process arguments).  This is optional — the CLI also
    reads ``POLYMARKET_PRIVATE_KEY`` from the shell environment and
    ``~/.config/polymarket/config.json``.

    Args:
        private_key: Polygon wallet private key (hex string starting with 0x).
        signature_type: One of "proxy" (default), "eoa", or "gnosis-safe".

    Returns:
        Standard envelope confirming configuration was saved.
    """
    if private_key is not None:
        _CONFIG["private_key"] = private_key
    if signature_type is not None:
        if signature_type not in ("proxy", "eoa", "gnosis-safe"):
            return _error("signature_type must be 'proxy', 'eoa', or 'gnosis-safe'")
        _CONFIG["signature_type"] = signature_type
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
            # Check if it's a missing required argument error
            if 'missing' in err_msg and 'required' in err_msg:
                return _error(err_msg)
            raise  # Re-raise other TypeErrors
    return wrapper


def _build_env() -> dict | None:
    """Build subprocess env dict with any configured credentials."""
    if not _CONFIG:
        return None
    env = os.environ.copy()
    if "private_key" in _CONFIG:
        env["POLYMARKET_PRIVATE_KEY"] = _CONFIG["private_key"]
    if "signature_type" in _CONFIG:
        env["POLYMARKET_SIGNATURE_TYPE"] = _CONFIG["signature_type"]
    return env


# ============================================================
# Generic Runner
# ============================================================


def run_cli(*args: str, timeout: int = 30) -> dict:
    """Execute a polymarket CLI command and return parsed JSON.

    Args:
        *args: Command segments, e.g. ("markets", "list", "--limit", "10")
        timeout: Subprocess timeout in seconds.

    Returns:
        Standard envelope: {"status": bool, "data": ..., "message": str}
    """
    binary = _find_binary()
    if binary is None:
        return _error(
            "polymarket CLI not installed. Install with: "
            "pip install sports-skills[polymarket]"
        )

    cmd = [binary, "-o", "json", *args]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
        )
    except subprocess.TimeoutExpired:
        return _error(f"CLI command timed out after {timeout}s: {' '.join(args)}")
    except FileNotFoundError:
        return _error("polymarket binary not found at expected path")
    except OSError as e:
        return _error(f"Failed to execute polymarket CLI: {e}")

    # Non-zero exit code
    if result.returncode != 0:
        stderr = result.stderr.strip()
        # Try to parse JSON error from stdout first
        try:
            err_data = json.loads(result.stdout)
            if isinstance(err_data, dict) and "error" in err_data:
                return _error(f"CLI error: {err_data['error']}")
        except (json.JSONDecodeError, ValueError):
            pass
        return _error(
            f"CLI exited with code {result.returncode}: {stderr or 'unknown error'}"
        )

    # Parse JSON stdout
    stdout = result.stdout.strip()
    if not stdout:
        return _success(None, "CLI returned empty response")

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        return _error(f"CLI returned invalid JSON: {e}", data=stdout[:500])

    # CLI errors in JSON mode return {"error": "..."}
    if isinstance(data, dict) and "error" in data and len(data) == 1:
        return _error(f"CLI error: {data['error']}")

    return _success(data)


# ============================================================
# Group A: Data & Analytics (read-only, no auth)
# ============================================================


def get_leaderboard(
    *, period: str = "month", order_by: str = "pnl", limit: int = 20
) -> dict:
    """Get the Polymarket trader leaderboard."""
    return run_cli(
        "data", "leaderboard",
        "--period", period,
        "--order-by", order_by,
        "--limit", str(limit),
    )


@_wrap_required_params
def get_positions(*, address: str) -> dict:
    """Get open positions for a wallet address."""
    return run_cli("data", "positions", address)


@_wrap_required_params
def get_closed_positions(*, address: str) -> dict:
    """Get closed positions for a wallet address."""
    return run_cli("data", "closed-positions", address)


@_wrap_required_params
def get_portfolio_value(*, address: str) -> dict:
    """Get portfolio value for a wallet address."""
    return run_cli("data", "value", address)


@_wrap_required_params
def get_trade_history(*, address: str, limit: int = 50) -> dict:
    """Get trade history for a wallet address."""
    return run_cli("data", "trades", address, "--limit", str(limit))


@_wrap_required_params
def get_activity(*, address: str) -> dict:
    """Get activity feed for a wallet address."""
    return run_cli("data", "activity", address)


@_wrap_required_params
def get_holders(*, condition_id: str) -> dict:
    """Get position holders for a market."""
    return run_cli("data", "holders", condition_id)


@_wrap_required_params
def get_open_interest(*, condition_id: str) -> dict:
    """Get open interest for a market."""
    return run_cli("data", "open-interest", condition_id)


@_wrap_required_params
def get_volume(*, event_id: str) -> dict:
    """Get volume data for an event."""
    return run_cli("data", "volume", event_id)


@_wrap_required_params
def get_traded(*, address: str) -> dict:
    """Get markets traded by a wallet address."""
    return run_cli("data", "traded", address)


# ============================================================
# Group B: Enhanced Search & Tags (read-only, no auth)
# ============================================================


@_wrap_required_params
def cli_search_markets(*, query: str, limit: int = 20) -> dict:
    """Full-text market search via CLI (more powerful than search_markets)."""
    return run_cli("markets", "search", query, "--limit", str(limit))


def get_tags(*, limit: int | None = None) -> dict:
    """List all Polymarket tags."""
    args = ["tags", "list"]
    if limit is not None:
        args.extend(["--limit", str(limit)])
    return run_cli(*args)


@_wrap_required_params
def get_tag(*, tag: str) -> dict:
    """Get details for a specific tag."""
    return run_cli("tags", "get", tag)


@_wrap_required_params
def get_related_tags(*, tag: str) -> dict:
    """Get tags related to a given tag."""
    return run_cli("tags", "related", tag)


# ============================================================
# Group C: Comments & Profiles (read-only, no auth)
# ============================================================


@_wrap_required_params
def get_comments(*, entity_type: str, entity_id: str) -> dict:
    """Get comments on an entity (event or market)."""
    return run_cli(
        "comments", "list",
        "--entity-type", entity_type,
        "--entity-id", entity_id,
    )


@_wrap_required_params
def get_comment(*, comment_id: str) -> dict:
    """Get a single comment by ID."""
    return run_cli("comments", "get", comment_id)


@_wrap_required_params
def get_user_comments(*, address: str) -> dict:
    """Get all comments by a user."""
    return run_cli("comments", "by-user", address)


@_wrap_required_params
def get_profile(*, address: str) -> dict:
    """Get a public user profile."""
    return run_cli("profiles", "get", address)


# ============================================================
# Group D: Sports Metadata (read-only, no auth)
# ============================================================


def cli_sports_list() -> dict:
    """List all sports on Polymarket."""
    return run_cli("sports", "list")


@_wrap_required_params
def cli_sports_teams(*, league: str, limit: int = 50) -> dict:
    """Get teams for a league."""
    return run_cli("sports", "teams", "--league", league, "--limit", str(limit))


# ============================================================
# Group E: CLOB Extras (read-only, no auth)
# ============================================================


@_wrap_required_params
def get_tick_size(*, token_id: str) -> dict:
    """Get the minimum tick size for a market."""
    return run_cli("clob", "tick-size", token_id)


@_wrap_required_params
def get_fee_rate(*, token_id: str) -> dict:
    """Get the fee rate for a market."""
    return run_cli("clob", "fee-rate", token_id)


# ============================================================
# Group F: Trading Commands (authenticated — requires wallet)
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
    """Place a limit order."""
    return run_cli(
        "clob", "create-order",
        "--token", token_id,
        "--side", side,
        "--price", price,
        "--size", size,
        "--order-type", order_type,
    )


@_wrap_required_params
def market_order(*, token_id: str, side: str, amount: str) -> dict:
    """Place a market order."""
    return run_cli(
        "clob", "market-order",
        "--token", token_id,
        "--side", side,
        "--amount", amount,
    )


@_wrap_required_params
def cancel_order(*, order_id: str) -> dict:
    """Cancel a specific order."""
    return run_cli("clob", "cancel", order_id)


def cancel_all_orders() -> dict:
    """Cancel all open orders."""
    return run_cli("clob", "cancel-all")


def get_balance(
    *, asset_type: str = "collateral", token_id: str | None = None
) -> dict:
    """Check wallet balance."""
    args = ["clob", "balance", "--asset-type", asset_type]
    if token_id is not None:
        args.extend(["--token", token_id])
    return run_cli(*args)


def get_orders(*, market: str | None = None) -> dict:
    """View open orders."""
    args = ["clob", "orders"]
    if market is not None:
        args.extend(["--market", market])
    return run_cli(*args)


def get_user_trades() -> dict:
    """View your recent trades."""
    return run_cli("clob", "trades")


# ============================================================
# Group G: On-Chain Operations (authenticated — requires wallet)
# ============================================================


@_wrap_required_params
def ctf_split(*, condition_id: str, amount: str) -> dict:
    """Split USDC into YES/NO conditional tokens."""
    return run_cli(
        "ctf", "split",
        "--condition", condition_id,
        "--amount", amount,
    )


@_wrap_required_params
def ctf_merge(*, condition_id: str, amount: str) -> dict:
    """Merge YES/NO tokens back into USDC."""
    return run_cli(
        "ctf", "merge",
        "--condition", condition_id,
        "--amount", amount,
    )


@_wrap_required_params
def ctf_redeem(*, condition_id: str) -> dict:
    """Redeem winning tokens after market resolution."""
    return run_cli("ctf", "redeem", "--condition", condition_id)


def approve_check(*, address: str | None = None) -> dict:
    """Check current contract approvals."""
    args = ["approve", "check"]
    if address is not None:
        args.append(address)
    return run_cli(*args)


def approve_set() -> dict:
    """Approve all Polymarket contracts for trading."""
    return run_cli("approve", "set")
