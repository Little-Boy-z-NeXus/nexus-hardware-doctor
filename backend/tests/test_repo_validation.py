"""Local .env is supported while tracked or unignored credential files fail checks."""

import runpy
import subprocess
from pathlib import Path

VALIDATE = runpy.run_path(str(Path(__file__).parents[2] / "scripts/validate_repo.py"))[
    "validate_secret_files"
]


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_ignored_local_env_is_allowed_but_forced_tracking_is_rejected(tmp_path):
    git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text(".env\n")
    (tmp_path / ".env").write_text("NEXUS_NEBIUS_API_KEY=fake-test-key\n")
    errors = []
    VALIDATE(tmp_path, errors)
    assert errors == []
    git(tmp_path, "add", "--force", ".env")
    VALIDATE(tmp_path, errors)
    assert errors == ["Secret file must not be tracked by Git: .env"]
    (tmp_path / ".env").unlink()
    errors = []
    VALIDATE(tmp_path, errors)
    assert errors == ["Secret file must not be tracked by Git: .env"]


def test_unignored_secret_is_rejected(tmp_path):
    git(tmp_path, "init")
    (tmp_path / "credentials.json").write_text("{}")
    errors = []
    VALIDATE(tmp_path, errors)
    assert errors == ["Local secret file is not excluded from Git: credentials.json"]


def test_source_archive_without_credentials_does_not_require_a_git_checkout(tmp_path):
    errors = []
    VALIDATE(tmp_path, errors)
    assert errors == []
