import os
import subprocess
import sys
from pathlib import Path

from . import agent_worker, store, zen
from .config import ROOT


def submit(provider: str, connection: str, model: str | None, effort: str,
           mode: str, task: str, workdir: str, approved: bool) -> dict:
    if not approved:
        raise ValueError('启动本机 Agent 前需要用户明确授权')
    if provider not in ('codex', 'claude'):
        raise ValueError('只支持 Codex 与 Claude Code')
    if connection not in ('zen', 'native'):
        raise ValueError('请选择 Zen 或本机已有账号')
    if not agent_worker.available()[provider]:
        raise ValueError(f'本机尚未安装 {provider} CLI')
    if connection == 'zen' and not zen.get_api_key():
        raise ValueError('请先连接 Zen API Key')
    if mode not in ('read-only', 'workspace-write'):
        raise ValueError('选择的操作权限无效')
    if not task.strip() or len(task) > 12000:
        raise ValueError('请提供有效的 Agent 任务')
    folder = agent_worker.validate_workdir(workdir or str(ROOT))
    job = store.new_agent_job(
        provider, connection, model, effort, mode, task.strip(), str(folder),
    )
    worker = sys.executable
    flags = 0
    if sys.platform == 'win32':
        worker = str(Path(sys.executable).with_name('pythonw.exe'))
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        [worker, '-m', 'app.agent_worker', job['id']],
        cwd=str(ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
        close_fds=True,
        start_new_session=sys.platform != 'win32',
    )
    return job
