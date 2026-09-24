from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    'migrate_auths', _ROOT / 'deploy' / 'migrate_auths.py',
)
assert _SPEC and _SPEC.loader
_MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MIGRATION)


class AuthDirectoryMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'auths').mkdir()
        (self.root / 'auths' / 'workbuddy-u1.json').write_text(
            '{"auth":{"accessToken":"fixture"}}', encoding='utf-8',
        )
        (self.root / 'config.json').write_text(json.dumps({
            'auth_dir': './auths', 'api_key': 'keep-this-setting',
        }), encoding='utf-8')
        (self.root / '.env').write_text(
            'WB_AUTH_DIR=./auths  # legacy path\nWB_ADMIN_PASSWORD=keep-this-secret\n',
            encoding='utf-8',
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_moves_files_and_updates_legacy_paths(self) -> None:
        moved, changed = _MIGRATION.migrate(self.root)
        self.assertEqual(moved, 1)
        self.assertTrue(changed)
        self.assertFalse((self.root / 'auths').exists())
        self.assertEqual(
            (self.root / 'data' / 'auths' / 'workbuddy-u1.json').read_text(encoding='utf-8'),
            '{"auth":{"accessToken":"fixture"}}',
        )
        config = json.loads((self.root / 'config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['auth_dir'], './data/auths')
        self.assertEqual(config['api_key'], 'keep-this-setting')
        env = (self.root / '.env').read_text(encoding='utf-8')
        self.assertIn('WB_AUTH_DIR=./data/auths  # legacy path', env)
        self.assertIn('WB_ADMIN_PASSWORD=keep-this-secret', env)

    def test_migration_is_idempotent(self) -> None:
        _MIGRATION.migrate(self.root)
        self.assertEqual(_MIGRATION.migrate(self.root), (0, False))

    def test_conflict_aborts_before_moving_any_credentials(self) -> None:
        target = self.root / 'data' / 'auths' / 'workbuddy-u1.json'
        target.parent.mkdir(parents=True)
        target.write_text('{"different":true}', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            _MIGRATION.migrate(self.root)
        self.assertTrue((self.root / 'auths' / 'workbuddy-u1.json').is_file())
        config = json.loads((self.root / 'config.json').read_text(encoding='utf-8'))
        self.assertEqual(config['auth_dir'], './auths')

    def test_installer_runs_migration_before_starting_service(self) -> None:
        installer = (_ROOT / 'deploy' / 'install.sh').read_text(encoding='utf-8')
        self.assertIn('deploy/migrate_auths.py', installer)

    def test_custom_auth_directory_is_preserved(self) -> None:
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps({'auth_dir': '/srv/secure/accounts'}), encoding='utf-8')
        _MIGRATION.migrate(self.root)
        config = json.loads(config_path.read_text(encoding='utf-8'))
        self.assertEqual(config['auth_dir'], '/srv/secure/accounts')


if __name__ == '__main__':
    unittest.main()
