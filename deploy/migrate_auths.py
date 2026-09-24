from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path


def _is_legacy_path(value: object, root: Path, source: Path) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    candidate = Path(value.strip())
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate.resolve(strict=False) == source.resolve(strict=False)


def _atomic_write(path: Path, content: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _updated_env(path: Path, root: Path, source: Path) -> str | None:
    if not path.is_file():
        return None
    # newline='' preserves the user's existing CRLF/LF style and unrelated values.
    with path.open('r', encoding='utf-8', newline='') as stream:
        text = stream.read()
    changed = False
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        match = re.match(r'^(\s*WB_AUTH_DIR\s*=\s*)([^#\r\n]*)(.*)$', line)
        if match and _is_legacy_path(match.group(2).strip().strip('"\''), root, source):
            raw_value = match.group(2)
            trailing_space = raw_value[len(raw_value.rstrip()):]
            ending = '\r\n' if line.endswith('\r\n') else '\n' if line.endswith('\n') else ''
            line = f'{match.group(1)}./data/auths{trailing_space}{match.group(3)}{ending}'
            changed = True
        lines.append(line)
    return ''.join(lines) if changed else None


def migrate(root: Path) -> tuple[int, bool]:
    """Move old credentials, refusing conflicts before changing files or settings."""
    root = root.resolve()
    source = root / 'auths'
    destination = root / 'data' / 'auths'
    files: list[Path] = []

    if source.exists():
        if source.is_symlink() or not source.is_dir():
            raise ValueError(f'Legacy auth path is not a real directory: {source}')
        for item in source.rglob('*'):
            if item.is_symlink():
                raise ValueError(f'Refusing symlink in credential directory: {item}')
            if item.is_file():
                files.append(item)
            elif not item.is_dir():
                raise ValueError(f'Unsupported entry in credential directory: {item}')

    # Preflight collisions and parse settings first, so malformed settings cannot leave
    # the credentials moved while the application still points at the old directory.
    duplicates: list[Path] = []
    for old_file in files:
        target = destination / old_file.relative_to(source)
        if target.exists():
            if not target.is_file() or old_file.read_bytes() != target.read_bytes():
                raise FileExistsError(f'Conflicting credential files: {old_file} and {target}')
            duplicates.append(old_file)

    config_path = root / 'config.json'
    config: dict | None = None
    config_needs_update = False
    if config_path.is_file():
        loaded = json.loads(config_path.read_text(encoding='utf-8'))
        if isinstance(loaded, dict):
            config = loaded
            config_needs_update = _is_legacy_path(config.get('auth_dir'), root, source)
    env_path = root / '.env'
    env_content = _updated_env(env_path, root, source)

    moved = 0
    if files:
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        for old_file in files:
            target = destination / old_file.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if old_file in duplicates:
                old_file.unlink()
            else:
                shutil.move(str(old_file), str(target))
                moved += 1
        # Remove only directories made empty by moving these files; never recursive-delete.
        for directory in sorted((p for p in source.rglob('*') if p.is_dir()),
                                key=lambda p: len(p.parts), reverse=True):
            directory.rmdir()
        source.rmdir()

    updated = False
    if config is not None and config_needs_update:
        config['auth_dir'] = './data/auths'
        _atomic_write(config_path, json.dumps(config, ensure_ascii=False, indent=2) + '\n')
        updated = True
    if env_content is not None:
        _atomic_write(env_path, env_content)
        updated = True

    # An empty legacy directory is safe to remove; non-empty/unrecognized contents remain.
    if source.is_dir():
        try:
            source.rmdir()
        except OSError:
            pass
    return moved, updated


def main() -> int:
    parser = argparse.ArgumentParser(description='Safely migrate legacy root auths/ to data/auths/.')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1],
                        help='project/deployment root (defaults to this checkout)')
    args = parser.parse_args()
    try:
        moved, updated = migrate(args.root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(f'Migrated {moved} credential file(s) into data/auths/.')
    if updated:
        print('Updated legacy auth directory settings in config.json and/or .env.')
    print('No credential contents were printed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
