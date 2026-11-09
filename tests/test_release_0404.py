"""Release gates for the sports-skills 0.40.4 distribution candidate."""

import ast
import email
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import textwrap
import time
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.40.4"
TAG = f"v{VERSION}"
REVIEWED_SOURCE_COMMIT = "d312fe8eb877dc243e2c6bbe16eaafc4d6c25976"
REVIEWED_SOURCE_TREE = "e99ddd8e2e4a602642088b3cb1978cdbbc5bd156"
SOURCE_DATE_EPOCH = 1794255772
AUTHORITY = ROOT / "release" / VERSION / "SHA256SUMS"
REVIEW_RECEIPT = ROOT / "release" / VERSION / "review-receipt.json"
WHEEL_NAME = f"sports_skills-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"sports_skills-{VERSION}.tar.gz"
MARKETS_CONNECTOR = "sports_skills/markets/_connector.py"
NBA_CONNECTOR = "sports_skills/nba/_connector.py"
CBB_CONNECTOR = "sports_skills/cbb/_connector.py"
FOOTBALL_CONNECTOR = "sports_skills/football/_connector.py"
SCOREBOARD_SPORTS = ("nba", "nfl", "mlb", "nhl", "wnba", "cfb", "cbb")
GLEAGUE_SOURCES = {
    "sports_skills/gleague/__init__.py",
    "sports_skills/gleague/_cdn.py",
    "sports_skills/gleague/_connector.py",
    "sports_skills/gleague/_stats.py",
}
GLEAGUE_COMMANDS = (
    "get_teams",
    "get_scoreboard",
    "get_schedule",
    "get_standings",
    "get_team_roster",
    "get_team_schedule",
    "get_game_summary",
    "get_play_by_play",
    "get_news",
    "get_live_boxscore",
    "get_live_playbyplay",
    "find_nba_player",
    "get_nbastats_game_log",
    "get_nbastats_player_career",
    "get_nbastats_team_stats",
    "get_nbastats_shot_chart",
    "get_nbastats_play_by_play",
    "get_nbastats_advanced_boxscore",
    "get_nbastats_leaders",
)
POLYMARKET_TODAYS_PARAMS = ("offset", "date", "timezone", "compact", "sports_market_types")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_rows():
    rows = AUTHORITY.read_text(encoding="ascii").splitlines()
    assert len(rows) == 2
    parsed = []
    for row in rows:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", row)
        assert match is not None, row
        parsed.append(match.groups())
    assert [name for _, name in parsed] == [WHEEL_NAME, SDIST_NAME]
    return dict(parsed)


def _build(output):
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = str(SOURCE_DATE_EPOCH)
    subprocess.run(
        [sys.executable, str(ROOT / "packaging/release.py"), str(ROOT), str(output)],
        check=True,
        cwd=ROOT,
        env=env,
    )
    assert sorted(path.name for path in output.iterdir()) == sorted([SDIST_NAME, WHEEL_NAME])
    return output / WHEEL_NAME, output / SDIST_NAME


def _assert_checksum_file_is_not_an_artifact_input(wheel, sdist):
    with zipfile.ZipFile(wheel) as archive:
        assert not any(name.endswith("SHA256SUMS") for name in archive.namelist())
    with tarfile.open(sdist, "r:gz") as archive:
        assert not any(name.endswith("SHA256SUMS") for name in archive.getnames())


def _polymarket_surface(wrapper_source, cli_source):
    wrapper = {
        node.name: [arg.arg for arg in node.args.kwonlyargs]
        for node in ast.parse(wrapper_source).body
        if isinstance(node, ast.FunctionDef)
    }
    registry = next(
        node.value
        for node in ast.parse(cli_source).body
        if isinstance(node, ast.Assign) and [getattr(target, "id", None) for target in node.targets] == ["_REGISTRY"]
    )
    modules = {key.value: value for key, value in zip(registry.keys, registry.values)}
    cli = ast.literal_eval(modules["polymarket"])
    return wrapper, cli


@pytest.fixture(scope="session")
def release_builds(tmp_path_factory):
    first = tmp_path_factory.mktemp("release-build-a")
    second = tmp_path_factory.mktemp("release-build-b")
    return _build(first), _build(second)


