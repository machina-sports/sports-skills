"""Build the 0.33.0 wheel and sdist with one reviewed source epoch."""

import gzip
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REVIEWED_SOURCE_COMMIT = "3b135bb324a39710df024a22e8d9fba434b8e6a2"
SOURCE_DATE_EPOCH = 1786998548
VERSION = "0.33.0"
EXPECTED_FILES = {
    f"sports_skills-{VERSION}-py3-none-any.whl",
    f"sports_skills-{VERSION}.tar.gz",
}


def _normalize_sdist(path):
    normalized = path.with_suffix(path.suffix + ".normalized")
    with (
        tarfile.open(path, "r:gz") as source,
        normalized.open("wb") as raw,
        gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=SOURCE_DATE_EPOCH) as compressed,
        tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as target,
    ):
        for member in source.getmembers():
            payload = source.extractfile(member) if member.isfile() else None
            member.uid = 0
            member.gid = 0
            member.uname = ""
            member.gname = ""
            member.mtime = SOURCE_DATE_EPOCH
            member.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
            member.pax_headers = {}
            target.addfile(member, payload)
    normalized.replace(path)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: release.py SOURCE_ROOT OUTPUT_DIRECTORY")
    if os.environ.get("SOURCE_DATE_EPOCH") != str(SOURCE_DATE_EPOCH):
        raise SystemExit(f"SOURCE_DATE_EPOCH must be {SOURCE_DATE_EPOCH} ({REVIEWED_SOURCE_COMMIT})")

    root = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise SystemExit(f"output directory must be empty: {output}")

    with tempfile.TemporaryDirectory(prefix="sports-skills-release-") as temporary:
        staging = Path(temporary)
        subprocess.run(
            [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(staging), str(root)],
            check=True,
            cwd=root,
            env={**os.environ, "SOURCE_DATE_EPOCH": str(SOURCE_DATE_EPOCH)},
        )
        found = {path.name for path in staging.iterdir()}
        if found != EXPECTED_FILES:
            raise SystemExit(f"unexpected artifact inventory: {sorted(found)}")
        _normalize_sdist(staging / f"sports_skills-{VERSION}.tar.gz")
        for artifact in sorted(staging.iterdir()):
            shutil.copyfile(artifact, output / artifact.name)


if __name__ == "__main__":
    main()
