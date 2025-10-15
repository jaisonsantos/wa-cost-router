#!/usr/bin/env python3
"""Local CI fallback runner.

This script mirrors the most critical CI steps when GitHub Actions workflows
are blocked (for example, due to billing issues). It orchestrates frontend and
backend checks without depending on Docker, producing structured logs and a
summary report under ``artifacts/ci-lite``. Também descreve (em português) o
uso recomendado enquanto o Actions estiver bloqueado por billing pendente.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "ci-lite"


def _slugify(value: str) -> str:
    """Convert a step name into a filesystem friendly slug."""
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or "step"


def _command_available(command: str) -> bool:
    return shutil.which(command) is not None


SkipCallback = Callable[[], Optional[str]]


@dataclass
class Step:
    name: str
    command: Iterable[str]
    required: bool = True
    env: Optional[Dict[str, str]] = None
    cwd: Optional[Path] = None
    skip_if: Optional[SkipCallback] = None
    shell: bool = False


@dataclass
class StepResult:
    name: str
    command: List[str]
    status: str
    duration_seconds: float
    log_path: Optional[str] = None
    skip_reason: Optional[str] = None
    required: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, object]:
        data = asdict(self)
        return data


class StepFailed(RuntimeError):
    """Raised when a required step fails."""


def run_step(step: Step) -> StepResult:
    skip_reason = step.skip_if() if step.skip_if else None
    if skip_reason:
        return StepResult(
            name=step.name,
            command=list(step.command),
            status="skipped",
            duration_seconds=0.0,
            log_path=None,
            skip_reason=skip_reason,
            required=step.required,
        )

    slug = _slugify(step.name)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = ARTIFACTS_DIR / f"{slug}.log"

    env = os.environ.copy()
    if step.env:
        env.update(step.env)

    start = time.perf_counter()
    with log_file.open("w", encoding="utf-8") as fp:
        fp.write(f"$ {' '.join(step.command)}\n\n")
        fp.flush()
        process = subprocess.Popen(
            step.command,
            cwd=step.cwd or REPO_ROOT,
            env=env,
            stdout=fp,
            stderr=subprocess.STDOUT,
            shell=step.shell,
            text=True,
        )
        return_code = process.wait()
    duration = time.perf_counter() - start

    status = "success" if return_code == 0 else "failed"
    result = StepResult(
        name=step.name,
        command=list(step.command),
        status=status,
        duration_seconds=duration,
        log_path=str(log_file.relative_to(REPO_ROOT)),
        required=step.required,
    )

    if status != "success" and step.required:
        raise StepFailed(
            f"Step '{step.name}' failed with exit code {return_code}. "
            f"Inspect {result.log_path} for details."
        )

    return result


def _pip_command() -> List[str]:
    python = sys.executable or "python3"
    return [python, "-m", "pip"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run local CI fallback")
    parser.add_argument(
        "--skip-e2e",
        action="store_true",
        help="Skip Playwright/Newman e2e step even if Docker is available.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip dependency installation (npm ci / pip install).",
    )
    args = parser.parse_args(argv)

    steps: List[Step] = []

    if not args.skip_install:
        steps.extend(
            [
                Step(
                    name="npm ci",
                    command=["npm", "ci"],
                    skip_if=lambda: None if _command_available("npm") else "npm não encontrado no PATH",
                ),
                Step(
                    name="pip install backend requirements",
                    command=_pip_command()
                    + [
                        "install",
                        "-r",
                        "backend/requirements-dev.txt",
                    ],
                    skip_if=lambda: None
                    if _command_available("python3") or _command_available("python")
                    else "Python não encontrado no PATH",
                ),
            ]
        )

    steps.extend(
        [
            Step(
                name="lint frontend",
                command=["npm", "run", "lint"],
                skip_if=lambda: None if _command_available("npm") else "npm não encontrado no PATH",
            ),
            Step(
                name="build frontend",
                command=["npm", "run", "build"],
                skip_if=lambda: None if _command_available("npm") else "npm não encontrado no PATH",
            ),
            Step(
                name="pytest backend",
                command=[
                    sys.executable or "python3",
                    "-m",
                    "pytest",
                    "backend/tests",
                ],
                env={"PYTHONPATH": str(REPO_ROOT / "backend")},
                skip_if=lambda: None
                if _command_available("python3") or _command_available("python")
                else "Python não encontrado no PATH",
            ),
            Step(
                name="frontend unit tests",
                command=["scripts/test-frontend.sh"],
                skip_if=lambda: None if (REPO_ROOT / "node_modules").exists() else "node_modules ausente - rode npm ci",
            ),
        ]
    )

    def _check_e2e() -> Optional[str]:
        if args.skip_e2e:
            return "flag --skip-e2e fornecida"
        if not _command_available("docker") and not _command_available("docker-compose"):
            return "Docker não encontrado - e2e depende do stack containerizado"
        return None

    steps.append(
        Step(
            name="e2e regression (docker stack)",
            command=["make", "ci-e2e"],
            skip_if=_check_e2e,
            required=False,
        )
    )

    results: List[StepResult] = []
    failed = False

    for step in steps:
        try:
            results.append(run_step(step))
        except StepFailed as exc:
            failed = True
            results.append(
                StepResult(
                    name=step.name,
                    command=list(step.command),
                    status="failed",
                    duration_seconds=0.0,
                    log_path=str((ARTIFACTS_DIR / f"{_slugify(step.name)}.log").relative_to(REPO_ROOT)),
                    required=step.required,
                    metadata={"error": str(exc)},
                )
            )
            break

    summary = {
        "status": "failed" if failed else "success",
        "results": [result.as_dict() for result in results],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = ARTIFACTS_DIR / "summary.json"
    report_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown_path = ARTIFACTS_DIR / "summary.md"
    markdown_path.write_text(_to_markdown(summary), encoding="utf-8")

    _print_summary(summary)
    return 1 if failed else 0


def _print_summary(summary: Dict[str, object]) -> None:
    results = summary["results"]
    print("\nCI Lite Summary")
    print("=" * 40)
    for entry in results:
        status = entry["status"]
        name = entry["name"]
        duration = entry["duration_seconds"]
        line = f"- {name}: {status.upper()} ({duration:.2f}s)"
        if entry.get("skip_reason"):
            line += f" — skipped ({entry['skip_reason']})"
        print(line)
        if entry.get("log_path"):
            print(f"    log: {entry['log_path']}")
        if entry.get("metadata", {}).get("error"):
            print(f"    error: {entry['metadata']['error']}")
    print(f"\nOverall status: {summary['status'].upper()}")
    print(f"Report: {ARTIFACTS_DIR.relative_to(REPO_ROOT) / Path('summary.json')}")


def _to_markdown(summary: Dict[str, object]) -> str:
    lines = ["# CI Lite", ""]
    lines.append(f"Status: **{summary['status'].upper()}**")
    lines.append("")
    lines.append("| Etapa | Status | Duração (s) | Obrigatória | Observações |")
    lines.append("|-------|--------|-------------|-------------|-------------|")
    for entry in summary["results"]:
        name = entry["name"]
        status = entry["status"].upper()
        duration = f"{entry['duration_seconds']:.2f}" if entry["duration_seconds"] else "-"
        required = "Sim" if entry.get("required", True) else "Não"
        notes: List[str] = []
        if entry.get("skip_reason"):
            notes.append(f"Skipped: {entry['skip_reason']}")
        if entry.get("log_path"):
            notes.append(f"Log: `{entry['log_path']}`")
        if entry.get("metadata", {}).get("error"):
            notes.append(f"Erro: {entry['metadata']['error']}")
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    status,
                    duration,
                    required,
                    "<br />".join(notes) if notes else "",
                ]
            )
            + " |"
        )

    lines.append("")
    lines.append(
        "Gere este relatório executando `scripts/ci_lite.py` sempre que o GitHub Actions"
        " estiver indisponível. O arquivo `summary.json` correspondente contém os"
        " mesmos dados em formato estruturado."
    )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