def test_every_active_version_surface_is_0404():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = (ROOT / "src/sports_skills/__init__.py").read_text(encoding="utf-8")
    phase1 = (ROOT / "src/sports_skills/canonical/_phase1.py").read_text(encoding="utf-8")
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert re.search(r'^version = "0\.40\.4"$', pyproject, re.MULTILINE)
    assert re.search(r'^__version__ = "0\.40\.4"$', package, re.MULTILINE)
    assert '"package_version": "0.40.4"' in phase1
    assert re.search(r'(?ms)^name = "sports-skills"\nversion = "0\.40\.4"$', lock)
    assert changelog.startswith("## [0.40.4]\n")
    assert "## [Unreleased]" not in changelog
    assert "\n## [0.40.3]\n" in changelog
    entry = changelog.split("\n## [0.40.3]\n", 1)[0]
    assert "`new/MEX.csv`" in entry
    assert "`pagination.pages`" in entry


def test_release_source_and_epoch_match_review_receipt():
    receipt = json.loads(REVIEW_RECEIPT.read_text(encoding="ascii"))
    assert type(receipt) is dict
    assert receipt == {
        "schema": "sports-skills-release-review-receipt-v1",
        "reviewed_source_commit": REVIEWED_SOURCE_COMMIT,
        "reviewed_source_tree": REVIEWED_SOURCE_TREE,
        "source_date_epoch": SOURCE_DATE_EPOCH,
    }
    assert {key: type(value) for key, value in receipt.items()} == {
        "schema": str,
        "reviewed_source_commit": str,
        "reviewed_source_tree": str,
        "source_date_epoch": int,
    }

    release_source = (ROOT / "packaging/release.py").read_text(encoding="utf-8")
    verify_source = (ROOT / "packaging/verify_release.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert f'REVIEWED_SOURCE_COMMIT = "{receipt["reviewed_source_commit"]}"' in release_source
    assert f"SOURCE_DATE_EPOCH = {receipt['source_date_epoch']}" in release_source
    assert f'VERSION = "{VERSION}"' in release_source
    assert f'SOURCE_COMMIT = "{receipt["reviewed_source_commit"]}"' in verify_source
    assert f'VERSION = "{VERSION}"' in verify_source
    assert (
        '"Reviewed source" = '
        f'"https://github.com/machina-sports/sports-skills/tree/{receipt["reviewed_source_commit"]}"'
    ) in pyproject
    assert f'REVIEWED_SOURCE_COMMIT: "{receipt["reviewed_source_commit"]}"' in workflow
    assert f'SOURCE_DATE_EPOCH: "{receipt["source_date_epoch"]}"' in workflow


def test_previous_release_receipt_is_unchanged():
    receipt = json.loads((ROOT / "release/0.40.3/review-receipt.json").read_text(encoding="ascii"))
    assert receipt == {
        "schema": "sports-skills-release-review-receipt-v1",
        "reviewed_source_commit": "14383136375d296d113694bbdcdd4b904dbf23f7",
        "reviewed_source_tree": "7a42cbbd2300f1742d34fd2d23b384ed1122fdf2",
        "source_date_epoch": 1793861403,
    }


def test_both_builds_reproduce_the_checksum_authority(release_builds):
    authority = _authority_rows()
    for wheel, sdist in release_builds:
        assert authority == {_sha256(wheel): WHEEL_NAME, _sha256(sdist): SDIST_NAME}
        _assert_checksum_file_is_not_an_artifact_input(wheel, sdist)


def test_two_clean_builds_are_byte_identical(release_builds):
    (wheel_a, sdist_a), (wheel_b, sdist_b) = release_builds
    assert wheel_a.read_bytes() == wheel_b.read_bytes()
    assert sdist_a.read_bytes() == sdist_b.read_bytes()


def test_artifact_metadata_provenance_license_and_dependencies_are_exact(release_builds):
    wheel, _ = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = email.message_from_bytes(archive.read(metadata_name))

    assert metadata["Name"] == "sports-skills"
    assert metadata["Version"] == VERSION
    assert metadata["Requires-Python"] == ">=3.9.10"
    assert metadata.get_all("License-Expression") == ["MIT"]
    assert metadata.get_all("License-File") == ["LICENSE"]
    assert metadata.get_all("Project-URL") == [
        f"Reviewed source, https://github.com/machina-sports/sports-skills/tree/{REVIEWED_SOURCE_COMMIT}"
    ]
    assert not any(
        requirement.casefold().startswith(("machina-sports-canonical", "machina_sports_canonical"))
        for requirement in metadata.get_all("Requires-Dist", [])
    )


def test_artifact_member_metadata_and_package_inventory_are_exact(release_builds):
    wheel, sdist = release_builds[0]
    source_files = {
        path.relative_to(ROOT / "src").as_posix()
        for path in (ROOT / "src/sports_skills").rglob("*")
        if path.is_file() and path.suffix not in {".pyc", ".pyo"} and "__pycache__" not in path.parts
    }

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        packaged = {name for name in names if name.startswith("sports_skills/")}
        assert packaged == source_files
        assert not any("__pycache__" in name or name.endswith((".pyc", ".pyo")) for name in names)
        assert not any(name.startswith(("tests/", ".hermes/", "release/")) for name in names)
        expected_time = time.gmtime(SOURCE_DATE_EPOCH)[:5] + (SOURCE_DATE_EPOCH % 60 // 2 * 2,)
        assert {item.date_time for item in archive.infolist()} == {expected_time}

    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        prefix = f"sports_skills-{VERSION}/"
        packaged = {
            member.name.removeprefix(prefix + "src/")
            for member in members
            if member.isfile() and member.name.startswith(prefix + "src/sports_skills/")
        }
        assert packaged == source_files
        assert {member.mtime for member in members} == {SOURCE_DATE_EPOCH}
        assert {member.uid for member in members} == {0}
        assert {member.gid for member in members} == {0}
        assert {member.uname for member in members} == {""}
        assert {member.gname for member in members} == {""}
        assert not any(
            part in member.name
            for member in members
            for part in ("/.git/", "/.hermes/", "/release/", "/tests/", "/__pycache__/")
        )


def test_artifacts_ship_the_score_preserving_markets_connector(release_builds):
    wheel, sdist = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_connector = archive.read(MARKETS_CONNECTOR).decode("utf-8")
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_connector = archive.extractfile(f"sports_skills-{VERSION}/src/{MARKETS_CONNECTOR}").read().decode("utf-8")

    assert wheel_connector == sdist_connector == (ROOT / "src" / MARKETS_CONNECTOR).read_text(encoding="utf-8")
    tree = ast.parse(wheel_connector)
    module_imports = {
        name
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module])
    }
    assert not any(name and name.startswith(("requests", "feedparser")) for name in module_imports)
    extract = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_extract_games")
    assert '"score": c.get("score")' in ast.get_source_segment(wheel_connector, extract)


