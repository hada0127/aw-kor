"""Explicit setup and offline verification of the pinned hancharacter checkout."""
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'data/localization_tools.lock.json'


def git(path, *arguments):
    return subprocess.check_output(['git', '-C', str(path), *arguments], text=True).strip()


def specification():
    return json.loads(LOCK.read_text())['hancharacter']


def verified_checkout():
    spec = specification()
    path = ROOT / spec['checkout']
    if not path.is_dir():
        raise ValueError('Run python3 tools/localization_dependencies.py --setup first')
    if git(path, 'rev-parse', 'HEAD') != spec['revision']:
        raise ValueError('hancharacter revision differs from lock')
    if git(path, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('hancharacter checkout has local changes')
    return path


def setup():
    spec = specification()
    path = ROOT / spec['checkout']
    if not path.exists():
        path.mkdir(parents=True)
        subprocess.run(['git', 'init', str(path)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(path), 'remote', 'add', 'origin', spec['url']], check=True)
    try:
        git(path, 'rev-parse', '--verify', 'HEAD')
    except subprocess.CalledProcessError:
        if git(path, 'remote', 'get-url', 'origin') != spec['url'] or git(path, 'status', '--porcelain', '--untracked-files=all'):
            raise ValueError('Refusing to modify a nonempty or unrelated incomplete checkout')
        subprocess.run(['git', '-C', str(path), 'fetch', '--depth', '1', 'origin', spec['revision']], check=True)
        subprocess.run(['git', '-C', str(path), 'checkout', '--detach', spec['revision']], check=True)
    return verified_checkout()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', action='store_true', help='Explicit network checkout; no pip install or service')
    args = parser.parse_args()
    print(setup() if args.setup else verified_checkout())
