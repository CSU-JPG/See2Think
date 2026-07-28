from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import paramiko


HOST = os.environ["SEE2THINK_REMOTE_HOST"]
PORT = int(os.environ.get("SEE2THINK_REMOTE_PORT", "22"))
USER = os.environ.get("SEE2THINK_REMOTE_USER", "root")
PASSWORD = os.environ["SEE2THINK_REMOTE_PASSWORD"]
REMOTE_RUN_MARKER = os.environ.get("SEE2THINK_REMOTE_RUN_MARKER", "remote_task_lists/qwen3vl32b_vaot_no_render_remaining_1063.json")
REMOTE_ROOT = os.environ.get(
    "SEE2THINK_REMOTE_OUTPUT_ROOT",
    "/root/autodl-tmp/See2Think/newtasks/final1200_qwen3-vl-32b-thinking_vaot_no_render",
)
LOCAL_ROOT = Path(
    os.environ.get(
        "SEE2THINK_LOCAL_OUTPUT_ROOT",
        "newtasks/final1200_qwen3-vl-32b-thinking_vaot_no_render",
    )
)
POLL_SECONDS = int(os.environ.get("SEE2THINK_REMOTE_POLL_SECONDS", "7200"))


def connect() -> paramiko.SSHClient:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        port=PORT,
        username=USER,
        password=PASSWORD,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
    )
    return ssh


def remote_running(ssh: paramiko.SSHClient) -> bool:
    cmd = (
        "ps -eo pid,cmd | "
        f"grep -F {shell_quote(REMOTE_RUN_MARKER)} | "
        "grep -v grep >/dev/null && echo RUNNING || echo DONE"
    )
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", "replace").strip()
    err = stderr.read().decode("utf-8", "replace").strip()
    if err:
        print(f"[remote stderr] {err}", flush=True)
    return "RUNNING" in out


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def ensure_local_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def download_tree(sftp: paramiko.SFTPClient, remote_dir: str, local_dir: Path) -> None:
    ensure_local_dir(local_dir)
    for item in sftp.listdir_attr(remote_dir):
        name = item.filename
        if name in {".", ".."}:
            continue
        rpath = remote_dir.rstrip("/") + "/" + name
        lpath = local_dir / name
        mode = item.st_mode
        if mode & 0o040000:
            download_tree(sftp, rpath, lpath)
        else:
            ensure_local_dir(lpath.parent)
            tmp = lpath.with_suffix(lpath.suffix + ".tmp")
            sftp.get(rpath, str(tmp))
            tmp.replace(lpath)


def main() -> int:
    print(f"[monitor] remote marker: {REMOTE_RUN_MARKER}", flush=True)
    print(f"[monitor] remote output: {REMOTE_ROOT}", flush=True)
    print(f"[monitor] local output:  {LOCAL_ROOT.resolve()}", flush=True)
    while True:
        try:
            ssh = connect()
            try:
                if remote_running(ssh):
                    print(f"[monitor] still running; next check in {POLL_SECONDS}s", flush=True)
                else:
                    print("[monitor] remote run finished; downloading output tree", flush=True)
                    sftp = ssh.open_sftp()
                    try:
                        download_tree(sftp, REMOTE_ROOT, LOCAL_ROOT)
                    finally:
                        sftp.close()
                    print("[monitor] download complete", flush=True)
                    return 0
            finally:
                ssh.close()
        except Exception as exc:
            print(f"[monitor] error: {exc!r}; retry in {POLL_SECONDS}s", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