def test_artifacts_ship_the_league_calendar_nba_connector(release_builds):
    wheel, sdist = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_connector = archive.read(NBA_CONNECTOR).decode("utf-8")
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_connector = archive.extractfile(f"sports_skills-{VERSION}/src/{NBA_CONNECTOR}").read().decode("utf-8")

    assert wheel_connector == sdist_connector == (ROOT / "src" / NBA_CONNECTOR).read_text(encoding="utf-8")
    tree = ast.parse(wheel_connector)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert 'LEAGUE_TZ = ZoneInfo("America/New_York")' in wheel_connector
    assert '"game_date": _league_date(' in ast.get_source_segment(wheel_connector, functions["_normalize_event"])
    plays = ast.get_source_segment(wheel_connector, functions["_normalize_plays"])
    assert "_summary_teams(summary_data)" in plays and '"team": abbreviation.get(' in plays
    assert '"day": day_info.get("date", "") or (date or "")' in ast.get_source_segment(
        wheel_connector, functions["get_scoreboard"]
    )


def test_artifacts_ship_the_bpi_paginating_cbb_connector(release_builds):
    wheel, sdist = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_connector = archive.read(CBB_CONNECTOR).decode("utf-8")
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_connector = archive.extractfile(f"sports_skills-{VERSION}/src/{CBB_CONNECTOR}").read().decode("utf-8")

    assert wheel_connector == sdist_connector == (ROOT / "src" / CBB_CONNECTOR).read_text(encoding="utf-8")
    tree = ast.parse(wheel_connector)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    for name in ("_fetch_bpi_for_team", "get_power_index", "get_tournament_projections"):
        body = ast.get_source_segment(wheel_connector, functions[name])
        assert 'pagination.get("pages", 1)' in body
        assert "pageCount" not in body


