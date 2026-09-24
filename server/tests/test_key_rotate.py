"""API key rotation returns a one-time secret without persisting plaintext."""
from __future__ import annotations

import unittest
from unittest import mock

from server import keysvc


class RotateKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.old = {
            'id': 7, 'name': 'agent', 'key_hash': 'old-hash', 'prefix': 'wbk_oldprefix',
            'enabled': 1, 'expires_at': None, 'max_ips': 0, 'ip_allowlist': '[]',
            'models': '[]', 'realm': 'cn', 'quota': 0, 'used_tokens': 0,
            'quota_credit': 0, 'used_credit': 0, 'created_at': 1, 'last_used_at': None,
        }

    def test_rotates_hash_and_returns_new_secret_once(self) -> None:
        fresh = dict(self.old)
        with mock.patch.object(keysvc.db, 'query_one', side_effect=[self.old, fresh]) as query, \
                mock.patch.object(keysvc.db, 'execute') as execute:
            result = keysvc.rotate_key(7)

        self.assertIsNotNone(result)
        self.assertEqual(query.call_count, 2)
        self.assertEqual(execute.call_count, 1)
        sql, params = execute.call_args.args
        self.assertIn('UPDATE api_keys SET key_hash = ?, prefix = ?', sql)
        secret_hash, prefix, key_id = params
        self.assertEqual(key_id, 7)
        self.assertTrue(result['key'].startswith(keysvc.TOKEN_PREFIX))
        self.assertEqual(prefix, result['key'][:12])
        self.assertEqual(secret_hash, keysvc._hash(result['key']))
        self.assertNotEqual(secret_hash, self.old['key_hash'])

    def test_missing_key_returns_none(self) -> None:
        with mock.patch.object(keysvc.db, 'query_one', return_value=None), \
                mock.patch.object(keysvc.db, 'execute') as execute:
            self.assertIsNone(keysvc.rotate_key(404))
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
