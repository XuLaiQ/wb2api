"""Automatic update checks are pinned to this repository only."""
from __future__ import annotations
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock
from server.services import updater

REPO = 'XuLaiQ/wb2api'
HEAD = 'a' * 40
_ORIGINAL_LOCAL_PROJECT_HEAD = updater._local_project_head

class ProjectUpdateCheckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.temp.name) / 'version-check.json'
        for patcher in (
            mock.patch.object(updater, '_VERSION_CACHE_FILE', self.cache_path),
            mock.patch.object(updater, 'current_version', return_value='v1.0.67'),
            mock.patch.object(updater, '_local_project_head', side_effect=lambda full=False: HEAD if full else HEAD[:8]),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    @staticmethod
    def fake_github(urls, ahead=2):
        def get(url, timeout=15):
            urls.append(url)
            if url == f'https://api.github.com/repos/{REPO}':
                return {'full_name': REPO, 'default_branch': 'main'}
            if url == f'https://api.github.com/repos/{REPO}/commits?sha=main&per_page=1':
                return [{'sha': 'b' * 40, 'html_url': f'https://github.com/{REPO}/commit/' + 'b' * 40,
                         'commit': {'message': 'feat: project update', 'committer': {'date': '2026-09-24T01:00:00Z'}}}]
            if url == f'https://api.github.com/repos/{REPO}/compare/{HEAD}...{"b" * 40}':
                return {'ahead_by': ahead, 'behind_by': 0}
            if url == f'https://api.github.com/repos/{REPO}/releases/latest':
                raise urllib.error.HTTPError(url, 404, 'No release', {}, None)
            raise AssertionError(f'Unexpected repository/API request: {url}')
        return get

    def test_only_queries_current_project(self):
        urls=[]
        with mock.patch.object(updater, '_gh_get', side_effect=self.fake_github(urls)):
            result=updater._fetch_remote_versions()
        self.assertEqual(result['repo'], REPO)
        self.assertEqual(result['project']['latest'], 'bbbbbbbb')
        self.assertEqual(result['project']['ahead'], 2)
        self.assertTrue(result['project']['has_update'])
        self.assertEqual(result['project']['subject'], 'feat: project update')
        self.assertTrue(urls)
        self.assertTrue(all(url.startswith(f'https://api.github.com/repos/{REPO}') for url in urls))
        self.assertFalse(any('ithtelab' in url or 'Sliverkiss' in url for url in urls))
        self.assertNotIn('manager', result)
        self.assertNotIn('upstream', result)

    def test_old_dual_repo_cache_is_ignored(self):
        self.cache_path.write_text(json.dumps({'checked_at': 9999999999,
            'manager': {'latest':'v99.0.0'}, 'upstream': {'latest':'deadbeef'}}), encoding='utf-8')
        urls=[]
        with mock.patch.object(updater, '_gh_get', side_effect=self.fake_github(urls)):
            result=updater.check_updates()
        self.assertEqual(result['project']['repo'], REPO)
        self.assertTrue(result['project']['has_update'])
        self.assertEqual(len(urls), 4)
        self.assertNotIn('manager', result)
        self.assertNotIn('upstream', result)

    def test_current_project_cache_is_reused(self):
        self.cache_path.write_text(json.dumps({'schema': updater._VERSION_CACHE_SCHEMA,
            'repo': REPO, 'checked_at': 9999999999,
            'project': {'current':HEAD[:8], 'latest':HEAD[:8], 'url':'commit-url',
                'release_url':'', 'can_update':False, 'date':'', 'subject':'',
                'ahead':0, 'has_update':False, 'error':''}}), encoding='utf-8')
        with mock.patch.object(updater, '_gh_get', side_effect=AssertionError('must use cache')):
            result=updater.check_updates()
        self.assertFalse(result['project']['has_update'])
        self.assertEqual(result['project']['latest'], HEAD[:8])

    def test_build_marker_supplies_local_commit_when_git_metadata_is_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / '.project-commit').write_text('c' * 40, encoding='utf-8')
            with mock.patch.object(updater.config, 'ROOT', root), \
                    mock.patch.object(updater, '_local_project_head', new=_ORIGINAL_LOCAL_PROJECT_HEAD), \
                    mock.patch.object(updater.subprocess, 'run', side_effect=OSError('git absent')):
                self.assertEqual(updater._local_project_head(), 'cccccccc')
                self.assertEqual(updater._local_project_head(full=True), 'c' * 40)

    def test_split_repository_update_targets_are_rejected(self):
        ok, message = updater.start_update('upstream')
        self.assertFalse(ok)
        self.assertIn('单一 wb2api 项目', message)

    def test_git_credential_helper_is_private_repo_fallback(self):
        completed=type('Completed', (), {'returncode':0, 'stdout':'protocol=https\nhost=github.com\nusername=user\npassword=credential-token\n'})()
        with mock.patch.dict(os.environ, {'WB_GITHUB_TOKEN':'', 'GITHUB_TOKEN':''}), \
             mock.patch.object(updater.subprocess, 'run', return_value=completed) as run:
            self.assertEqual(updater._github_token(), 'credential-token')
        self.assertEqual(run.call_args.args[0], ['git','credential','fill'])
        self.assertEqual(run.call_args.kwargs['timeout'], 4)
        self.assertEqual(run.call_args.kwargs['env']['GIT_TERMINAL_PROMPT'], '0')

    def test_token_is_sent_to_github_api(self):
        captured=[]
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self): return b'{"tag_name":"v1.0.68"}'
        with mock.patch.dict(os.environ, {'WB_GITHUB_TOKEN':'secret-test-token'}), \
             mock.patch.object(updater.urllib.request, 'urlopen', side_effect=lambda req, timeout: (captured.append(req) or Response())):
            updater._gh_get(f'https://api.github.com/repos/{REPO}/releases/latest')
        self.assertEqual(captured[0].get_header('Authorization'), 'Bearer secret-test-token')

if __name__ == '__main__':
    unittest.main()