def test_artifacts_ship_the_liga_mx_football_connector(release_builds):
    wheel, sdist = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_connector = archive.read(FOOTBALL_CONNECTOR).decode("utf-8")
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_connector = (
            archive.extractfile(f"sports_skills-{VERSION}/src/{FOOTBALL_CONNECTOR}").read().decode("utf-8")
        )

    assert wheel_connector == sdist_connector == (ROOT / "src" / FOOTBALL_CONNECTOR).read_text(encoding="utf-8")
    tree = ast.parse(wheel_connector)
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert '"fduk": "MEX"' in wheel_connector
    assert '"MEX": {"season_start_month": 7}' in wheel_connector
    assert "if div in _FDUK_EXTRA_DIVS:" in ast.get_source_segment(wheel_connector, functions["_fduk_fetch_season"])
    assert "clubelo_covers=False" in ast.get_source_segment(wheel_connector, functions["get_team_strength"])


def test_artifacts_ship_polymarket_dated_reads_and_broad_sport_listing(release_builds):
    wheel, sdist = release_builds[0]
    wrapper_name = "sports_skills/polymarket/__init__.py"
    with zipfile.ZipFile(wheel) as archive:
        wheel_wrapper = archive.read(wrapper_name).decode("utf-8")
        wheel_cli = archive.read("sports_skills/cli.py").decode("utf-8")
    with tarfile.open(sdist, "r:gz") as archive:
        prefix = f"sports_skills-{VERSION}/src/"
        sdist_wrapper = archive.extractfile(prefix + wrapper_name).read().decode("utf-8")
        sdist_cli = archive.extractfile(prefix + "sports_skills/cli.py").read().decode("utf-8")

    assert wheel_wrapper == sdist_wrapper == (ROOT / "src" / wrapper_name).read_text(encoding="utf-8")
    assert wheel_cli == sdist_cli == (ROOT / "src/sports_skills/cli.py").read_text(encoding="utf-8")
    for wrapper_source, cli_source in ((wheel_wrapper, wheel_cli), (sdist_wrapper, sdist_cli)):
        wrapper, cli = _polymarket_surface(wrapper_source, cli_source)
        assert cli["get_todays_events"]["required"] == ["sport"]
        assert set(POLYMARKET_TODAYS_PARAMS) <= set(cli["get_todays_events"]["optional"])
        assert {"sport", *POLYMARKET_TODAYS_PARAMS} <= set(wrapper["get_todays_events"])
        assert "sport" in cli["get_sports_events"]["optional"]
        assert "sport" in wrapper["get_sports_events"]


def test_artifacts_ship_gleague_modules_cli_registry_and_storefront(release_builds):
    wheel, sdist = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        assert GLEAGUE_SOURCES | {"sports_skills/_storefront.py"} <= set(archive.namelist())
        cli = archive.read("sports_skills/cli.py").decode("utf-8")

    with tarfile.open(sdist, "r:gz") as archive:
        assert {f"sports_skills-{VERSION}/src/{name}" for name in GLEAGUE_SOURCES} <= set(archive.getnames())

    assert cli == (ROOT / "src/sports_skills/cli.py").read_text(encoding="utf-8")
    gleague = cli.split('    "gleague": {\n', 1)[1].split("\n    },\n", 1)[0]
    assert tuple(re.findall(r'(?m)^        "(\w+)": ', gleague)) == GLEAGUE_COMMANDS
    assert 'if args.module == "storefront":' in cli


