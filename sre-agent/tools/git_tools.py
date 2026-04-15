"""
Git/GitHub tools for GitOps remediation.
Creates fix branches and PRs against the gitops-repo.
"""
import os
import subprocess
import logging
import tempfile
import shutil
from langchain.tools import tool

logger = logging.getLogger(__name__)

# Configuration from environment variables
GITOPS_REPO_URL = os.getenv("GITOPS_REPO_URL", "")        # e.g. https://github.com/user/sre-gitops
GITOPS_REPO_PATH = os.getenv("GITOPS_REPO_PATH", "/gitops-repo")  # local clone path
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GIT_USER_NAME = os.getenv("GIT_USER_NAME", "SRE-Copilot")
GIT_USER_EMAIL = os.getenv("GIT_USER_EMAIL", "sre-copilot@local")


def _run_git(args: list[str], cwd: str = None, timeout: int = 30) -> tuple[bool, str]:
    """Run a git command and return (success, output)."""
    cmd = ["git"] + args
    env = os.environ.copy()
    if GITHUB_TOKEN:
        env["GIT_ASKPASS"] = "echo"
        env["GIT_PASSWORD"] = GITHUB_TOKEN
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=cwd or GITOPS_REPO_PATH, timeout=timeout, env=env
        )
        output = result.stdout.strip() + result.stderr.strip()
        return result.returncode == 0, output
    except Exception as e:
        return False, str(e)


@tool
def list_gitops_files(input: str) -> str:
    """
    List files in the local gitops repository.
    Input: subdirectory path relative to repo root, e.g. 'apps' or '.'
    """
    target_dir = os.path.join(GITOPS_REPO_PATH, input.strip().lstrip("/"))
    if not os.path.exists(target_dir):
        return f"Directory not found: {target_dir}"
    try:
        files = []
        for root, dirs, filenames in os.walk(target_dir):
            # Skip .git directory
            dirs[:] = [d for d in dirs if d != ".git"]
            for f in filenames:
                rel = os.path.relpath(os.path.join(root, f), GITOPS_REPO_PATH)
                files.append(rel)
        return "\n".join(files) if files else "(empty)"
    except Exception as e:
        return f"ERROR: {e}"


@tool
def read_gitops_file(input: str) -> str:
    """
    Read a file from the local gitops repository.
    Input: file path relative to repo root, e.g. 'apps/demo-app.yaml'
    """
    file_path = os.path.join(GITOPS_REPO_PATH, input.strip().lstrip("/"))
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"
    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"ERROR reading file: {e}"


@tool
def create_fix_pr(input: str) -> str:
    """
    Create a GitOps fix: write a file, commit it on a new branch, and push (or create a local branch if no remote configured).
    Input format (JSON string):
    {
        "branch": "fix/pod-restart-demo",
        "file_path": "apps/demo-app.yaml",
        "file_content": "<full yaml content>",
        "commit_message": "fix: scale down crash-app to prevent restart loop",
        "pr_title": "fix(demo): scale down crash-app"
    }
    """
    import json
    try:
        data = json.loads(input)
    except json.JSONDecodeError as e:
        return f"ERROR: invalid JSON input: {e}"

    branch = data.get("branch", "fix/auto-remediation")
    file_path = data.get("file_path", "")
    file_content = data.get("file_content", "")
    commit_message = data.get("commit_message", "fix: auto-remediation by SRE Copilot")
    pr_title = data.get("pr_title", commit_message)

    if not file_path or not file_content:
        return "ERROR: 'file_path' and 'file_content' are required"

    repo_path = GITOPS_REPO_PATH

    if not os.path.exists(repo_path):
        return f"ERROR: gitops repo not found at {repo_path}"

    # Configure git identity
    _run_git(["config", "user.name", GIT_USER_NAME], cwd=repo_path)
    _run_git(["config", "user.email", GIT_USER_EMAIL], cwd=repo_path)

    # Create and checkout new branch
    ok, out = _run_git(["checkout", "-b", branch], cwd=repo_path)
    if not ok:
        # Branch may already exist; try switching to it
        ok, out = _run_git(["checkout", branch], cwd=repo_path)
        if not ok:
            return f"ERROR creating branch '{branch}': {out}"

    # Write the file
    full_path = os.path.join(repo_path, file_path.lstrip("/"))
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w") as f:
        f.write(file_content)

    # Stage and commit
    ok, out = _run_git(["add", file_path], cwd=repo_path)
    if not ok:
        return f"ERROR staging file: {out}"

    ok, out = _run_git(["commit", "-m", commit_message], cwd=repo_path)
    if not ok:
        return f"ERROR committing: {out}"

    # Push if remote is configured
    if GITOPS_REPO_URL and GITHUB_TOKEN:
        ok, push_out = _run_git(["push", "origin", branch], cwd=repo_path)
        if ok:
            # Extract repo owner/name from URL for PR link
            repo_part = GITOPS_REPO_URL.replace("https://github.com/", "").rstrip(".git")
            pr_url = f"https://github.com/{repo_part}/compare/{branch}?expand=1&title={pr_title.replace(' ', '+')}"
            return f"SUCCESS: branch '{branch}' pushed. Open PR: {pr_url}"
        else:
            return f"Branch committed locally but push failed: {push_out}. Run: git push origin {branch}"
    else:
        return (
            f"SUCCESS: fix committed locally on branch '{branch}'.\n"
            f"To push: set GITOPS_REPO_URL and GITHUB_TOKEN env vars, then run:\n"
            f"  cd {repo_path} && git push origin {branch}"
        )


@tool
def get_git_log(input: str) -> str:
    """
    Get the recent git log from the gitops repository.
    Input: number of commits to show, e.g. '10'
    """
    n = input.strip() or "10"
    ok, out = _run_git(["log", f"--oneline", f"-{n}"])
    return out
