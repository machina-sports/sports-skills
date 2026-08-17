"""Fail-closed verification for the exact sports-skills 0.33.0 artifacts."""

import email
import hashlib
import re
import sys
import tarfile
import zipfile
from pathlib import Path

VERSION = "0.33.0"
SOURCE_COMMIT = "3b135bb324a39710df024a22e8d9fba434b8e6a2"
EXPECTED = [
    f"sports_skills-{VERSION}-py3-none-any.whl",
    f"sports_skills-{VERSION}.tar.gz",
]


def _authority(path):
    rows = path.read_text(encoding="ascii").splitlines()
    if len(rows) != 2:
        raise SystemExit("SHA256SUMS must contain exactly two rows")
    result = {}
    for row in rows:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", row)
        if match is None:
            raise SystemExit(f"invalid SHA256SUMS row: {row!r}")
        digest, name = match.groups()
        result[name] = digest
    if list(result) != EXPECTED:
        raise SystemExit(f"unexpected SHA256SUMS inventory: {list(result)}")
    return result


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_release.py DIST_DIRECTORY SHA256SUMS")
    dist = Path(sys.argv[1])
    authority = _authority(Path(sys.argv[2]))
    if sorted(path.name for path in dist.iterdir()) != sorted(EXPECTED):
        raise SystemExit("dist must contain exactly the release wheel and sdist")
    for name, expected_digest in authority.items():
        digest = hashlib.sha256((dist / name).read_bytes()).hexdigest()
        if digest != expected_digest:
            raise SystemExit(f"checksum mismatch for {name}: {digest}")

    wheel = dist / EXPECTED[0]
    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise SystemExit("wheel must contain exactly one METADATA file")
        metadata = email.message_from_bytes(archive.read(metadata_names[0]))
        wheel_names = archive.namelist()
    expected_source = f"Reviewed source, https://github.com/machina-sports/sports-skills/tree/{SOURCE_COMMIT}"
    checks = {
        "name": metadata["Name"] == "sports-skills",
        "version": metadata["Version"] == VERSION,
        "python": metadata["Requires-Python"] == ">=3.9.10",
        "license expression": metadata.get_all("License-Expression") == ["MIT"],
        "license file": metadata.get_all("License-File") == ["LICENSE"],
        "source provenance": metadata.get_all("Project-URL") == [expected_source],
        "external canonical dependency": not any(
            requirement.casefold().startswith(("machina-sports-canonical", "machina_sports_canonical"))
            for requirement in metadata.get_all("Requires-Dist", [])
        ),
        "checksum self-reference": not any(name.endswith("SHA256SUMS") for name in wheel_names),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise SystemExit("artifact metadata gate failed: " + ", ".join(failed))

    with tarfile.open(dist / EXPECTED[1], "r:gz") as archive:
        sdist_names = archive.getnames()
    if any(name.endswith("SHA256SUMS") for name in sdist_names):
        raise SystemExit("sdist contains its checksum authority")

    print(f"wheel members ({len(wheel_names)}):")
    print("\n".join(wheel_names))
    print(f"sdist members ({len(sdist_names)}):")
    print("\n".join(sdist_names))


if __name__ == "__main__":
    main()