def test_artifacts_ship_gemini_module_and_cli_registry_entries(release_builds):
    wheel, sdist = release_builds[0]
    required = {"sports_skills/gemini/__init__.py", "sports_skills/gemini/_connector.py"}
    with zipfile.ZipFile(wheel) as archive:
        assert required <= set(archive.namelist())
        cli = archive.read("sports_skills/cli.py").decode("utf-8")

    with tarfile.open(sdist, "r:gz") as archive:
        assert {f"sports_skills-{VERSION}/src/{name}" for name in required} <= set(archive.getnames())

    assert cli == (ROOT / "src/sports_skills/cli.py").read_text(encoding="utf-8")
    gemini = cli.split('    "gemini": {\n', 1)[1].split("\n    },\n", 1)[0]
    for command in ("get_events", "get_event", "search_markets", "get_todays_events"):
        assert f'"{command}": ' in gemini


def test_wheel_ships_novig_module_and_cli_registry_entries(release_builds):
    wheel, _ = release_builds[0]
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        assert {"sports_skills/novig/__init__.py", "sports_skills/novig/_connector.py"} <= names
        cli = archive.read("sports_skills/cli.py").decode("utf-8")

    assert cli == (ROOT / "src/sports_skills/cli.py").read_text(encoding="utf-8")
    novig = cli.split('    "novig": {\n', 1)[1].split("\n    },\n", 1)[0]
    for command in (
        "get_sports_config",
        "get_events",
        "get_event",
        "get_markets",
        "get_market",
        "get_order_book",
        "search_markets",
        "get_todays_events",
    ):
        assert f'"{command}": ' in novig
    markets = cli.split('    "markets": {\n', 1)[1].split("\n    },\n", 1)[0]
    assert '"compare_market_url": {"required": ["url"]}' in markets


def test_installed_wheel_imports_resources_wrappers_and_owner_inventory(release_builds, tmp_path):
    wheel, _ = release_builds[0]
    environment = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--no-deps", "--no-index", str(wheel)],
        check=True,
        cwd=tmp_path,
    )
    probe = textwrap.dedent(
        f"""
        import hashlib
        import importlib
        import importlib.metadata
        import importlib.resources
        import inspect
        import json
        import pathlib
        import sys
        import types

        distribution = importlib.metadata.distribution("sports-skills")
        assert distribution.version == "{VERSION}"
        root = pathlib.Path(distribution.locate_file(""))
        package = types.ModuleType("sports_skills")
        package.__path__ = [str(root / "sports_skills")]
        package.__package__ = "sports_skills"
        sys.modules["sports_skills"] = package

        canonical = importlib.import_module("sports_skills.canonical")
        football = importlib.import_module("sports_skills.canonical.adapters.football")
        nba = importlib.import_module("sports_skills.canonical.adapters.nba")
        assert pathlib.Path(canonical.__file__).is_relative_to(root)
        assert pathlib.Path(football.__file__).is_relative_to(root)
        assert pathlib.Path(nba.__file__).is_relative_to(root)
        assert str(inspect.signature(canonical.to_successor_envelope)) == "(*, operation, request_bytes, operation_arguments_bytes, output_mode, consumer_tier) -> bytes"
        assert str(inspect.signature(canonical.to_longitudinal_envelope)) == "(*, operation, request_bytes, operation_arguments_bytes, consumer_tier) -> bytes"

        vendored = importlib.resources.files("sports_skills.canonical._vendored")
        receipt = json.loads(vendored.joinpath("VENDORED.json").read_text(encoding="utf-8"))
        runtime = json.loads(vendored.joinpath("data/trusted_loader_manifest_v1.json").read_text(encoding="utf-8"))
        assert receipt["runtime_files"] == runtime["runtime_files"]
        assert receipt["required_data_files"] == runtime["required_data_files"]
        assert receipt["private_symbols"] == runtime["private_symbols"]
        for item in runtime["runtime_files"] + runtime["required_data_files"]:
            payload = vendored.joinpath(item["relative_path"]).read_bytes()
            assert len(payload) == item["byte_length"]
            assert "sha256:" + hashlib.sha256(payload).hexdigest() == item["sha256"]
        successor = importlib.import_module("sports_skills.canonical._vendored.successor")
        assert all(hasattr(successor, item["symbol"]) for item in runtime["private_symbols"])
        assert importlib.util.find_spec("machina_sports_canonical") is None

        connector = importlib.import_module("sports_skills.markets._connector")
        assert pathlib.Path(connector.__file__).is_relative_to(root)
        for sport in {SCOREBOARD_SPORTS!r}:
            games = connector._extract_games(
                sport,
                {{
                    "status": True,
                    "data": {{
                        "events": [
                            {{
                                "id": "live",
                                "competitors": [
                                    {{"home_away": "home", "team": {{"id": "1"}}, "score": 0}},
                                    {{"home_away": "away", "team": {{"id": "2"}}, "score": "0"}},
                                ],
                            }},
                            {{
                                "id": "unknown",
                                "competitors": [
                                    {{"home_away": "home", "team": {{"id": "3"}}}},
                                    {{"home_away": "away", "team": {{"id": "4"}}, "score": None}},
                                ],
                            }},
                        ]
                    }},
                }},
            )
            assert [(game["home"]["score"], game["away"]["score"]) for game in games] == [(0, "0"), (None, None)]
            assert type(games[0]["home"]["score"]) is int
        """
    )
    subprocess.run([str(python), "-I", "-c", probe], check=True, cwd=tmp_path)
    # The same probe the publish workflow runs, including the gleague, storefront,
    # polymarket and markets score-preservation checks.
    subprocess.run([str(python), "-I", str(ROOT / "packaging/probe_installed.py")], check=True, cwd=tmp_path)


