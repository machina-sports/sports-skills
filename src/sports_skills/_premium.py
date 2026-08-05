"""Premium data handoff helpers for the sports-skills CLI."""

import json
import os
import shutil
import subprocess
import sys

DOCS_URL = "https://docs.machina.gg/"
SITE_URL = "https://machina.gg"
MACHINA_INSTALL = "pipx install machina-cli  # or: uv tool install machina-cli"
MACHINA_INSTALL_SH = "curl -fsSL https://raw.githubusercontent.com/machina-sports/machina-cli/main/install.sh -o /tmp/machina-install.sh && less /tmp/machina-install.sh && bash /tmp/machina-install.sh"

# Command that activates the premium tier. Surfaced in both the upgrade hint and
# the catalog's premium metadata, so keep it as one constant to avoid drift.
_PREMIUM_COMMAND = "sports-skills premium"

# Skills available on the premium tier. The gateway entry point lives here; the
# full premium catalog is served by the platform, not this open package.
PREMIUM_SKILLS = ["machina"]

_PREMIUM_NEXT = [
    "machina login",
    "machina project use <project-id>",
    "machina template list        # list available data templates",
    "machina connector list       # list available data connectors",
]

_SUPPRESS_ENV = "SPORTS_SKILLS_NO_UPGRADE_HINTS"

# Internal marker key. A connector that refuses a request because the free
# sources structurally cannot serve it (not a transient miss) sets
# ``result[UPGRADE_MARKER] = "licensed_data"``; ``attach`` consumes the marker
# and replaces it with a full ``upgrade`` block. The marker is always stripped
# from the response, including when hints are suppressed.
UPGRADE_MARKER = "upgrade_trigger"

TRIGGERS = {
    "rate_limited": {
        "reason": "The public API rate-limited this request.",
        "capability": ("Machina's licensed feeds offer higher throughput plus real-time, zero-latency data."),
    },
    "licensed_data": {
        "reason": "This request needs licensed or real-time data the public API does not provide.",
        "capability": ("Machina's licensed feeds add real-time, zero-latency, and proprietary data."),
    },
}


def _hints_suppressed():
    return os.environ.get(_SUPPRESS_ENV, "").strip().lower() in ("1", "true", "yes", "on")


def _tagged(url, surface):
    """Append a ``ref`` parameter naming the surface a link was shown on.

    Lets the docs site attribute visits per surface without this package
    sending anything anywhere itself — the URL only carries the tag if the
    user (or agent) chooses to open it.
    """
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}ref=sports-skills-{surface}"


def build_hint(trigger, surface="hint"):
    """Build an additive ``upgrade`` block for a known trigger."""
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
                "command": _PREMIUM_COMMAND,
                "docs": _tagged(DOCS_URL, surface),
            },
            "deploy": {"command": "sports-skills deploy"},
        },
        "x402": None,
    }


def premium_tier():
    """Static metadata describing the premium tier, for the ``catalog`` command.

    Purely declarative — no secrets, no network. Safe to ship in the open package.
    ``machina_cli_installed`` is a local ``which`` check so tooling can tell whether
    the optional CLI is already present.
    """
    return {
        "available": True,
        "skills": PREMIUM_SKILLS,
        "activate": _PREMIUM_COMMAND,
        "requires": "machina-cli",
        "machina_cli_installed": shutil.which("machina") is not None,
        "docs": _tagged(DOCS_URL, "catalog"),
    }


def attach(result):
    """Attach an upgrade hint where the free tier could not serve the request.

    Two ways in:
    - a connector marked the response via ``UPGRADE_MARKER`` (deliberate,
      set only at structural coverage refusals), or
    - the response is a rate-limited error (``status_code == 429``).

    The marker is consumed unconditionally so it never reaches callers, and
    ``attach`` is idempotent — a response that already carries ``upgrade``
    passes through untouched.
    """
    if not isinstance(result, dict):
        return result
    marker = result.pop(UPGRADE_MARKER, None)
    if _hints_suppressed() or "upgrade" in result:
        return result
    trigger = None
    if marker in TRIGGERS:
        trigger = marker
    elif result.get("status") is False and result.get("status_code") == 429:
        trigger = "rate_limited"
    if trigger:
        hint = build_hint(trigger)
        if hint is not None:
            result["upgrade"] = hint
    return result


def premium_handoff(remaining):
    """Handle the ``sports-skills premium`` command."""
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
                        "docs": _tagged(DOCS_URL, "premium-cmd"),
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
    print(f"\n  Docs: {_tagged(DOCS_URL, 'premium-cmd')}")
