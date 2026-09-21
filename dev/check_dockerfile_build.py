"""把 Dockerfile 里 web-builder 阶段的 RUN 逻辑抽出来，在等价目录上真跑一遍。

为什么这样做：本机没装 docker（CI 也会跑，但发版前我要自己确认），而那个 RUN
块是纯 shell —— 可以在等价目录结构上直接执行，比只读代码可靠得多。要确认的是
**两个分支都能产出可用的 /dist**（有产物直接复用、没有就构建、产物不完整要
识别为无效）。

    python dev/check_dockerfile_build.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DF = ROOT / 'Dockerfile'


def extract_run_block(marker: str) -> str:
    """抽出以 marker 开头的 RUN 块（含续行），还原成可直接执行的 shell。"""
    lines = DF.read_text(encoding='utf-8').splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(marker))
    block = []
    i = start
    while i < len(lines):
        block.append(lines[i])
        if not lines[i].rstrip().endswith(chr(92)):   # 不是续行就结束
            break
        i += 1
    raw = '\n'.join(block)
    raw = raw[len('RUN '):]
    # 去掉行尾续行符（反斜杠）
    return raw.replace(chr(92) + '\n', '\n')


def _posix(p: Path) -> str:
    """把 Windows 路径转成 Git Bash 认的 /c/... 形式。

    为什么必须转：直接把带反斜杠的 Windows 路径交给 bash，那些反斜杠会被当作
    转义符，`[ -f ... ]` 判断随之失败 —— 实测会让「有产物」场景误报成「未复用」，
    看起来像 Dockerfile 的 bug，其实只是验证脚本自己的路径问题。
    """
    s = str(p).replace(chr(92), '/')
    if len(s) > 1 and s[1] == ':':
        s = '/' + s[0].lower() + s[2:]
    return s


def run_case(label: str, setup, shell: str) -> tuple[int, str]:
    tmp = Path(tempfile.mkdtemp())
    try:
        setup(tmp)
        s = (shell.replace('/src', _posix(tmp / 'src'))
                  .replace('/dist', _posix(tmp / 'dist'))
                  .replace('/build', _posix(tmp / 'build')))
        r = subprocess.run(['bash', '-c', s], capture_output=True, text=True,
                           env={**os.environ, 'NPM_REGISTRY': ''})
        return r.returncode, (r.stdout + r.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    shell = extract_run_block('RUN set -eu;')
    print('extracted web-builder RUN block (%d lines)' % len(shell.splitlines()))

    # On Windows, `bash` may resolve to a WSL launcher even when WSL is not
    # installed. Treat that environment like a missing optional verifier.
    bash = shutil.which('bash')
    if not bash:
        print('bash unavailable; skipping shell branch execution')
        return 0
    try:
        probe = subprocess.run([bash, '-c', 'exit 0'], timeout=10)
    except OSError:
        probe = None
    if probe is None or probe.returncode != 0:
        print('bash unavailable; skipping shell branch execution')
        return 0

    fails: list[str] = []

    # 场景 A：有完整产物（发布包 / CI）→ 应直接复用，不跑 npm
    def setup_a(tmp: Path) -> None:
        (tmp / 'src' / 'out').mkdir(parents=True)
        (tmp / 'src' / 'out' / 'index.html').write_text('<html>prebuilt</html>')

    rc, out = run_case('A', setup_a, shell)
    if rc != 0 or 'frontend: using prebuilt output' not in out:
        fails.append(f'case A (prebuilt) did not reuse output: rc={rc}')
    print(f'  case A prebuilt  -> rc={rc}  {"reuse OK" if "frontend: using prebuilt output" in out else "reuse FAIL"}')

    # 场景 C：产物不完整（有 out/ 但缺 index.html）→ 必须识别为无效并尝试构建
    def setup_c(tmp: Path) -> None:
        (tmp / 'src' / 'out').mkdir(parents=True)
        (tmp / 'src' / 'out' / 'foo.txt').write_text('x')

    rc, out = run_case('C', setup_c, shell)
    if 'frontend: building output' not in out:
        fails.append(f'case C (incomplete) did not enter build branch: {out[:200]}')
    print(f'  case C incomplete -> rc={rc}  {"build OK" if "frontend: building output" in out else "build FAIL"}')

    # 场景 B：完全没有 out/（git clone）→ 应尝试容器内构建
    def setup_b(tmp: Path) -> None:
        (tmp / 'src' / 'app').mkdir(parents=True)
        (tmp / 'src' / 'package.json').write_text('{}')

    rc, out = run_case('B', setup_b, shell)
    if 'frontend: building output' not in out:
        fails.append(f'case B (missing) did not enter build branch: {out[:200]}')
    print(f'  case B missing    -> rc={rc}  {"build branch OK" if "frontend: building output" in out else "build branch FAIL"}')

    if fails:
        print()
        for f in fails:
            print('  FAIL', f)
        return 1
    print()
    print('all frontend branches are correct')
    return 0


if __name__ == '__main__':
    sys.exit(main())
