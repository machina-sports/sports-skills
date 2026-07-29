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


def build_hint(trigger):
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
                "docs": DOCS_URL,
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
        "docs": DOCS_URL,
    }


def attach(result):
    """Attach an upgrade hint to rate-limited responses."""
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
        except Exception:  # ruff:ignore[blind-except]
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
