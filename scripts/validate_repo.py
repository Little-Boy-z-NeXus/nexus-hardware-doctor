"""Dependency-free validation for the NeXus repository foundation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRECTORIES = (
    "firmware",
    "backend",
    "frontend",
    "docs",
    "nexus-contracts/v1/schemas",
    "nexus-contracts/v1/fixtures",
    "nexus-contracts/migrations",
    "nexus-k6-tests",
    ".github/ISSUE_TEMPLATE",
    ".github/workflows",
)

REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "CONTRIBUTING.md",
    ".env.example",
    ".gitignore",
    ".github/workflows/ci.yml",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    "firmware/platformio.ini",
    "firmware/src/main.cpp",
    "firmware/README.md",
    "backend/pyproject.toml",
    "backend/src/nexus_backend/app.py",
    "backend/README.md",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/.env.example",
    "frontend/eslint.config.js",
    "frontend/src/App.tsx",
    "frontend/src/components/AppShell.tsx",
    "frontend/src/pages/DashboardPage.tsx",
    "frontend/src/pages/HardwareGraphPage.tsx",
    "frontend/src/pages/AIDoctorPage.tsx",
    "frontend/src/vite-env.d.ts",
    "frontend/src/App.test.tsx",
    "frontend/src/config/env.test.ts",
    "frontend/src/test/setup.ts",
    "frontend/vitest.config.ts",
    "frontend/README.md",
    "firmware/include/nexus_contract_v1.h",
    "backend/src/nexus_backend/contracts.py",
    "backend/tests/test_contracts.py",
    "frontend/src/contracts/v1.ts",
    "nexus-contracts/v1/README.md",
    "nexus-contracts/README.md",
    "nexus-contracts/migrations/README.md",
    "nexus-contracts/v1/schemas/hardware-model.schema.json",
    "nexus-contracts/v1/schemas/telemetry.schema.json",
    "nexus-contracts/v1/schemas/tool.schema.json",
    "nexus-contracts/v1/schemas/event.schema.json",
    "nexus-contracts/v1/fixtures/hardware-model.example.json",
    "nexus-contracts/v1/fixtures/telemetry.example.json",
    "nexus-contracts/v1/fixtures/tool.example.json",
    "nexus-contracts/v1/fixtures/event.example.json",
    "nexus-contracts/migrations/0001-freeze-v1.md",
    "scripts/validate_contracts.py",
    "scripts/README.md",
    "nexus-k6-tests/README.md",
    "nexus-k6-tests/smoke.js",
    "nexus-k6-tests/load.js",
    "docs/README.md",
    "docs/architecture.md",
    "docs/ownership.md",
    "docs/mvp-scope.md",
)

README_FILES = (
    "README.md",
    "firmware/README.md",
    "backend/README.md",
    "frontend/README.md",
    "nexus-contracts/README.md",
    "nexus-contracts/v1/README.md",
    "nexus-contracts/migrations/README.md",
    "docs/README.md",
    "scripts/README.md",
    "nexus-k6-tests/README.md",
)

MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_readme_links(errors: list[str]) -> None:
    for relative in README_FILES:
        readme_path = ROOT / relative
        if not readme_path.is_file():
            continue

        for raw_target in MARKDOWN_LINK.findall(
            readme_path.read_text(encoding="utf-8")
        ):
            target = raw_target.strip().strip("<>")
            if not target or target.startswith(("#", "mailto:")) or "://" in target:
                continue

            file_target = target.split("#", maxsplit=1)[0]
            resolved = (readme_path.parent / file_target).resolve()
            require(
                resolved.is_relative_to(ROOT) and resolved.exists(),
                f"Broken README link in {relative}: {target}",
                errors,
            )


def main() -> int:
    errors: list[str] = []

    require(
        bool(re.fullmatch(r"nexus-[a-z0-9]+(?:-[a-z0-9]+)*", ROOT.name)),
        "Project folder must match nexus-<lowercase-kebab-name>.",
        errors,
    )

    for relative in REQUIRED_DIRECTORIES:
        require((ROOT / relative).is_dir(), f"Missing directory: {relative}", errors)

    for relative in REQUIRED_FILES:
        require((ROOT / relative).is_file(), f"Missing file: {relative}", errors)

    if (ROOT / "LICENSE").is_file():
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        require(
            license_text.startswith("MIT License"), "Root LICENSE must be MIT.", errors
        )

    if (ROOT / "README.md").is_file():
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        require(
            "nexus-<name>" in readme,
            "README must document the nexus- naming rule.",
            errors,
        )
        require(
            "docs.google.com/spreadsheets" in readme,
            "README must link the shared backlog.",
            errors,
        )

    if (ROOT / "backend/pyproject.toml").is_file():
        backend_config = (ROOT / "backend/pyproject.toml").read_text(encoding="utf-8")
        require(
            'name = "nexus-backend"' in backend_config,
            "Backend package must use the nexus- prefix.",
            errors,
        )

    if (ROOT / "frontend/package.json").is_file():
        frontend_config = (ROOT / "frontend/package.json").read_text(encoding="utf-8")
        require(
            '"name": "nexus-frontend"' in frontend_config,
            "Frontend package must use the nexus- prefix.",
            errors,
        )

    forbidden = [ROOT / ".env", ROOT / "secrets.json", ROOT / "credentials.json"]
    for path in forbidden:
        require(
            not path.exists(),
            f"Forbidden local secret file present: {path.name}",
            errors,
        )

    validate_readme_links(errors)

    if errors:
        print("NeXus repository validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("NeXus repository foundation: PASS")
    print(f"Root: {ROOT.name}")
    print(f"Required directories: {len(REQUIRED_DIRECTORIES)}")
    print(f"Required files: {len(REQUIRED_FILES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
