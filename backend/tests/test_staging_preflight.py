"""
Regression and unit test suite for Session 98 Staging Readiness Preflight Harness.

Covers all 12 required scenarios from Session 98:
1. Missing required configuration.
2. Missing or insecure production secrets.
3. Development-only SQLite configuration in production.
4. Valid production configuration.
5. Missing Docker Compose executable.
6. Invalid Compose configuration.
7. Missing external staging endpoint or TLS evidence.
8. Backup and restore not actually verified.
9. Secret redaction in output.
10. Correct aggregation of PASS, FAIL, BLOCKED, WARNING, and NOT APPLICABLE states.
11. A mandatory failed check prevents a ready-for-review verdict.
12. A blocked external check cannot be misreported as verified.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.ops.staging_preflight import (
    CheckStatus,
    OverallVerdict,
    PreflightCheck,
    PreflightReport,
    StagingPreflightRunner,
    format_report_console,
    redact_sensitive_text,
)


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Creates a synthetic repository root populated with standard configuration files."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "docker-compose.yml").write_text(
        """services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:?ERROR: POSTGRES_PASSWORD must be explicitly provided in environment or .env file}"
    ports:
      - "127.0.0.1:5432:5432"
  backend:
    environment:
      DATABASE_URL: "${DATABASE_URL:-postgresql+psycopg://quant_user:${POSTGRES_PASSWORD:?ERROR: POSTGRES_PASSWORD must be explicitly provided in environment or .env file}@postgres:5432/quant_portfolio_db}"
    ports:
      - "127.0.0.1:8000:8000"
  frontend:
    ports:
      - "80:80"
