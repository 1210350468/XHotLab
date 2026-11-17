import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import store, zen
from .config import ROOT

LOGS = ROOT / 'data' / 'agent_logs'
MAX_RUNNING_SECONDS = 900


def available() -> dict:
    return {
        'codex': bool(shutil.which('codex.cmd') or shutil.which('codex')),
        'claude': bool(shutil.which('claude.exe') or shutil.which('claude')),
    }


def validate_workdir(value: str) -> Path:
    folder = Path(value).expanduser().resolve()
    allowed = ROOT.parent.resolve()
    if folder != allowed and allowed not in folder.parents:
        raise ValueError(f'Agent 工作目录必须位于 {allowed} 内')
    if not folder.is_dir():
        raise ValueError('Agent 工作目录不存在')
    return folder


def build_agent_command(job: dict) -> tuple[list[str], dict, str]:
    executable = available()
    provider = job['provider']
    if provider not in executable or not executable[provider]:
        raise ValueError(f'本机尚未安装 {provider} CLI')
    env = os.environ.copy()
    if job['connection'] == 'zen':
        key = zen.get_api_key()
        if not key:
            raise ValueError('需要连接 OpenCode Console 后才能运行 Zen Agent')
        base = ('https://opencode.ai/inference/go' if zen.settings()['plan'] == 'go'
                else 'https://opencode.ai/inference')
        env['OPENCODE_API_KEY'] = key
        env.pop('ANTHROPIC_API_KEY', None)
        env.pop('CLAUDE_CODE_OAUTH_TOKEN', None)
        env['ANTHROPIC_BASE_URL'] = base + '/anthropic'
        env['ANTHROPIC_AUTH_TOKEN'] = key
    elif job['connection'] != 'native':
        raise ValueError('未知的 Agent 认证方式')

    workdir = validate_workdir(job['workdir'])
    mode = job['mode']
    if mode not in ('read-only', 'workspace-write'):
        raise ValueError('工作权限参数无效')
    model = job['model'] or ''
    effort = job['effort']
    background = store.profile()
    prompt = (
        'You are assisting with a Chinese-language X content research and creation project. '
        'Read the requested project and user task carefully. Respect the workspace permission mode. '
        'Any publication on an external social platform needs the user to confirm it inside the official website. '
        'Explain completed actions with actual file paths and verification evidence.\n\n'
        + ('User context for decision-making:\n' + background['content'][:5500] + '\n\n'
           if background['enabled'] else '')
        + 'User task:\n' + job['task']
    )
    if provider == 'codex':
        executable_path = shutil.which('codex.cmd') or shutil.which('codex')
        args = [
            executable_path, 'exec', '--skip-git-repo-check',
            '--sandbox', mode, '--ephemeral', '--json',
        ]
        if job['connection'] == 'zen':
            args.extend([
                '-c', 'model_provider="xhotlab_zen"',
                '-c', 'model_providers.xhotlab_zen.name="OpenCode Console"',
                '-c', f'model_providers.xhotlab_zen.base_url="{base}/openai/v1"',
                '-c', 'model_providers.xhotlab_zen.env_key="OPENCODE_API_KEY"',
                '-c', 'model_providers.xhotlab_zen.wire_api="responses"',
            ])
        if model:
            args.extend(['--model', model])
        if effort not in ('none', ''):
            args.extend(['-c', f'model_reasoning_effort="{effort}"'])
        args.append('-')
    else:
        executable_path = shutil.which('claude.exe') or shutil.which('claude')
        args = [
            executable_path, '--print', '--output-format', 'json',
            '--permission-mode', 'plan' if mode == 'read-only' else 'acceptEdits',
            '--no-session-persistence', '--max-turns', '18',
        ]
        if model:
            args.extend(['--model', model])
        if effort not in ('none', ''):
            args.extend(['--effort', effort])
    return args, env, prompt


def read_output(provider: str, stdout: str) -> str:
    if provider == 'claude':
        response = json.loads(stdout)
        return str(response.get('result') or response.get('errors') or response)[:80000]
    chunks = []
    for line in stdout.splitlines():
        if not line.lstrip().startswith('{'):
            continue
        event = json.loads(line)
        item = event.get('item') or {}
        if item.get('type') == 'agent_message' and event.get('type') in (
            'item.completed', 'item.updated'
        ):
            chunks.append(str(item.get('text') or ''))
    return ('\n\n'.join(chunks) or stdout)[-80000:]


def explain_failure(provider: str, stdout: str, stderr: str) -> str:
    if provider == 'codex':
        for line in stdout.splitlines():
            if not line.lstrip().startswith('{'):
                continue
            event = json.loads(line)
            if event.get('type') in ('turn.failed', 'error'):
                issue = event.get('error') or event.get('message') or ''
                if isinstance(issue, dict):
                    issue = issue.get('message') or str(issue)
                if 'usage limit' in str(issue).lower():
                    return 'Codex 当前账号已达到用量限制。可选择 Zen 认证模式，或使用已授权的 Claude Code。'
                return str(issue)[:6000]
    return (stderr or stdout)[-6000:]


def run(job_id: str) -> None:
    job = store.get_agent_job(job_id)
    if job is None:
        raise ValueError('Agent 任务不存在')
    store.start_agent_job(job_id)
    try:
        command, env, prompt = build_agent_command(job)
        completed = subprocess.run(
            command,
            cwd=job['workdir'],
            input=prompt,
            text=True,
            encoding='utf-8',
            capture_output=True,
            timeout=MAX_RUNNING_SECONDS,
            check=False,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
        )
        key = zen.get_api_key()
        output = completed.stdout.replace(key, '[redacted]') if key else completed.stdout
        stderr = completed.stderr.replace(key, '[redacted]') if key else completed.stderr
        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / f'{job_id}.log').write_text(output[-120000:] + '\n' + stderr[-20000:], encoding='utf-8')
        if completed.returncode != 0:
            store.finish_agent_job(job_id, 'failed', '',
                                   explain_failure(job['provider'], output, stderr))
            return
        store.finish_agent_job(job_id, 'completed', read_output(job['provider'], output), '')
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        store.finish_agent_job(job_id, 'failed', '', f'{type(error).__name__}: {error}')
        raise


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise ValueError('Usage: python -m app.agent_worker <job_id>')
    run(sys.argv[1])