def test_installed_probe_checks_polymarket_surface_without_importing_it():
    probe = (ROOT / "packaging/probe_installed.py").read_text(encoding="utf-8")
    tree = ast.parse(probe)
    assert 'VERSION = "0.40.4"' in probe
    assert 'POLYMARKET_TODAYS_PARAMS = ("offset", "date", "timezone", "sports_market_types", "compact")' in probe
    assert '"sports_skills/polymarket/__init__.py"' in probe
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in ([alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module])
    }
    assert not any(name and name.startswith(("requests", "sports_skills.polymarket")) for name in imported)
    assert 'import_module("sports_skills.polymarket' not in probe


def test_installed_probe_runs_the_installed_markets_score_normalizer():
    probe = (ROOT / "packaging/probe_installed.py").read_text(encoding="utf-8")
    assert 'SCOREBOARD_SPORTS = ("nba", "nfl", "mlb", "nhl", "wnba", "cfb", "cbb")' in probe
    assert 'importlib.import_module("sports_skills.markets._connector")' in probe
    assert 'root / "sports_skills/markets/_connector.py"' in probe
    assert "connector._extract_games(sport, scoreboard)" in probe
    assert '[(sport, "synthetic-1", 0, "0"), (sport, "synthetic-2", None, None)]' in probe
    # The markets check must run before the canonical loop rebinds ``root``.
    assert probe.index("sports_skills.markets._connector") < probe.index(
        "for operation, fixture_id, mode in successes:"
    )


def test_installed_probe_runs_the_installed_nba_league_calendar_and_play_teams():
    probe = (ROOT / "packaging/probe_installed.py").read_text(encoding="utf-8")
    assert 'importlib.import_module("sports_skills.nba._connector")' in probe
    assert 'root / "sports_skills/nba/_connector.py"' in probe
    assert 'nba._league_date("2026-11-03T00:30Z")' in probe
    assert "nba._normalize_plays(" in probe
    # The nba check must run before the canonical loop rebinds ``root``.
    assert probe.index("sports_skills.nba._connector") < probe.index("for operation, fixture_id, mode in successes:")


def test_installed_probe_runs_the_installed_cbb_bpi_pagination():
    probe = (ROOT / "packaging/probe_installed.py").read_text(encoding="utf-8")
    assert 'importlib.import_module("sports_skills.cbb._connector")' in probe
    assert 'root / "sports_skills/cbb/_connector.py"' in probe
    assert "cbb.espn_fitt_request = _bpi_page" in probe
    assert 'cbb.get_power_index({"params": {"team_id": "1110"}})' in probe
    assert "bpi_pages != [1, 2, 3]" in probe
    # The cbb check must run before the canonical loop rebinds ``root``.
    assert probe.index("sports_skills.cbb._connector") < probe.index("for operation, fixture_id, mode in successes:")


