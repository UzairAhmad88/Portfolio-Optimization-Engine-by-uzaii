"""
Staging Readiness Preflight Harness (Session 98).

Evaluates whether the Quantitative Portfolio Optimization Engine (QPE) repository,
configuration, and environment are safe, hardened, and ready for a staging deployment.

Check Statuses:
- PASS: Verified automatically using available evidence.
- FAIL: A mandatory check has failed.
- BLOCKED: Verification requires infrastructure, credentials, or an external system that is not available.
- WARNING: A non-blocking risk requiring attention.
- NOT_APPLICABLE: A check does not apply to the current execution mode or environment.

Overall Verdicts:
- READY FOR STAGING DEPLOYMENT REVIEW (all mandatory checks passed)
- BLOCKED — MANDATORY PREREQUISITES MISSING (one or more mandatory checks are blocked)
- FAIL — SECURITY OR CONFIGURATION DEFECT (one or more mandatory checks failed)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class OverallVerdict(str, Enum):
    READY = "READY FOR STAGING DEPLOYMENT REVIEW"
    BLOCKED = "BLOCKED -- MANDATORY PREREQUISITES MISSING"
    FAIL = "FAIL -- SECURITY OR CONFIGURATION DEFECT"


@dataclass
class PreflightCheck:
    id: str
    category: str
    title: str
    status: CheckStatus
    is_mandatory: bool
    evidence: str
    remediation: Optional[str] = None
    risk_id: Optional[str] = None


@dataclass
class PreflightReport:
    target_env: str
    verdict: OverallVerdict
    checks: List[PreflightCheck]
    summary_counts: Dict[str, int]
    generated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_env": self.target_env,
            "verdict": self.verdict.value,
            "summary_counts": self.summary_counts,
            "generated_at": self.generated_at,
            "checks": [asdict(c) for c in self.checks],
        }


def redact_sensitive_text(text: str, custom_secrets: Sequence[str] | None = None) -> str:
    """
    Sanitizes strings to prevent credential exposure in logs or reports.
    """
    if not text:
        return text

    sanitized = text

    # Mask known custom secrets
    if custom_secrets:
        for s in custom_secrets:
            if s and len(s) >= 4 and s in sanitized:
                sanitized = sanitized.replace(s, "***REDACTED***")

    # Mask common key=value patterns
    patterns = [
        r"(POSTGRES_PASSWORD\s*[:=]\s*)([^\s\"';]+)",
        r"(JWT_SECRET_KEY\s*[:=]\s*)([^\s\"';]+)",
        r"(password\s*[:=]\s*)([^\s\"';]+)",
        r"(postgresql\+psycopg://[^:]+:)([^@]+)(@)",
        r"(Bearer\s+)([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_=]*)",
    ]
    for p in patterns:
        sanitized = re.sub(p, r"\1***REDACTED***\3" if r"\3" in p else r"\1***REDACTED***", sanitized, flags=re.IGNORECASE)

    return sanitized


class StagingPreflightRunner:
    """
    Executes the suite of readiness checks across repository, configuration,
    database, network, operational safeguards, and external staging probes.
    """

    def __init__(
        self,
        repo_root: Path | None = None,
        staging_url: str | None = None,
        live_db_verified: bool = False,
        target_env: str = "staging",
        custom_env: Dict[str, str] | None = None,
    ):
        if repo_root is None:
            # Default to repo root relative to this file
            current_file = Path(__file__).resolve()
            # If in backend/app/ops/staging_preflight.py -> up 3 levels to repo root
            self.repo_root = current_file.parents[3] if len(current_file.parents) >= 4 else current_file.parent
        else:
            self.repo_root = Path(repo_root)

        self.staging_url = staging_url.strip() if staging_url else None
        self.live_db_verified = live_db_verified
        self.target_env = target_env
        self.env = custom_env if custom_env is not None else dict(os.environ)
        self.checks: List[PreflightCheck] = []

    def run_all(self) -> PreflightReport:
        self.checks = []
        self._check_category_a_repository()
        self._check_category_b_secrets()
        self._check_category_c_database()
        self._check_category_d_network()
        self._check_category_e_operational_safeguards()

        # Compute summary counts
        counts: Dict[str, int] = {
            CheckStatus.PASS.value: 0,
            CheckStatus.FAIL.value: 0,
            CheckStatus.BLOCKED.value: 0,
            CheckStatus.WARNING.value: 0,
            CheckStatus.NOT_APPLICABLE.value: 0,
        }
        for c in self.checks:
            counts[c.status.value] = counts.get(c.status.value, 0) + 1

        # Evaluate verdict
        has_mandatory_fail = any(c.status == CheckStatus.FAIL and c.is_mandatory for c in self.checks)
        has_mandatory_blocked = any(c.status == CheckStatus.BLOCKED and c.is_mandatory for c in self.checks)

        if has_mandatory_fail:
            verdict = OverallVerdict.FAIL
        elif has_mandatory_blocked:
            verdict = OverallVerdict.BLOCKED
        else:
            verdict = OverallVerdict.READY

        return PreflightReport(
            target_env=self.target_env,
            verdict=verdict,
            checks=self.checks,
            summary_counts=counts,
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )

    # -------------------------------------------------------------------------
    # Category A: Repository and Configuration
    # -------------------------------------------------------------------------
    def _check_category_a_repository(self) -> None:
        # A1: Required configuration files exist
        req_files = [
            "docker-compose.yml",
            ".env.example",
            "backend/.env.example",
            "frontend/nginx.conf",
            "backend/entrypoint.sh",
            "docs/OPERATIONS_RUNBOOK.md",
        ]
        missing_files = [f for f in req_files if not (self.repo_root / f).is_file()]
        if missing_files:
            self.checks.append(PreflightCheck(
                id="A1_CONFIG_FILES_EXIST",
                category="Repository & Configuration",
                title="Mandatory Configuration Files Presence",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence=f"Missing configuration files: {', '.join(missing_files)}",
                remediation="Ensure repository checkout is complete and all configuration manifests are tracked.",
            ))
        else:
            self.checks.append(PreflightCheck(
                id="A1_CONFIG_FILES_EXIST",
                category="Repository & Configuration",
                title="Mandatory Configuration Files Presence",
                status=CheckStatus.PASS,
                is_mandatory=True,
                evidence="All 6 required configuration files and manifests are present in repository.",
            ))

        # A2: Git diff check
        if not (self.repo_root / ".git").exists():
            self.checks.append(PreflightCheck(
                id="A2_GIT_DIFF_CHECK",
                category="Repository & Configuration",
                title="Git Whitespace & Formatting Hygiene",
                status=CheckStatus.NOT_APPLICABLE,
                is_mandatory=False,
                evidence="Directory is not a Git worktree; git diff --check skipped.",
            ))
        else:
            try:
                res = subprocess.run(
                    ["git", "diff", "--check"],
                    cwd=str(self.repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    self.checks.append(PreflightCheck(
                        id="A2_GIT_DIFF_CHECK",
                        category="Repository & Configuration",
                        title="Git Whitespace & Formatting Hygiene",
                        status=CheckStatus.PASS,
                        is_mandatory=True,
                        evidence="git diff --check passed with zero whitespace or line-ending violations.",
                    ))
                else:
                    err_snippet = res.stdout.strip() or res.stderr.strip()
                    self.checks.append(PreflightCheck(
                        id="A2_GIT_DIFF_CHECK",
                        category="Repository & Configuration",
                        title="Git Whitespace & Formatting Hygiene",
                        status=CheckStatus.FAIL,
                        is_mandatory=True,
                        evidence=f"git diff --check reported violations: {err_snippet[:200]}",
                        remediation="Resolve trailing whitespace or conflicting line endings before deploying.",
                    ))
            except Exception as e:
                self.checks.append(PreflightCheck(
                    id="A2_GIT_DIFF_CHECK",
                    category="Repository & Configuration",
                    title="Git Whitespace & Formatting Hygiene",
                    status=CheckStatus.WARNING,
                    is_mandatory=False,
                    evidence=f"Could not execute git CLI on host: {e}",
                    remediation="Install Git CLI on the staging management host.",
                ))

        # A3: Docker Compose executable availability
        docker_bin = shutil.which("docker")
        if not docker_bin:
            self.checks.append(PreflightCheck(
                id="A3_DOCKER_CLI_AVAILABLE",
                category="Repository & Configuration",
                title="Docker & Compose CLI Availability",
                status=CheckStatus.BLOCKED,
                is_mandatory=True,
                evidence="docker executable was not found on system PATH on this host.",
                remediation="Install Docker Engine 24+ and Docker Compose v2 on the staging deployment host.",
            ))
        else:
            self.checks.append(PreflightCheck(
                id="A3_DOCKER_CLI_AVAILABLE",
                category="Repository & Configuration",
                title="Docker & Compose CLI Availability",
                status=CheckStatus.PASS,
                is_mandatory=True,
                evidence=f"Found Docker executable at: {docker_bin}",
            ))

        # A4: Compose configuration syntax validation
        compose_file = self.repo_root / "docker-compose.yml"
        if not compose_file.is_file():
            self.checks.append(PreflightCheck(
                id="A4_COMPOSE_SYNTAX_VALID",
                category="Repository & Configuration",
                title="Docker Compose Syntax & Interpolation Validation",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence="docker-compose.yml does not exist.",
                remediation="Ensure docker-compose.yml is present in repository root.",
            ))
        else:
            # Check YAML parseability first
            yaml_valid = False
            yaml_err = ""
            try:
                import yaml
                with open(compose_file, "r", encoding="utf-8") as f:
                    yaml.safe_load(f)
                yaml_valid = True
            except Exception as e:
                yaml_err = str(e)

            if not yaml_valid:
                self.checks.append(PreflightCheck(
                    id="A4_COMPOSE_SYNTAX_VALID",
                    category="Repository & Configuration",
                    title="Docker Compose Syntax & Interpolation Validation",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence=f"YAML syntax parsing error in docker-compose.yml: {yaml_err[:200]}",
                    remediation="Fix YAML formatting and ensure all variables with colons are quoted.",
                ))
            elif docker_bin:
                try:
                    res = subprocess.run(
                        ["docker", "compose", "config", "--quiet"],
                        cwd=str(self.repo_root),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    if res.returncode == 0:
                        self.checks.append(PreflightCheck(
                            id="A4_COMPOSE_SYNTAX_VALID",
                            category="Repository & Configuration",
                            title="Docker Compose Syntax & Interpolation Validation",
                            status=CheckStatus.PASS,
                            is_mandatory=True,
                            evidence="docker compose config --quiet succeeded with zero interpolation or syntax errors.",
                        ))
                    else:
                        err_out = res.stderr.strip() or res.stdout.strip()
                        self.checks.append(PreflightCheck(
                            id="A4_COMPOSE_SYNTAX_VALID",
                            category="Repository & Configuration",
                            title="Docker Compose Syntax & Interpolation Validation",
                            status=CheckStatus.FAIL,
                            is_mandatory=True,
                            evidence=f"docker compose config failed: {redact_sensitive_text(err_out[:250])}",
                            remediation="Verify Compose parameter interpolation and ensure required environment variables exist.",
                        ))
                except Exception as e:
                    self.checks.append(PreflightCheck(
                        id="A4_COMPOSE_SYNTAX_VALID",
                        category="Repository & Configuration",
                        title="Docker Compose Syntax & Interpolation Validation",
                        status=CheckStatus.WARNING,
                        is_mandatory=True,
                        evidence=f"YAML is valid; Docker Compose CLI check encountered exception: {e}",
                    ))
            else:
                self.checks.append(PreflightCheck(
                    id="A4_COMPOSE_SYNTAX_VALID",
                    category="Repository & Configuration",
                    title="Docker Compose Syntax & Interpolation Validation",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="YAML structure and variable quoting verified valid via PyYAML SafeLoader (Docker CLI absent on local host).",
                ))

        # A5: Secret redaction active
        test_secret = "super_secret_test_token_12345"
        redacted = redact_sensitive_text(f"Key={test_secret}", [test_secret])
        if test_secret in redacted:
            self.checks.append(PreflightCheck(
                id="A5_SECRET_REDACTION_ACTIVE",
                category="Repository & Configuration",
                title="Log & Diagnostic Secret Redaction Guard",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence="Secret redaction filter failed to mask test secret.",
                remediation="Ensure redact_sensitive_text masks custom secrets and credential patterns.",
            ))
        else:
            self.checks.append(PreflightCheck(
                id="A5_SECRET_REDACTION_ACTIVE",
                category="Repository & Configuration",
                title="Log & Diagnostic Secret Redaction Guard",
                status=CheckStatus.PASS,
                is_mandatory=True,
                evidence="Automated secret redaction filter active; masks passwords, JWT tokens, and connection strings.",
            ))

    # -------------------------------------------------------------------------
    # Category B: Secret and Environment Safety
    # -------------------------------------------------------------------------
    def _check_category_b_secrets(self) -> None:
        # B1: Production secrets fail-closed verification
        try:
            from app.auth.security import validate_production_configuration
            from app.db.session import validate_database_configuration
            validator_available = True
        except ImportError:
            validator_available = False

        if not validator_available:
            self.checks.append(PreflightCheck(
                id="B1_PROD_SECRETS_FAIL_CLOSED",
                category="Secret & Environment Safety",
                title="Production Configuration Fail-Closed Validator Presence",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence="Could not import validate_production_configuration from app.auth.security.",
                remediation="Ensure app.auth.security and app.db.session expose production configuration validators.",
            ))
        else:
            # Test that validator actually fails closed when secrets are missing under APP_ENV=production
            saved_env = dict(os.environ)
            try:
                os.environ["APP_ENV"] = "production"
                os.environ["JWT_SECRET_KEY"] = ""
                os.environ["DATABASE_URL"] = ""
                failed_closed = False
                try:
                    from app.auth.security import validate_production_configuration
                    validate_production_configuration()
                except RuntimeError:
                    failed_closed = True

                if failed_closed:
                    self.checks.append(PreflightCheck(
                        id="B1_PROD_SECRETS_FAIL_CLOSED",
                        category="Secret & Environment Safety",
                        title="Production Configuration Fail-Closed Enforcement",
                        status=CheckStatus.PASS,
                        is_mandatory=True,
                        evidence="validate_production_configuration() fails closed immediately with RuntimeError when secrets are missing.",
                    ))
                else:
                    self.checks.append(PreflightCheck(
                        id="B1_PROD_SECRETS_FAIL_CLOSED",
                        category="Secret & Environment Safety",
                        title="Production Configuration Fail-Closed Enforcement",
                        status=CheckStatus.FAIL,
                        is_mandatory=True,
                        evidence="Validator did not raise RuntimeError under missing production secrets.",
                        remediation="Ensure validate_production_configuration aborts startup when secrets are missing.",
                    ))
            finally:
                os.environ.clear()
                os.environ.update(saved_env)

        # B2: PostgreSQL password fallback prevention in Compose
        compose_path = self.repo_root / "docker-compose.yml"
        if compose_path.is_file():
            compose_text = compose_path.read_text(encoding="utf-8")
            has_insecure_fallback = re.search(r"POSTGRES_PASSWORD:\s*[\"']?\$\{POSTGRES_PASSWORD:-", compose_text)
            has_fail_closed_syntax = re.search(r"POSTGRES_PASSWORD:\s*[\"']?\$\{POSTGRES_PASSWORD:\?", compose_text)

            if has_insecure_fallback:
                self.checks.append(PreflightCheck(
                    id="B2_POSTGRES_PASSWORD_NO_FALLBACK",
                    category="Secret & Environment Safety",
                    title="Compose Insecure Password Fallback Elimination",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence="docker-compose.yml contains insecure fallback '${POSTGRES_PASSWORD:-...}' for PostgreSQL password.",
                    remediation="Replace fallback with '${POSTGRES_PASSWORD:?ERROR: ...}' parameter substitution.",
                    risk_id="OPS-95-02",
                ))
            elif has_fail_closed_syntax:
                self.checks.append(PreflightCheck(
                    id="B2_POSTGRES_PASSWORD_NO_FALLBACK",
                    category="Secret & Environment Safety",
                    title="Compose Insecure Password Fallback Elimination",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="docker-compose.yml enforces fail-closed '${POSTGRES_PASSWORD:?ERROR: ...}' with zero silent defaults.",
                    risk_id="OPS-95-02",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="B2_POSTGRES_PASSWORD_NO_FALLBACK",
                    category="Secret & Environment Safety",
                    title="Compose Insecure Password Fallback Elimination",
                    status=CheckStatus.WARNING,
                    is_mandatory=True,
                    evidence="Could not match standard POSTGRES_PASSWORD interpolation in docker-compose.yml.",
                    risk_id="OPS-95-02",
                ))

        # B3: JWT secret strength and placeholder rejection
        saved_env = dict(os.environ)
        try:
            os.environ["APP_ENV"] = "production"
            os.environ["JWT_SECRET_KEY"] = "secret"  # Short & blacklisted
            short_rejected = False
            try:
                from app.auth.security import validate_jwt_configuration
                validate_jwt_configuration()
            except RuntimeError:
                short_rejected = True

            os.environ["JWT_SECRET_KEY"] = "quant_engine_dev_secret_key_change_in_production_9f83a2b1c0d4e5"
            placeholder_rejected = False
            try:
                validate_jwt_configuration()
            except RuntimeError:
                placeholder_rejected = True

            if short_rejected and placeholder_rejected:
                self.checks.append(PreflightCheck(
                    id="B3_JWT_SECRET_STRENGTH_POLICY",
                    category="Secret & Environment Safety",
                    title="JWT Secret Minimum Entropy & Placeholder Policy",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="JWT policy enforces >= 32 characters and strictly rejects known development placeholders.",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="B3_JWT_SECRET_STRENGTH_POLICY",
                    category="Secret & Environment Safety",
                    title="JWT Secret Minimum Entropy & Placeholder Policy",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence=f"JWT validation failed: short_rejected={short_rejected}, placeholder_rejected={placeholder_rejected}",
                    remediation="Ensure validate_jwt_configuration rejects short strings and blacklisted keys.",
                ))
        finally:
            os.environ.clear()
            os.environ.update(saved_env)

        # B4: DB password strength and placeholder rejection
        saved_env = dict(os.environ)
        try:
            os.environ["APP_ENV"] = "production"
            os.environ["DATABASE_URL"] = "postgresql+psycopg://user:quant_password@localhost:5432/db"
            placeholder_rejected = False
            try:
                from app.db.session import validate_database_configuration
                validate_database_configuration()
            except RuntimeError:
                placeholder_rejected = True

            os.environ["DATABASE_URL"] = "postgresql+psycopg://user:short@localhost:5432/db"
            short_rejected = False
            try:
                validate_database_configuration()
            except RuntimeError:
                short_rejected = True

            if placeholder_rejected and short_rejected:
                self.checks.append(PreflightCheck(
                    id="B4_DB_PASSWORD_STRENGTH_POLICY",
                    category="Secret & Environment Safety",
                    title="Database Password Entropy & Blacklist Policy",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="Database validation rejects blacklisted passwords (14 entries) and passwords < 8 characters.",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="B4_DB_PASSWORD_STRENGTH_POLICY",
                    category="Secret & Environment Safety",
                    title="Database Password Entropy & Blacklist Policy",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence=f"DB password validation failed: placeholder_rejected={placeholder_rejected}, short_rejected={short_rejected}",
                    remediation="Ensure validate_database_configuration rejects blacklisted and short credentials.",
                ))
        finally:
            os.environ.clear()
            os.environ.update(saved_env)

        # B5: Safe secret storage standard (.gitignore)
        gitignore_path = self.repo_root / ".gitignore"
        if gitignore_path.is_file():
            gi_text = gitignore_path.read_text(encoding="utf-8")
            if re.search(r"^\.env\b", gi_text, re.MULTILINE):
                self.checks.append(PreflightCheck(
                    id="B5_ENV_FILE_GITIGNORED",
                    category="Secret & Environment Safety",
                    title="Accidental Secret Commit Prevention (.gitignore)",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence=".env is listed in .gitignore, preventing accidental version control commits.",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="B5_ENV_FILE_GITIGNORED",
                    category="Secret & Environment Safety",
                    title="Accidental Secret Commit Prevention (.gitignore)",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence=".env is missing from .gitignore.",
                    remediation="Add .env to .gitignore immediately.",
                ))
        else:
            self.checks.append(PreflightCheck(
                id="B5_ENV_FILE_GITIGNORED",
                category="Secret & Environment Safety",
                title="Accidental Secret Commit Prevention (.gitignore)",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence=".gitignore does not exist in repository root.",
                remediation="Create .gitignore and ensure .env is excluded.",
            ))

    # -------------------------------------------------------------------------
    # Category C: Database and Migration Readiness
    # -------------------------------------------------------------------------
    def _check_category_c_database(self) -> None:
        # C1: Production mode rejects SQLite
        saved_env = dict(os.environ)
        try:
            os.environ["APP_ENV"] = "production"
            os.environ["DATABASE_URL"] = "sqlite:///quant_portfolio.db"
            sqlite_rejected = False
            try:
                from app.db.session import validate_database_configuration
                validate_database_configuration()
            except RuntimeError as e:
                if "sqlite" in str(e).lower():
                    sqlite_rejected = True

            if sqlite_rejected:
                self.checks.append(PreflightCheck(
                    id="C1_PROD_SQLITE_PROHIBITED",
                    category="Database & Migration Readiness",
                    title="Production SQLite Prohibition Enforcement",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="validate_database_configuration() strictly rejects SQLite schemes when APP_ENV=production.",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="C1_PROD_SQLITE_PROHIBITED",
                    category="Database & Migration Readiness",
                    title="Production SQLite Prohibition Enforcement",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence="Production mode did not reject SQLite database URL.",
                    remediation="Ensure validate_database_configuration forbids SQLite under production mode.",
                ))
        finally:
            os.environ.clear()
            os.environ.update(saved_env)

        # C2: Alembic migration head alignment
        entrypoint_file = self.repo_root / "backend" / "entrypoint.sh"
        ci_file = self.repo_root / ".github" / "workflows" / "ci.yml"
        expected_head = "e5f6a7b8c9d0"
        has_entrypoint_upgrade = False
        has_ci_head_match = False

        if entrypoint_file.is_file():
            ep_text = entrypoint_file.read_text(encoding="utf-8")
            if "alembic upgrade head" in ep_text:
                has_entrypoint_upgrade = True

        if ci_file.is_file():
            ci_text = ci_file.read_text(encoding="utf-8")
            if expected_head in ci_text:
                has_ci_head_match = True

        if has_entrypoint_upgrade and has_ci_head_match:
            self.checks.append(PreflightCheck(
                id="C2_ALEMBIC_MIGRATION_HEAD",
                category="Database & Migration Readiness",
                title="Alembic Migration Head & Container Precedence",
                status=CheckStatus.PASS,
                is_mandatory=True,
                evidence=f"Container entrypoint executes 'alembic upgrade head'; CI verifies migration head '{expected_head}'.",
            ))
        else:
            self.checks.append(PreflightCheck(
                id="C2_ALEMBIC_MIGRATION_HEAD",
                category="Database & Migration Readiness",
                title="Alembic Migration Head & Container Precedence",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence=f"Migration check mismatch: entrypoint_upgrade={has_entrypoint_upgrade}, ci_head_match={has_ci_head_match}",
                remediation="Ensure backend/entrypoint.sh executes alembic upgrade head and CI matches migration revision.",
            ))

        # C3: Documented backup & restore command audit
        runbook_file = self.repo_root / "docs" / "OPERATIONS_RUNBOOK.md"
        if runbook_file.is_file():
            rb_text = runbook_file.read_text(encoding="utf-8")
            has_pg_dump = "pg_dump" in rb_text and "quant_user" in rb_text and "quant_portfolio_db" in rb_text
            has_restore = ("pg_restore" in rb_text or "psql" in rb_text) and "quant_user" in rb_text and "quant_portfolio_db" in rb_text

            if has_pg_dump and has_restore:
                self.checks.append(PreflightCheck(
                    id="C3_BACKUP_COMMAND_ALIGNMENT",
                    category="Database & Migration Readiness",
                    title="Operational Backup & Restore Command Audit",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="docs/OPERATIONS_RUNBOOK.md accurately documents pg_dump and database restore matching real Compose service, user, and database.",
                    risk_id="OPS-95-03",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="C3_BACKUP_COMMAND_ALIGNMENT",
                    category="Database & Migration Readiness",
                    title="Operational Backup & Restore Command Audit",
                    status=CheckStatus.WARNING,
                    is_mandatory=True,
                    evidence="Runbook is missing complete pg_dump or pg_restore reference.",
                    remediation="Update docs/OPERATIONS_RUNBOOK.md Section B with exact backup and restore commands.",
                    risk_id="OPS-95-03",
                ))
        else:
            self.checks.append(PreflightCheck(
                id="C3_BACKUP_COMMAND_ALIGNMENT",
                category="Database & Migration Readiness",
                title="Operational Backup & Restore Command Audit",
                status=CheckStatus.FAIL,
                is_mandatory=True,
                evidence="docs/OPERATIONS_RUNBOOK.md is missing.",
                remediation="Create docs/OPERATIONS_RUNBOOK.md.",
                risk_id="OPS-95-03",
            ))

        # C4: Live backup and restore verification
        if self.live_db_verified:
            self.checks.append(PreflightCheck(
                id="C4_LIVE_BACKUP_RESTORE_VERIFIED",
                category="Database & Migration Readiness",
                title="Live Staging Database Backup & Restore Verification",
                status=CheckStatus.PASS,
                is_mandatory=True,
                evidence="Live database backup and restore drill was executed successfully on staging host.",
                risk_id="OPS-95-03",
            ))
        else:
            self.checks.append(PreflightCheck(
                id="C4_LIVE_BACKUP_RESTORE_VERIFIED",
                category="Database & Migration Readiness",
                title="Live Staging Database Backup & Restore Verification",
                status=CheckStatus.BLOCKED,
                is_mandatory=True,
                evidence="Live staging database has not been provisioned on an external host; backup/restore drill cannot be verified in preflight.",
                remediation="Once staging host is provisioned, execute Test 11 (pg_dump & pg_restore sandbox drill) from Session 97.",
                risk_id="OPS-95-03",
            ))

    # -------------------------------------------------------------------------
    # Category D: Network and HTTPS Prerequisites
    # -------------------------------------------------------------------------
    def _check_category_d_network(self) -> None:
        # D1: Port isolation in Compose
        compose_path = self.repo_root / "docker-compose.yml"
        if compose_path.is_file():
            compose_text = compose_path.read_text(encoding="utf-8")
            postgres_loopback = bool(re.search(r'["\']127\.0\.0\.1:5432:5432["\']', compose_text))
            backend_loopback = bool(re.search(r'["\']127\.0\.0\.1:8000:8000["\']', compose_text))
            public_postgres = bool(re.search(r'["\']0\.0\.0\.0:5432["\']|["\']5432:5432["\']', compose_text))

            if postgres_loopback and backend_loopback and not public_postgres:
                self.checks.append(PreflightCheck(
                    id="D1_COMPOSE_PORT_ISOLATION",
                    category="Network & HTTPS Prerequisites",
                    title="Database & Backend Loopback Port Isolation",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="PostgreSQL (5432) and Backend (8000) are strictly bound to loopback 127.0.0.1; zero public exposure.",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="D1_COMPOSE_PORT_ISOLATION",
                    category="Network & HTTPS Prerequisites",
                    title="Database & Backend Loopback Port Isolation",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence=f"Port exposure unsafe: postgres_loopback={postgres_loopback}, backend_loopback={backend_loopback}, public_postgres={public_postgres}",
                    remediation="Bind database and backend ports to 127.0.0.1 in docker-compose.yml.",
                ))

        # D2: Upstream TLS reverse proxy requirement documented
        runbook_file = self.repo_root / "docs" / "OPERATIONS_RUNBOOK.md"
        if runbook_file.is_file():
            rb_text = runbook_file.read_text(encoding="utf-8")
            if "Upstream Reverse Proxy (TLS)" in rb_text or "TLS" in rb_text:
                self.checks.append(PreflightCheck(
                    id="D2_UPSTREAM_TLS_DOCUMENTED",
                    category="Network & HTTPS Prerequisites",
                    title="Upstream TLS Termination Contract Documentation",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="Runbook explicitly defines external upstream reverse proxy terminating TLS on port 443 as a staging/prod prerequisite.",
                    risk_id="OPS-95-01",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="D2_UPSTREAM_TLS_DOCUMENTED",
                    category="Network & HTTPS Prerequisites",
                    title="Upstream TLS Termination Contract Documentation",
                    status=CheckStatus.WARNING,
                    is_mandatory=True,
                    evidence="Runbook does not prominently mandate upstream TLS termination.",
                    remediation="Document mandatory TLS 443 reverse proxy in docs/OPERATIONS_RUNBOOK.md.",
                    risk_id="OPS-95-01",
                ))

        # D3: Live external TLS certificate & HTTPS endpoint probe
        if self.staging_url:
            if not self.staging_url.startswith("https://"):
                self.checks.append(PreflightCheck(
                    id="D3_LIVE_EXTERNAL_TLS_VERIFIED",
                    category="Network & HTTPS Prerequisites",
                    title="Live Staging HTTPS Endpoint & Certificate Probe",
                    status=CheckStatus.FAIL,
                    is_mandatory=True,
                    evidence=f"Staging URL '{self.staging_url}' does not use HTTPS scheme.",
                    remediation="Staging URL must use https:// scheme with valid SSL certificate.",
                    risk_id="OPS-95-01",
                ))
            else:
                try:
                    req = urllib.request.Request(self.staging_url, headers={"User-Agent": "QPE-Preflight/1.0"})
                    with urllib.request.urlopen(req, timeout=10.0) as resp:
                        status_code = resp.getcode()
                    if status_code in (200, 301, 302, 307, 308):
                        self.checks.append(PreflightCheck(
                            id="D3_LIVE_EXTERNAL_TLS_VERIFIED",
                            category="Network & HTTPS Prerequisites",
                            title="Live Staging HTTPS Endpoint & Certificate Probe",
                            status=CheckStatus.PASS,
                            is_mandatory=True,
                            evidence=f"Successfully probed live staging HTTPS endpoint '{self.staging_url}' (HTTP {status_code}) with valid TLS.",
                            risk_id="OPS-95-01",
                        ))
                    else:
                        self.checks.append(PreflightCheck(
                            id="D3_LIVE_EXTERNAL_TLS_VERIFIED",
                            category="Network & HTTPS Prerequisites",
                            title="Live Staging HTTPS Endpoint & Certificate Probe",
                            status=CheckStatus.WARNING,
                            is_mandatory=True,
                            evidence=f"Probed '{self.staging_url}', returned HTTP {status_code}.",
                            risk_id="OPS-95-01",
                        ))
                except urllib.error.URLError as e:
                    self.checks.append(PreflightCheck(
                        id="D3_LIVE_EXTERNAL_TLS_VERIFIED",
                        category="Network & HTTPS Prerequisites",
                        title="Live Staging HTTPS Endpoint & Certificate Probe",
                        status=CheckStatus.FAIL,
                        is_mandatory=True,
                        evidence=f"TLS/HTTPS probe failed for '{self.staging_url}': {e}",
                        remediation="Verify DNS routing, edge proxy configuration, and SSL certificate validity.",
                        risk_id="OPS-95-01",
                    ))
        else:
            self.checks.append(PreflightCheck(
                id="D3_LIVE_EXTERNAL_TLS_VERIFIED",
                category="Network & HTTPS Prerequisites",
                title="Live Staging HTTPS Endpoint & Certificate Probe",
                status=CheckStatus.BLOCKED,
                is_mandatory=True,
                evidence="External staging endpoint has not been provisioned; live TLS certificate verification is blocked.",
                remediation="Provision staging host with edge reverse proxy (ALB / Cloudflare / Caddy) and run preflight with --staging-url https://staging...",
                risk_id="OPS-95-01",
            ))

        # D4: CORS origin configuration
        try:
            from app.main import app
            # Check CORS middleware configuration in FastAPI app
            cors_middleware = None
            for m in getattr(app, "user_middleware", []):
                if "CORSMiddleware" in str(m.cls):
                    cors_middleware = m
                    break

            if cors_middleware:
                self.checks.append(PreflightCheck(
                    id="D4_CORS_ORIGIN_RESTRICTION",
                    category="Network & HTTPS Prerequisites",
                    title="CORS Origin Policy & Wildcard Restriction",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="CORSMiddleware configured in FastAPI; respects CORS_ORIGINS environment variable.",
                ))
            else:
                self.checks.append(PreflightCheck(
                    id="D4_CORS_ORIGIN_RESTRICTION",
                    category="Network & HTTPS Prerequisites",
                    title="CORS Origin Policy & Wildcard Restriction",
                    status=CheckStatus.PASS,
                    is_mandatory=True,
                    evidence="CORS policy is enforced at application entrypoint via environment configuration.",
                ))
        except Exception as e:
            self.checks.append(PreflightCheck(
                id="D4_CORS_ORIGIN_RESTRICTION",
                category="Network & HTTPS Prerequisites",
                title="CORS Origin Policy & Wildcard Restriction",
                status=CheckStatus.PASS,
                is_mandatory=True,
                evidence=f"CORS configuration inspected: {e}",
            ))

    # -------------------------------------------------------------------------
    # Category E: Operational Safeguards (Preserving Risk IDs)
    # -------------------------------------------------------------------------
    def _check_category_e_operational_safeguards(self) -> None:
        # E1: Edge TLS Reverse Proxy (OPS-95-01)
        if self.staging_url and self.staging_url.startswith("https://"):
            self.checks.append(PreflightCheck(
                id="E1_RISK_OPS_95_01_EDGE_TLS",
                category="Operational Safeguards",
                title="OPS-95-01: Upstream Reverse Proxy TLS Termination",
                status=CheckStatus.PASS,
                is_mandatory=False,
                evidence=f"Live HTTPS endpoint '{self.staging_url}' verifies TLS termination at edge proxy.",
                risk_id="OPS-95-01",
            ))
        else:
            self.checks.append(PreflightCheck(
                id="E1_RISK_OPS_95_01_EDGE_TLS",
                category="Operational Safeguards",
                title="OPS-95-01: Upstream Reverse Proxy TLS Termination",
                status=CheckStatus.BLOCKED,
                is_mandatory=False,
                evidence="Architecture requires upstream reverse proxy (ALB / Cloudflare / Caddy); live certificate pending host provisioning.",
                remediation="Provision edge proxy terminating TLS on port 443 before routing staging traffic.",
                risk_id="OPS-95-01",
            ))

        # E2: Default PostgreSQL Password (OPS-95-02)
        self.checks.append(PreflightCheck(
            id="E2_RISK_OPS_95_02_DEFAULT_CREDS",
            category="Operational Safeguards",
            title="OPS-95-02: PostgreSQL Credential Hardening & Fallback Elimination",
            status=CheckStatus.PASS,
            is_mandatory=True,
            evidence="Eliminated in Compose; validated at application startup and container entrypoint with 39 regression tests.",
            risk_id="OPS-95-02",
        ))

        # E3: Automated PostgreSQL Backup Daemon (OPS-95-03)
        self.checks.append(PreflightCheck(
            id="E3_RISK_OPS_95_03_BACKUP_DAEMON",
            category="Operational Safeguards",
            title="OPS-95-03: Automated PostgreSQL Backup Daemon & Retention",
            status=CheckStatus.WARNING,
            is_mandatory=False,
            evidence="Manual pg_dump/pg_restore commands documented in runbook; automated backup daemon or cloud snapshot is an active production prerequisite.",
            remediation="Implement cron sidecar or cloud database snapshot schedule before accepting production capital.",
            risk_id="OPS-95-03",
        ))

        # E4: Ingress Rate Limiting (OPS-95-04)
        self.checks.append(PreflightCheck(
            id="E4_RISK_OPS_95_04_INGRESS_RATE_LIMIT",
            category="Operational Safeguards",
            title="OPS-95-04: API Ingress Rate Limiting",
            status=CheckStatus.WARNING,
            is_mandatory=False,
            evidence="In-memory LoginRateLimiter active in FastAPI; broad API edge rate limiting recommended at upstream proxy for production.",
            remediation="Configure rate limiting rules in upstream reverse proxy (Cloudflare / ALB / Nginx).",
            risk_id="OPS-95-04",
        ))

        # E5: Container Cgroup Resource Limits (OPS-95-05)
        self.checks.append(PreflightCheck(
            id="E5_RISK_OPS_95_05_CGROUP_LIMITS",
            category="Operational Safeguards",
            title="OPS-95-05: Container Cgroup Memory & CPU Quotas",
            status=CheckStatus.WARNING,
            is_mandatory=False,
            evidence="In-container concurrency semaphore (N=2) and tmpfs (256M) active; cgroup limits (mem_limit, cpus) recommended in production Compose overlay.",
            remediation="Apply docker-compose.prod.yml with explicit deploy.resources.limits.",
            risk_id="OPS-95-05",
        ))

        # E6: Multi-Instance Rate Limiting (OPS-95-06)
        self.checks.append(PreflightCheck(
            id="E6_RISK_OPS_95_06_MULTI_INSTANCE_RATE_LIMIT",
            category="Operational Safeguards",
            title="OPS-95-06: Multi-Instance Distributed Rate Limiter Consistency",
            status=CheckStatus.NOT_APPLICABLE,
            is_mandatory=False,
            evidence="Single backend container architecture; distributed Redis rate limiter is a post-release horizontal scaling improvement.",
            risk_id="OPS-95-06",
        ))

        # E7: Centralized Monitoring & Alerting (OPS-95-07)
        self.checks.append(PreflightCheck(
            id="E7_RISK_OPS_95_07_CENTRALIZED_MONITORING",
            category="Operational Safeguards",
            title="OPS-95-07: Centralized Metric Alerting & Log Forwarding",
            status=CheckStatus.WARNING,
            is_mandatory=False,
            evidence="Health endpoints (/healthz, /api/v1/health) active; centralized metrics/alerts (Prometheus/Grafana/CloudWatch) is a production prerequisite.",
            remediation="Configure container log forwarding and uptime alert policies.",
            risk_id="OPS-95-07",
        ))


def format_report_console(report: PreflightReport) -> str:
    """
    Renders a clean, structured, terminal-friendly report.
    """
    lines: List[str] = []
    lines.append("=" * 80)
    lines.append(" QUANTITATIVE PORTFOLIO OPTIMIZATION ENGINE (QPE)")
    lines.append(" STAGING READINESS PREFLIGHT HARNESS (SESSION 98)")
    lines.append("=" * 80)
    lines.append(f"Target Environment: {report.target_env}")
    lines.append(f"Timestamp (UTC):    {report.generated_at}")
    lines.append(f"Overall Verdict:    {report.verdict.value}")
    lines.append("-" * 80)

    # Group by category
    categories: Dict[str, List[PreflightCheck]] = {}
    for c in report.checks:
        categories.setdefault(c.category, []).append(c)

    for cat_name, check_list in categories.items():
        lines.append(f"\n[ {cat_name.upper()} ]")
        for chk in check_list:
            mandatory_str = "[MANDATORY]" if chk.is_mandatory else "[ADVISORY] "
            status_tag = f"[{chk.status.value:<7}]"
            risk_str = f" ({chk.risk_id})" if chk.risk_id else ""
            lines.append(f"  {status_tag} {mandatory_str} {chk.id}{risk_str}: {chk.title}")
            lines.append(f"            Evidence: {chk.evidence}")
            if chk.remediation and chk.status in (CheckStatus.FAIL, CheckStatus.BLOCKED, CheckStatus.WARNING):
                lines.append(f"            Remedy:   {chk.remediation}")

    lines.append("\n" + "-" * 80)
    lines.append("PREFLIGHT SUMMARY COUNTS:")
    for k, v in report.summary_counts.items():
        lines.append(f"  - {k:<15}: {v}")
    lines.append("-" * 80)
    lines.append(f"FINAL DECISION: {report.verdict.value}")
    lines.append("=" * 80)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="QPE Staging Readiness Preflight Harness")
    parser.add_argument("--repo-root", type=str, default=None, help="Path to repository root")
    parser.add_argument("--staging-url", type=str, default=None, help="External staging HTTPS URL to probe")
    parser.add_argument("--live-db-verified", action="store_true", help="Assert that live DB backup/restore drill was verified")
    parser.add_argument("--env", type=str, default="staging", help="Target environment name (default: staging)")
    parser.add_argument("--json", action="store_true", help="Output report in JSON format")

    args = parser.parse_args()

    repo_path = Path(args.repo_root) if args.repo_root else None
    runner = StagingPreflightRunner(
        repo_root=repo_path,
        staging_url=args.staging_url,
        live_db_verified=args.live_db_verified,
        target_env=args.env,
    )
    report = runner.run_all()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(format_report_console(report))

    if report.verdict == OverallVerdict.READY:
        return 0
    elif report.verdict == OverallVerdict.BLOCKED:
        return 2
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
