"""ControlDeck version: <yyyy>.<mm>.<dd>.<build>, e.g. 2026.10.05.27.

The date is the build day in Europe/Amsterdam; <build> is the ever-increasing GitHub Actions run
number of the CI workflow. CI computes the version for every build, so no file has to be edited
by hand. Local builds without a build number are "development".
"""
import argparse
import datetime
import re

DEVELOPMENT = "development"
PATTERN = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\.([1-9]\d{0,8})")


def build_version(day, build):
    if not isinstance(build, int) or isinstance(build, bool) or build < 1:
        raise ValueError("Build number must be a positive integer")
    return f"{day:%Y.%m.%d}.{build}"


def validate(version):
    """Accepts a CalVer build version or "development"; rejects anything else, including impossible dates."""
    if version == DEVELOPMENT:
        return version
    match = PATTERN.fullmatch(version) if isinstance(version, str) else None
    if not match:
        raise ValueError(f"Invalid version {version!r}; expected yyyy.mm.dd.build")
    datetime.date(int(match[1]), int(match[2]), int(match[3]))
    return version


def today():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    except Exception:  # No time zone database (e.g. bare Windows): fall back to UTC.
        return datetime.datetime.now(datetime.timezone.utc).date()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--build", type=int, help="CI run number")
    group.add_argument("--check", help="validate a version string")
    args = parser.parse_args()
    print(validate(args.check) if args.check is not None else build_version(today(), args.build))


if __name__ == "__main__":
    main()
