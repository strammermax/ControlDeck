"""Collect installed Python distribution license notices for the shipped runtime."""
import argparse
from importlib import metadata
from pathlib import Path


def collect(requirements):
    notices = []
    for line in Path(requirements).read_text().splitlines():
        if '==' not in line:
            continue
        name = line.split('==')[0].strip()
        try:
            package = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue  # For example Gunicorn is absent in Windows development environments.
        notices.append(f"\n{'=' * 72}\n{name} {package.version}\n")
        for file in package.files or []:
            if '.dist-info' not in str(file) or not any(word in file.name.upper() for word in ('LICENSE', 'COPYING', 'NOTICE')):
                continue
            path = package.locate_file(file)
            if path.is_file():
                notices.append(f"\n{file.name}\n{path.read_text(encoding='utf-8', errors='replace')}\n")
    return 'Python dependency license notices — generated from installed distributions.\n' + ''.join(notices)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(collect(Path(__file__).resolve().parent.parent / 'requirements.txt'), encoding='utf-8')
