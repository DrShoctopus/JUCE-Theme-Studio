"""Git status, diff, stage, and commit (explicit user action only)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

git: Any = None
try:
    import git as git_module
except ImportError:
    pass
else:
    git = git_module


class GitCommandError(RuntimeError):
    """Raised when a git CLI command fails."""


@dataclass
class GitStatus:
    is_repo: bool = False
    branch: str = ""
    changed_files: list[str] = field(default_factory=list)
    untracked_files: list[str] = field(default_factory=list)
    has_unrelated_changes: bool = False


@dataclass
class GitDiff:
    path: str
    diff_text: str


def detect_git_repo(project_root: Path) -> bool:
    if git is not None:
        try:
            _ = git.Repo(project_root, search_parent_directories=True)
            return True
        except Exception:
            return False
    return (project_root / ".git").exists()


def get_status(project_root: Path, studio_relative: str = ".juce_theme_studio") -> GitStatus:
    status = GitStatus()
    if not detect_git_repo(project_root):
        return status

    status.is_repo = True

    if git is not None:
        try:
            repo = git.Repo(project_root, search_parent_directories=True)
            status.branch = repo.active_branch.name if not repo.head.is_detached else "DETACHED"
            for item in repo.index.diff(None):
                if item.a_path is not None:
                    status.changed_files.append(item.a_path)
            for item in repo.index.diff("HEAD"):
                if item.a_path is not None and item.a_path not in status.changed_files:
                    status.changed_files.append(item.a_path)
            status.untracked_files = list(repo.untracked_files)
        except Exception:
            pass
    else:
        status.branch = _git_cmd(project_root, "rev-parse", "--abbrev-ref", "HEAD") or ""
        porcelain = _git_cmd(project_root, "status", "--porcelain")
        if porcelain:
            for line in porcelain.splitlines():
                path = line[3:].strip()
                if line.startswith("??"):
                    status.untracked_files.append(path)
                else:
                    status.changed_files.append(path)

    studio_prefix = studio_relative.rstrip("/") + "/"
    all_files = set(status.changed_files) | set(status.untracked_files)
    theme_files = [f for f in all_files if f.startswith(studio_prefix) or f == studio_relative]
    other = [f for f in all_files if f not in theme_files]
    status.has_unrelated_changes = bool(other)
    return status


def get_diff(project_root: Path, file_path: str) -> GitDiff:
    if git is not None:
        try:
            repo = git.Repo(project_root, search_parent_directories=True)
            diff = repo.git.diff(file_path)
            if not diff and file_path in repo.untracked_files:
                diff = f"New untracked file: {file_path}"
            return GitDiff(file_path, diff)
        except Exception as exc:
            return GitDiff(file_path, str(exc))
    text = _git_cmd(project_root, "diff", file_path) or ""
    return GitDiff(file_path, text)


def create_backup_branch(project_root: Path, base_name: str = "theme-studio-backup") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch_name = f"{base_name}-{ts}"
    if git is not None:
        repo = git.Repo(project_root, search_parent_directories=True)
        if branch_name in {h.name for h in repo.heads}:
            raise GitCommandError(f"Branch already exists: {branch_name}")
        repo.git.checkout("-b", branch_name)
        return branch_name
    rc = _git_cmd_rc(project_root, "checkout", "-b", branch_name)
    if rc != 0:
        raise GitCommandError(f"Failed to create branch: {branch_name}")
    return branch_name


def stage_files(project_root: Path, files: list[str]) -> None:
    if not files:
        return
    if git is not None:
        repo = git.Repo(project_root, search_parent_directories=True)
        repo.index.add(files)
        return
    rc = _git_cmd_rc(project_root, "add", *files)
    if rc != 0:
        raise GitCommandError("git add failed")


def commit(project_root: Path, message: str, files: list[str] | None = None) -> str:
    """Commit only when explicitly called — never auto-commit."""
    if files:
        stage_files(project_root, files)
    if git is not None:
        repo = git.Repo(project_root, search_parent_directories=True)
        commit_obj = repo.index.commit(message)
        return str(commit_obj.hexsha[:8])
    rc = _git_cmd_rc(project_root, "commit", "-m", message)
    if rc != 0:
        raise GitCommandError("git commit failed — nothing staged or commit rejected")
    sha = _git_cmd(project_root, "rev-parse", "--short", "HEAD")
    if not sha:
        raise GitCommandError("git commit succeeded but rev-parse failed")
    return sha


def _git_cmd(project_root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return (result.stdout or result.stderr).strip()
    except OSError:
        return ""


def _git_cmd_rc(project_root: Path, *args: str) -> int:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode
    except OSError:
        return 1
