"""Central premium-funnel surface for sports-skills.

The open-source sport skills are intentionally premium-agnostic: they emit only
open data and generic technical signals (e.g. an HTTP 429 from a public API).
ALL Machina-facing routing and phrasing lives here and is invoked only from the
CLI — never from a sport connector.

sports-skills does not enumerate premium endpoints. The premium catalog
(licensed / real-time data) is owned by machina-templates and connectors served
by a deployed Machina pod, and is discovered through ``machina-cli`` — not here.
"""

import json
import os
import shutil
import subprocess
import sys

# --- Machina pointers (single source of truth; shared with the deploy handoff) ---

DOCS_URL = "http://docs.machina.gg/"
SITE_URL = "https://machina.gg"
MACHINA_INSTALL = "pip install machina-cli"
MACHINA_INSTALL_SH = "curl -fsSL https://raw.githubusercontent.com/machina-sports/machina-cli/main/install.sh | bash"

# Next steps into the premium DATA motion (motion #2): licensed / real-time data
# via machina-cli templates + connectors. The data twin of the build/ship steps
# in the `deploy` handoff. sports-skills points; machina-cli holds the catalog.
_PREMIUM_NEXT = [
    "machina login",
    "machina project use <project-id>",
    "machina template list        # discover premium data templates",
    "machina connector list       # discover licensed / real-time connectors",
]

_SUPPRESS_ENV = "SPORTS_SKILLS_NO_UPGRADE_HINTS"

# In-band hint triggers. Only generic, catalog-agnostic signals belong here.
# `rate_limited` is the one signal detectable centrally without any per-skill
# knowledge. `licensed_data` / `realtime` are reserved names for the future x402
# capability catalog and are intentionally NOT wired — that catalog lives in
# machina-templates / connectors, not in this repo.
TRIGGERS = {
    "rate_limited": {
        "reason": "The public API rate-limited this request.",
        "capability": ("Machina's licensed feeds offer higher throughput plus real-time, zero-latency data."),
    },
}


def _hints_suppressed():
    return os.environ.get(_SUPPRESS_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def build_hint(trigger):
    """Build the additive ``upgrade`` block for a known trigger, or ``None``.

    Data-first: ``via.data`` (premium data via machina-cli) is primary;
    ``via.deploy`` (ship via the Factory) is secondary. ``x402`` is reserved and
    always ``None`` in this version — a future machine-payable offer
    (endpoint / price / asset / network / resource) drops in here additively.
    """
    info = TRIGGERS.get(trigger)
    if info is None:
        return None
    return {
        "trigger": trigger,
        "reason": info["reason"],
        "capability": info["capability"],
        "via": {
            "data": {
                "skill": "machina",
                "command": "sports-skills premium",
                "docs": DOCS_URL,
            },
            "deploy": {"command": "sports-skills deploy"},
        },
        "x402": None,
    }


def attach(result):
    """Attach an in-band upgrade hint when a generic high-intent signal is present.

    Currently fires only on an upstream rate-limit (HTTP 429) surfaced by a public
    API. It never inspects which skill ran — the signal is purely the status code,
    so no premium knowledge leaks into the open-source skills.

    No-op on success responses, non-429 errors, non-dicts, when an ``upgrade``
    block already exists (idempotent), or when hints are suppressed via the
    ``SPORTS_SKILLS_NO_UPGRADE_HINTS`` env var. Returns ``result`` (mutated in
    place when a hint applies).
    """
    if _hints_suppressed():
        return result
    if not isinstance(result, dict) or "upgrade" in result:
        return result
    if result.get("status") is False and result.get("status_code") == 429:
        hint = build_hint("rate_limited")
        if hint is not None:
            result["upgrade"] = hint
    return result


def premium_handoff(remaining):
    """``sports-skills premium`` — hand off to machina-cli for the premium DATA
    motion (licensed / real-time feeds via templates + connectors).

    The data twin of ``deploy``. sports-skills neither hosts nor enumerates
    premium data; machina-cli and a deployed Machina pod do. This command only
    detects machina-cli and prints the next steps (optionally installing it with
    ``--install``). ``--json`` emits a machine-readable payload.
    """
    flags = {a.lstrip("-") for a in remaining if a.startswith("-")}
    as_json = "json" in flags
    do_install = "install" in flags

    machina = shutil.which("machina")

    if do_install and not machina:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "machina-cli"],
                check=True,
            )
            machina = shutil.which("machina")
        except Exception:  # noqa: BLE001
            # Installation failed; fall through to the not-installed guidance.
            pass

    if as_json:
        print(
            json.dumps(
                {
                    "status": True,
                    "message": (
                        "Need licensed or real-time data? machina-cli connects you to "
                        "premium feeds via the Machina platform."
                    ),
                    "data": {
                        "machina_cli_installed": bool(machina),
                        "install": MACHINA_INSTALL,
                        "install_sh": MACHINA_INSTALL_SH,
                        "next": _PREMIUM_NEXT,
                        "docs": DOCS_URL,
                    },
                },
                indent=2,
            )
        )
        return

    print("Premium data via Machina " + "─" * 39)
    print("The open-source skills use free public APIs (snapshot, rate-limited).")
    print("For licensed + real-time data — higher throughput, zero-latency feeds,")
    print("and packaged data templates/connectors — connect via machina-cli.\n")
    if machina:
        print("  ✓ machina-cli detected\n")
        print("  Next:")
        for s in _PREMIUM_NEXT:
            print(f"    $ {s}")
    else:
        print("  1. Install machina-cli:")
        print(f"       {MACHINA_INSTALL}")
        print(f"       # or: {MACHINA_INSTALL_SH}")
        print("       # or: sports-skills premium --install")
        print("\n  2. Then:")
        for s in _PREMIUM_NEXT:
            print(f"    $ {s}")
    print(f"\n  Docs: {DOCS_URL}")