""",
        encoding="utf-8",
    )
    (root / ".env.example").write_text("APP_ENV=development\nPOSTGRES_PASSWORD=\n", encoding="utf-8")
    (root / ".gitignore").write_text(".env\n__pycache__/\n", encoding="utf-8")

    backend_dir = root / "backend"
    backend_dir.mkdir()
    (backend_dir / ".env.example").write_text("APP_ENV=development\n", encoding="utf-8")
    (backend_dir / "entrypoint.sh").write_text("#!/bin/sh\nalembic upgrade head\n", encoding="utf-8")

    frontend_dir = root / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "nginx.conf").write_text("server { listen 80; }\n", encoding="utf-8")

    docs_dir = root / "docs"
    docs_dir.mkdir()
    (docs_dir / "OPERATIONS_RUNBOOK.md").write_text(
        "# Runbook\nUpstream Reverse Proxy (TLS)\npg_dump -U quant_user quant_portfolio_db\npsql -U quant_user -d quant_portfolio_db\n",
        encoding="utf-8",
    )

    github_workflows = root / ".github" / "workflows"
    github_workflows.mkdir(parents=True)
    (github_workflows / "ci.yml").write_text("migration_head: e5f6a7b8c9d0\n", encoding="utf-8")

    return root


# -----------------------------------------------------------------------------
# Scenario 1: Missing required configuration
# -----------------------------------------------------------------------------
def test_missing_required_configuration_files(repo_root: Path):
    # Remove docker-compose.yml
    (repo_root / "docker-compose.yml").unlink()

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_a1 = next(c for c in report.checks if c.id == "A1_CONFIG_FILES_EXIST")
    assert chk_a1.status == CheckStatus.FAIL
    assert chk_a1.is_mandatory is True
    assert "docker-compose.yml" in chk_a1.evidence
    assert report.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Scenario 2: Missing or insecure production secrets
# -----------------------------------------------------------------------------
def test_missing_or_insecure_production_secrets(repo_root: Path):
    with patch.dict(os.environ, {"APP_ENV": "production", "JWT_SECRET_KEY": "secret", "DATABASE_URL": ""}):
        from app.auth.security import validate_jwt_configuration

        with pytest.raises(RuntimeError):
            validate_jwt_configuration()

        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_b1 = next(c for c in report.checks if c.id == "B1_PROD_SECRETS_FAIL_CLOSED")
        assert chk_b1.status == CheckStatus.PASS  # Confirmed that fail-closed logic works

        chk_b3 = next(c for c in report.checks if c.id == "B3_JWT_SECRET_STRENGTH_POLICY")
        assert chk_b3.status == CheckStatus.PASS  # Verified policy rejects "secret"


# -----------------------------------------------------------------------------
# Scenario 3: Development-only SQLite configuration in production
# -----------------------------------------------------------------------------
def test_development_sqlite_in_production_rejected(repo_root: Path):
    with patch.dict(os.environ, {"APP_ENV": "production", "DATABASE_URL": "sqlite:///test.db"}):
        from app.db.session import validate_database_configuration

        with pytest.raises(RuntimeError, match="PostgreSQL is mandatory in production; SQLite cannot be used"):
            validate_database_configuration()

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()
    chk_c1 = next(c for c in report.checks if c.id == "C1_PROD_SQLITE_PROHIBITED")
    assert chk_c1.status == CheckStatus.PASS


# -----------------------------------------------------------------------------
# Scenario 4: Valid production configuration
# -----------------------------------------------------------------------------
def test_valid_production_configuration_accepted(repo_root: Path):
    valid_jwt = "8f7c9e1d2b3a4c5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
    valid_db_url = "postgresql+psycopg://quant_user:SecureStagingPass123!@localhost:5432/quant_portfolio_db"

    with patch.dict(os.environ, {"APP_ENV": "production", "JWT_SECRET_KEY": valid_jwt, "DATABASE_URL": valid_db_url}):
        from app.auth.security import validate_production_configuration

        validate_production_configuration()  # Should not raise

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()
    chk_b1 = next(c for c in report.checks if c.id == "B1_PROD_SECRETS_FAIL_CLOSED")
    assert chk_b1.status == CheckStatus.PASS


# -----------------------------------------------------------------------------
# Scenario 5: Missing Docker Compose executable
# -----------------------------------------------------------------------------
def test_missing_docker_compose_executable_reported_as_blocked(repo_root: Path):
    with patch("shutil.which", return_value=None):
        runner = StagingPreflightRunner(repo_root=repo_root)
        report = runner.run_all()

        chk_a3 = next(c for c in report.checks if c.id == "A3_DOCKER_CLI_AVAILABLE")
        assert chk_a3.status == CheckStatus.BLOCKED
        assert chk_a3.is_mandatory is True
        assert "not found on system PATH" in chk_a3.evidence


# -----------------------------------------------------------------------------
# Scenario 6: Invalid Compose configuration
# -----------------------------------------------------------------------------
def test_invalid_compose_configuration_fails(repo_root: Path):
    # Corrupt docker-compose.yml with invalid YAML syntax
    (repo_root / "docker-compose.yml").write_text("services: { unclosed_bracket", encoding="utf-8")

    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    chk_a4 = next(c for c in report.checks if c.id == "A4_COMPOSE_SYNTAX_VALID")
    assert chk_a4.status == CheckStatus.FAIL
    assert report.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Scenario 7: Missing external staging endpoint or TLS evidence
# -----------------------------------------------------------------------------
def test_missing_external_staging_endpoint_reported_as_blocked(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root, staging_url=None)
    report = runner.run_all()

    chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
    assert chk_d3.status == CheckStatus.BLOCKED
    assert chk_d3.is_mandatory is True
    assert "not been provisioned" in chk_d3.evidence


def test_non_https_staging_url_fails(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root, staging_url="http://insecure.staging.local")
    report = runner.run_all()

    chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
    assert chk_d3.status == CheckStatus.FAIL
    assert "does not use HTTPS scheme" in chk_d3.evidence


# -----------------------------------------------------------------------------
# Scenario 8: Backup and restore not actually verified
# -----------------------------------------------------------------------------
def test_backup_and_restore_not_verified_reported_as_blocked(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root, live_db_verified=False)
    report = runner.run_all()

    chk_c4 = next(c for c in report.checks if c.id == "C4_LIVE_BACKUP_RESTORE_VERIFIED")
    assert chk_c4.status == CheckStatus.BLOCKED
    assert chk_c4.is_mandatory is True
    assert "cannot be verified in preflight" in chk_c4.evidence


# -----------------------------------------------------------------------------
# Scenario 9: Secret redaction in output
# -----------------------------------------------------------------------------
def test_secret_redaction_in_output():
    secret_pass = "SuperSecretDbPassword123!"
    secret_jwt = "8f7c9e1d2b3a4c5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e"
    raw_text = (
        f"Connecting with POSTGRES_PASSWORD={secret_pass} and "
        f"JWT_SECRET_KEY={secret_jwt} to postgresql+psycopg://user:{secret_pass}@localhost:5432/db"
    )

    sanitized = redact_sensitive_text(raw_text, [secret_pass, secret_jwt])

    assert secret_pass not in sanitized
    assert secret_jwt not in sanitized
    assert "***REDACTED***" in sanitized


# -----------------------------------------------------------------------------
# Scenario 10: Correct aggregation of PASS, FAIL, BLOCKED, WARNING, NOT_APPLICABLE
# -----------------------------------------------------------------------------
def test_aggregation_of_check_statuses(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    counts = report.summary_counts
    assert "PASS" in counts
    assert "FAIL" in counts
    assert "BLOCKED" in counts
    assert "WARNING" in counts
    assert "NOT_APPLICABLE" in counts

    total_counted = sum(counts.values())
    assert total_counted == len(report.checks)
    assert counts["PASS"] >= 10
    assert counts["BLOCKED"] >= 1
    assert counts["WARNING"] >= 1


# -----------------------------------------------------------------------------
# Scenario 11: Mandatory failed check prevents ready-for-review verdict
# -----------------------------------------------------------------------------
def test_mandatory_failed_check_prevents_ready_verdict(repo_root: Path):
    # Break a mandatory check: remove .gitignore
    (repo_root / ".gitignore").unlink()

    # Even if Docker is available and live staging URL is mocked
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_url.return_value.__enter__.return_value = mock_resp

        runner = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url="https://staging.test.internal",
            live_db_verified=True,
        )
        report = runner.run_all()

        chk_b5 = next(c for c in report.checks if c.id == "B5_ENV_FILE_GITIGNORED")
        assert chk_b5.status == CheckStatus.FAIL

        # Mandatory failure MUST cause overall FAIL
        assert report.verdict == OverallVerdict.FAIL


# -----------------------------------------------------------------------------
# Scenario 12: Blocked external check cannot be misreported as verified
# -----------------------------------------------------------------------------
def test_blocked_external_check_cannot_be_misreported_as_verified(repo_root: Path):
    # Without live staging URL or live db verification
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run") as mock_subproc:
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = ""
        mock_res.stderr = ""
        mock_subproc.return_value = mock_res

        runner = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url=None,
            live_db_verified=False,
        )
        report = runner.run_all()

        # External checks must be BLOCKED
        chk_d3 = next(c for c in report.checks if c.id == "D3_LIVE_EXTERNAL_TLS_VERIFIED")
        chk_c4 = next(c for c in report.checks if c.id == "C4_LIVE_BACKUP_RESTORE_VERIFIED")
        assert chk_d3.status == CheckStatus.BLOCKED
        assert chk_c4.status == CheckStatus.BLOCKED

        # Overall verdict MUST be BLOCKED, never READY
        assert report.verdict == OverallVerdict.BLOCKED
        assert report.verdict != OverallVerdict.READY


# -----------------------------------------------------------------------------
# Scenario 13: Ready verdict when all prerequisites and probes are verified
# -----------------------------------------------------------------------------
def test_ready_verdict_when_all_prerequisites_and_probes_verified(repo_root: Path):
    with patch("shutil.which", return_value="/usr/bin/docker"), \
         patch("subprocess.run") as mock_subproc, \
         patch("urllib.request.urlopen") as mock_url:
        # Mock git and compose
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = ""
        mock_res.stderr = ""
        mock_subproc.return_value = mock_res

        # Mock HTTPS probe
        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_url.return_value.__enter__.return_value = mock_resp

        runner = StagingPreflightRunner(
            repo_root=repo_root,
            staging_url="https://staging.quantengine.internal",
            live_db_verified=True,
        )
        report = runner.run_all()

        # All mandatory checks should PASS
        mandatory_statuses = [c.status for c in report.checks if c.is_mandatory]
        assert all(s == CheckStatus.PASS for s in mandatory_statuses)
        assert report.verdict == OverallVerdict.READY


# -----------------------------------------------------------------------------
# Scenario 14: Report formatting and JSON conversion
# -----------------------------------------------------------------------------
def test_report_formatting_and_json(repo_root: Path):
    runner = StagingPreflightRunner(repo_root=repo_root)
    report = runner.run_all()

    formatted_text = format_report_console(report)
    assert "STAGING READINESS PREFLIGHT HARNESS" in formatted_text
    assert "PREFLIGHT SUMMARY COUNTS:" in formatted_text
    assert report.verdict.value in formatted_text

    report_dict = report.to_dict()
    assert report_dict["verdict"] == report.verdict.value
    assert len(report_dict["checks"]) == len(report.checks)