def test_installed_probe_runs_the_installed_liga_mx_season_slicer():
    probe = (ROOT / "packaging/probe_installed.py").read_text(encoding="utf-8")
    # football._connector needs requests, so the probe compiles the slicer from
    # the installed bytes instead of importing the module.
    assert 'importlib.import_module("sports_skills.football._connector")' not in probe
    assert 'football_path = root / "sports_skills/football/_connector.py"' in probe
    assert '"_fduk_extra_season_code", "_fduk_extra_season_csv"' in probe
    assert 'liga_mx["_fduk_extra_season_csv"](extra, "2627")' in probe
    assert probe.index("football_path = root") < probe.index("for operation, fixture_id, mode in successes:")


def test_publish_workflow_is_tag_triggered_build_once_and_least_privilege():
    workflow = (ROOT / ".github/workflows/publish.yml").read_text(encoding="utf-8")
    assert "types: [published]" not in workflow
    assert not re.search(r"(?m)^  release:\s*$", workflow.split("jobs:", 1)[0])
    assert re.search(r'(?ms)^on:\n  push:\n    tags:\n      - "v\*"$', workflow)
    assert re.search(r"(?ms)^permissions:\n  contents: read$", workflow)
    assert f'RELEASE_VERSION: "{VERSION}"' in workflow
    assert f'REVIEWED_SOURCE_COMMIT: "{REVIEWED_SOURCE_COMMIT}"' in workflow
    assert f'SOURCE_DATE_EPOCH: "{SOURCE_DATE_EPOCH}"' in workflow

    action_refs = re.findall(r"uses:\s+[^@\s]+@([^\s#]+)", workflow)
    assert action_refs
    assert all(re.fullmatch(r"[0-9a-f]{40}", ref) for ref in action_refs)

    build = workflow.split("  build:", 1)[1].split("  verify-installed:", 1)[0]
    verify = workflow.split("  verify-installed:", 1)[1].split("  publish:", 1)[0]
    publish = workflow.split("  publish:", 1)[1].split("  release:", 1)[0]
    release = workflow.split("  release:", 1)[1]
    assert 'test "$GITHUB_REF_NAME" = "v${RELEASE_VERSION}"' in build
    assert 'test "$(git rev-parse HEAD)" = "$GITHUB_SHA"' in build
    assert 'assert package["project"]["version"] == os.environ["RELEASE_VERSION"]' in build
    assert "merge-base" not in workflow
    assert "--is-ancestor" not in workflow
    assert "git diff" not in workflow
    assert "id-token: write" not in build
    assert build.count("packaging/release.py") == 1
    assert 'python-version: ["3.9", "3.14"]' in verify
    assert "packaging/probe_installed.py" in verify
    assert "needs: [build, verify-installed]" in publish
    assert "environment: pypi" in publish
    assert "id-token: write" in publish
    assert "actions/checkout" not in publish
    assert "packaging/release.py" not in publish
    assert "python -m build" not in publish
    assert "sha256sum --check --strict" in publish
    assert "License-Expression" in publish and "License-File" in publish
    assert "needs: publish" in release
    assert "contents: write" in release
    assert "sha256sum --check --strict" in release
    assert "dist/*.whl" in release and "dist/*.tar.gz" in release and "SHA256SUMS" in release


def test_ci_reaches_release_gates_on_python_39_and_current_python():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "paths-ignore" not in workflow and "paths:" not in workflow
    assert "pull_request:" in workflow and "push:" in workflow
    assert '"3.9"' in workflow and '"3.14"' in workflow
    test_job = workflow.split("  test:", 1)[1]
    assert re.search(
        r"(?m)^      - uses: actions/checkout@[^\n]+\n        with:\n          fetch-depth: 0$",
        test_job,
    )
    assert "pytest -v" in workflow
