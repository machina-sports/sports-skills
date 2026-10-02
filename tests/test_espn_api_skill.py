"""Offline regression tests for the prompt-only espn-api reference skill.

Covers the raw fetch helpers (TLS verification, query handling, replay refusal),
the shape fixtures behind references/response-schemas.md, and the routing and
output-contract text in SKILL.md.

The SKILL.md text checks are policy regression guards: they fail when a routing
or safety rule is dropped from the prompt. They do not show that a model will
deterministically pick the right skill. No test here touches the network:
urlopen is replaced in-process and curl is replaced by a stub on PATH.
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import types
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "skills" / "espn-api"
SKILL_MD = SKILL_DIR / "SKILL.md"
PY_HELPER = SKILL_DIR / "scripts" / "espn_fetch.py"
SH_HELPER = SKILL_DIR / "scripts" / "espn_fetch.sh"
REFERENCES = SKILL_DIR / "references"
FIXTURES = REFERENCES / "shape-fixtures.json"

HOSTILE_QUERIES = [
    "Shaquille O'Neal",
    "x'); import os; os.system('touch PWNED'); print('",
    '$(touch PWNED) `touch PWNED` "; touch PWNED #',
]
REPLAY_MODES = ["record", "replay", "fill", " Replay ", "bogus"]


def _load_helper():
    spec = importlib.util.spec_from_file_location("espn_fetch_under_test", PY_HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(self, body=b"{}"):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def helper(monkeypatch):
    monkeypatch.delenv("SPORTS_SKILLS_REPLAY", raising=False)
    return _load_helper()


@pytest.fixture
def urlopen_calls(helper, monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=None, context=None):
        calls.append({"url": req.full_url, "timeout": timeout, "context": context})
        return _Response()

    monkeypatch.setattr(helper.urllib.request, "urlopen", fake_urlopen)
    return calls


# ── Python helper ──────────────────────────────────────────────────────


@pytest.mark.parametrize("query", HOSTILE_QUERIES)
def test_python_search_query_is_url_encoded_data(helper, urlopen_calls, tmp_path, monkeypatch, query):
    monkeypatch.chdir(tmp_path)
    helper.cmd_search(argparse.Namespace(query=query, sport=None, limit=None))

    assert len(urlopen_calls) == 1
    sent = urllib.parse.parse_qs(urllib.parse.urlsplit(urlopen_calls[0]["url"]).query)
    assert sent["query"] == [query]
    assert not (tmp_path / "PWNED").exists()


def test_python_fetch_uses_verifying_context_and_timeout(helper, urlopen_calls):
    helper.fetch("https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/scoreboard")

    ctx = urlopen_calls[0]["context"]
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    assert urlopen_calls[0]["timeout"] == 30


def test_python_helper_source_never_disables_verification():
    source = PY_HELPER.read_text(encoding="utf-8")
    assert "_create_unverified_context" not in source
    assert "CERT_NONE" not in source
    assert "check_hostname = False" not in source


def test_ssl_context_without_certifi_uses_verified_system_store(helper, monkeypatch):
    monkeypatch.setitem(sys.modules, "certifi", None)  # makes `import certifi` raise ImportError
    ctx = helper._ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_ssl_context_uses_certifi_bundle_when_installed(helper, monkeypatch):
    seen = []
    real = ssl.create_default_context

    def recording(*args, **kwargs):
        seen.append(kwargs.get("cafile"))
        return real()

    fake = types.ModuleType("certifi")
    fake.where = lambda: "/fake/certifi/cacert.pem"
    monkeypatch.setitem(sys.modules, "certifi", fake)
    monkeypatch.setattr(helper.ssl, "create_default_context", recording)

    ctx = helper._ssl_context()
    assert seen == ["/fake/certifi/cacert.pem"]
    assert ctx.verify_mode == ssl.CERT_REQUIRED


def test_broken_certifi_bundle_fails_with_message(helper, monkeypatch, tmp_path, capsys):
    fake = types.ModuleType("certifi")
    fake.where = lambda: str(tmp_path / "missing.pem")
    monkeypatch.setitem(sys.modules, "certifi", fake)

    with pytest.raises(SystemExit) as exc:
        helper._ssl_context()
    assert exc.value.code == 1
    assert "certifi" in capsys.readouterr().err


def test_cert_verification_failure_is_actionable(helper, monkeypatch, capsys):
    def failing_urlopen(req, timeout=None, context=None):
        raise urllib.error.URLError(ssl.SSLCertVerificationError("certificate verify failed"))

    monkeypatch.setattr(helper.urllib.request, "urlopen", failing_urlopen)
    with pytest.raises(SystemExit) as exc:
        helper.fetch("https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/teams")
    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert "certificate verification failed" in err
    assert "certifi" in err
    assert "never disabled" in err


@pytest.mark.parametrize("mode", REPLAY_MODES)
def test_python_fetch_refuses_under_replay_before_network(helper, urlopen_calls, monkeypatch, capsys, mode):
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", mode)
    with pytest.raises(SystemExit) as exc:
        helper.fetch("https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/scoreboard")
    err = capsys.readouterr().err
    assert exc.value.code == 1
    assert urlopen_calls == []
    assert "SPORTS_SKILLS_REPLAY" in err
    assert "package runtime" in err


@pytest.mark.parametrize("mode", REPLAY_MODES)
def test_python_main_refuses_under_replay_before_network(helper, urlopen_calls, monkeypatch, mode):
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", mode)
    monkeypatch.setattr(sys, "argv", ["espn_fetch.py", "search", HOSTILE_QUERIES[1]])
    with pytest.raises(SystemExit):
        helper.main()
    assert urlopen_calls == []


@pytest.mark.parametrize("mode", ["off", "OFF", ""])
def test_python_fetch_runs_when_replay_off(helper, urlopen_calls, monkeypatch, mode):
    monkeypatch.setenv("SPORTS_SKILLS_REPLAY", mode)
    assert helper.fetch("https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/teams") == {}
    assert len(urlopen_calls) == 1


# ── Shell helper (curl replaced by a stub that records argv) ───────────

needs_bash = pytest.mark.skipif(shutil.which("bash") is None or os.name == "nt", reason="needs bash")

_CURL_STUB = """#!/bin/sh
printf '%s\\n' "$@" > "$CURL_ARGV_FILE"
printf '{}'
exit "${CURL_EXIT:-0}"
"""


def _run_shell(tmp_path, *args, replay=None, curl_exit=0):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "curl"
    stub.write_text(_CURL_STUB, encoding="utf-8")
    stub.chmod(0o755)
    argv_file = tmp_path / "curl-argv.txt"

    env = {k: v for k, v in os.environ.items() if k != "SPORTS_SKILLS_REPLAY"}
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["CURL_ARGV_FILE"] = str(argv_file)
    env["CURL_EXIT"] = str(curl_exit)
    if replay is not None:
        env["SPORTS_SKILLS_REPLAY"] = replay

    result = subprocess.run(
        ["bash", str(SH_HELPER), *args],
        env=env,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    argv = argv_file.read_text(encoding="utf-8").splitlines() if argv_file.exists() else None
    return result, argv


@needs_bash
@pytest.mark.parametrize("query", HOSTILE_QUERIES)
def test_shell_search_passes_query_as_curl_data(tmp_path, query):
    result, argv = _run_shell(tmp_path, "search", query)

    assert result.returncode == 0, result.stderr
    assert "-G" in argv
    assert argv[argv.index("--data-urlencode") + 1] == f"query={query}"
    assert not (tmp_path / "PWNED").exists()


def test_shell_helper_does_not_build_python_code():
    assert "python3 -c" not in SH_HELPER.read_text(encoding="utf-8")


@needs_bash
def test_shell_fetch_sets_bounded_timeouts_and_visible_errors(tmp_path):
    result, argv = _run_shell(tmp_path, "teams", "lacrosse", "pll")

    assert result.returncode == 0, result.stderr
    assert argv[argv.index("--max-time") + 1] == "30"
    assert argv[argv.index("--connect-timeout") + 1] == "10"
    assert "-sS" in argv
    assert "-f" in argv
    assert argv[-1] == "https://site.api.espn.com/apis/site/v2/sports/lacrosse/pll/teams"


@needs_bash
def test_shell_propagates_curl_failure(tmp_path):
    result, _ = _run_shell(tmp_path, "teams", "lacrosse", "pll", curl_exit=22)
    assert result.returncode == 22


@needs_bash
@pytest.mark.parametrize("mode", REPLAY_MODES)
def test_shell_refuses_under_replay_before_network(tmp_path, mode):
    result, argv = _run_shell(tmp_path, "search", "Stephen Curry", replay=mode)

    assert result.returncode != 0
    assert argv is None  # curl was never invoked
    assert "SPORTS_SKILLS_REPLAY" in result.stderr
    assert "package runtime" in result.stderr


@needs_bash
def test_shell_runs_when_replay_off(tmp_path):
    result, argv = _run_shell(tmp_path, "teams", "lacrosse", "pll", replay="off")
    assert result.returncode == 0, result.stderr
    assert argv is not None


# ── Shape fixtures and response-schemas reference ──────────────────────


@pytest.fixture(scope="module")
def fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def test_fixtures_are_labelled_as_shape_projections(fixtures):
    about = fixtures["_about"]
    assert "SHAPE FIXTURES" in about
    assert "not raw payloads" in about
    assert "illustrative" in about
    for name, entry in fixtures.items():
        if name.startswith("_"):
            continue
        assert "source_url" in entry
        assert {"source_timestamp", "fetched_at", "notes"} <= set(entry["observed"])
        assert entry["observed"]["fetched_at"] is None  # fetch time was not recorded


def test_fixture_source_urls_are_the_recorded_requests(fixtures):
    assert fixtures["nba_roster"]["source_url"] is None  # not recorded; not invented
    assert fixtures["nba_summary"]["source_url"] == (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event=401705534"
    )
    assert fixtures["nba_gamelog"]["source_url"] == (
        "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/3136776/gamelog?season=2025"
    )
    assert fixtures["now_news"]["source_url"] == (
        "https://now.core.api.espn.com/v1/sports/news?sport=basketball&league=nba&limit=2"
    )


def test_roster_athletes_are_flat(fixtures):
    athletes = fixtures["nba_roster"]["shape"]["athletes"]
    assert athletes
    for athlete in athletes:
        assert isinstance(athlete["id"], str)
        assert "items" not in athlete


def test_summary_players_are_sibling_of_teams(fixtures):
    boxscore = fixtures["nba_summary"]["shape"]["boxscore"]
    assert isinstance(boxscore["teams"], list)
    assert isinstance(boxscore["players"], list)
    assert all("players" not in team for team in boxscore["teams"])
    row = boxscore["players"][0]["statistics"][0]
    assert len(row["names"]) == len(row["athletes"][0]["stats"])


def test_gamelog_events_keyed_and_rows_under_season_types(fixtures):
    shape = fixtures["nba_gamelog"]["shape"]
    events = shape["events"]
    assert isinstance(events, dict)
    assert all(key == value["id"] for key, value in events.items())
    rows = [row for st in shape["seasonTypes"] for cat in st["categories"] for row in cat["events"]]
    assert rows
    for row in rows:
        assert row["eventId"] in events
        assert len(row["stats"]) == len(shape["labels"])


def test_now_news_uses_headlines_not_feed(fixtures):
    shape = fixtures["now_news"]["shape"]
    assert isinstance(shape["headlines"], list)
    assert isinstance(shape["breakingNews"], list)
    assert "feed" not in shape


def test_response_schemas_doc_matches_fixtures():
    doc = (REFERENCES / "response-schemas.md").read_text(encoding="utf-8")
    assert "illustrative shapes, not actual historical results" in doc
    assert "shape-fixtures.json" in doc
    assert "**flat** list" in doc
    assert "`boxscore.players[]` is a **sibling** of `boxscore.teams[]`" in doc
    assert "boxscore.teams[].players" not in doc
    assert "**dict keyed by event ID**" in doc
    assert "seasonTypes[].categories[].events[]" in doc
    assert '"headlines": [' in doc
    assert '"feed": [' not in doc


# ── League coverage claims ─────────────────────────────────────────────


def test_league_slug_counts_match_documented_scope():
    text = (REFERENCES / "league-slugs.md").read_text(encoding="utf-8")
    body = text.split("## College Football Conference IDs")[0]
    sports = re.findall(r"^## .+\(sport: `[^`]+`\)$", body, re.MULTILINE)
    rows = re.findall(r"^\| [^|]+ \| `[^`]+` \| [^|]+ \|$", body, re.MULTILINE)
    assert len(sports) == 17
    assert len(rows) == 106
    assert "106 league rows across 17 sport sections" in text
    assert "not a complete list" in text


def test_no_unverified_league_totals():
    catalog = json.loads((ROOT / "skills" / "catalog.json").read_text(encoding="utf-8"))
    readme_line = next(
        line for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines() if "`espn-api`" in line
    )
    for text in (SKILL_MD.read_text(encoding="utf-8"), catalog["skills"]["espn-api"]["description"], readme_line):
        assert "139" not in text
    assert "Complete mapping" not in (REFERENCES / "league-slugs.md").read_text(encoding="utf-8")
    assert "Complete reference" not in (REFERENCES / "endpoints.md").read_text(encoding="utf-8")


# ── Routing and output contract (policy text, not model behaviour) ─────


def _frontmatter_description():
    front = SKILL_MD.read_text(encoding="utf-8").split("---")[1]
    return front.split("description: |", 1)[1].split("\nlicense:", 1)[0]


def test_description_defaults_to_dedicated_skills():
    description = _frontmatter_description()
    first_paragraph = description.strip().split("\n\n")[0]
    assert "no dedicated sports-skills skill covers" in first_paragraph
    assert "explicitly asks" in first_paragraph
    assert "not normalized or canonical" in first_paragraph
    for skill in ("fastf1", "volleyball-data", "sports-news", "sports-reporter", "betting", "markets"):
        assert skill in description
    assert "Dutch Nevobo volleyball only, not NCAA" in description
    assert "not permission to switch to raw ESPN automatically" in description


def test_skill_states_output_contract():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "**provider-native**" in text
    assert '`{"status", "data", "message"}`' in text
    assert "say it is unsupported. Do not invent one." in text
    assert "keep IDs as strings" in text
    assert "keep timestamp precision as given" in text
    assert "untrusted data" in text
    assert "non-commercial" in text


def test_canonical_path_named_in_skill_exists():
    from sports_skills import canonical

    text = SKILL_MD.read_text(encoding="utf-8")
    for name in ("canonicalize_event", "to_observation", "to_envelope", "canonicalize_nba_event"):
        assert hasattr(canonical, name)
        assert f"`{name}`" in text or f"{name}`" in text
    assert "--format=machina-canonical" in text


def test_fantasy_scope_is_public_leagues_only():
    skill = SKILL_MD.read_text(encoding="utf-8")
    endpoints = (REFERENCES / "endpoints.md").read_text(encoding="utf-8")
    assert "Fantasy endpoints: public leagues only. Private leagues are out of scope" in skill
    assert "Public Leagues Only" in endpoints
    assert "require cookies" not in endpoints


def test_replay_limitation_documented():
    skill = SKILL_MD.read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "do not participate in `SPORTS_SKILLS_REPLAY`" in skill
    assert "Not covered: the `espn-api` skill's raw helper scripts" in readme


# ── No runtime namespace added ─────────────────────────────────────────


def test_no_espn_api_runtime_namespace():
    import sports_skills
    from sports_skills.cli import _REGISTRY

    assert not (ROOT / "src" / "sports_skills" / "espn_api").exists()
    assert not (ROOT / "src" / "sports_skills" / "espn_api.py").exists()
    assert importlib.util.find_spec("sports_skills.espn_api") is None
    assert "espn_api" not in sports_skills.__all__
    assert not any("espn" in module for module in _REGISTRY)


def test_catalog_entry_stays_read_only():
    entry = json.loads((ROOT / "skills" / "catalog.json").read_text(encoding="utf-8"))["skills"]["espn-api"]
    assert entry["mode"] == "read_only"
    assert entry["money_movement"] is False
    assert entry["secrets_required"] is False
    assert entry["untrusted_content"] is True
    assert "not normalized or canonical" in entry["description"]
