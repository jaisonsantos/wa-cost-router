#!/usr/bin/env python3
"""Publish CI Lite results to GitHub Checks and PR comments.

This helper is part of the mitigation for GitHub Actions billing blocks. When the
hosted runners refuse to start, teams can run ``scripts/ci_lite.py`` locally,
generate the ``summary.json``/``summary.md`` artifacts and then execute this
script to publish a manual status back to GitHub.

The script supports creating a "check run" on a commit SHA and, optionally,
posting a comment on a pull request with the markdown summary. It only relies on
the standard library so it can run in constrained environments.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Publicar resultados do CI Lite manualmente no GitHub")
    parser.add_argument(
        "--summary",
        default=Path("artifacts/ci-lite/summary.json"),
        type=Path,
        help="Caminho para o summary.json gerado pelo scripts/ci_lite.py",
    )
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="owner/repo")
    parser.add_argument(
        "--sha",
        help="Commit SHA para associar o check run (default: HEAD)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="Token GitHub com escopo 'repo' e permissões de checks",
    )
    parser.add_argument(
        "--check-name",
        default="ci-lite (manual)",
        help="Nome exibido no check run",
    )
    parser.add_argument(
        "--details-url",
        help="URL opcional para apontar logs completos (por exemplo, artefato compartilhado)",
    )
    parser.add_argument(
        "--pr",
        type=int,
        help="Número do PR para comentar (opcional)",
    )
    parser.add_argument(
        "--comment",
        action="store_true",
        help="Publicar comentário no PR além do check run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não publica nada, apenas exibe a payload gerada",
    )

    args = parser.parse_args(argv)

    if not args.repo:
        print("[erro] informe --repo ou defina GITHUB_REPOSITORY", file=sys.stderr)
        return 1
    if not args.token and not args.dry_run:
        print("[erro] informe --token ou defina GITHUB_TOKEN", file=sys.stderr)
        return 1

    if not args.summary.exists():
        print(f"[erro] summary não encontrado em {args.summary}", file=sys.stderr)
        return 1

    sha = args.sha or _git_rev_parse()
    if not sha:
        print("[erro] não foi possível determinar o SHA. Passe --sha explicitamente.", file=sys.stderr)
        return 1

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    markdown = _build_markdown(summary, args.details_url)

    if args.dry_run:
        payload = _check_run_payload(args.check_name, sha, summary, markdown, args.details_url)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        if args.comment and args.pr:
            comment = _comment_payload(markdown)
            print("\n--- PR comment payload ---\n")
            print(json.dumps(comment, indent=2, ensure_ascii=False))
        return 0

    response = _post_check_run(
        repo=args.repo,
        token=args.token,
        payload=_check_run_payload(args.check_name, sha, summary, markdown, args.details_url),
    )
    print(f"[ok] check run publicado: {response.get('html_url', 'sem link')}")

    if args.comment and args.pr:
        comment_response = _post_comment(
            repo=args.repo,
            token=args.token,
            issue_number=args.pr,
            body=_comment_payload(markdown)["body"],
        )
        print(f"[ok] comentário publicado: {comment_response.get('html_url', 'sem link')}")
    elif args.comment and not args.pr:
        print("[aviso] flag --comment informada sem --pr; comentário não enviado.")

    return 0


def _git_rev_parse() -> Optional[str]:
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return output or None


def _build_markdown(summary: Dict[str, object], details_url: Optional[str]) -> str:
    lines: List[str] = ["## CI Lite", ""]
    status = summary.get("status", "unknown").upper()
    lines.append(f"Status: **{status}**")
    lines.append("")
    lines.append("| Etapa | Status | Duração (s) | Obrigatória | Observações |")
    lines.append("|-------|--------|-------------|-------------|-------------|")
    for entry in summary.get("results", []):
        name = entry.get("name", "-")
        step_status = str(entry.get("status", "unknown")).upper()
        duration = entry.get("duration_seconds")
        duration_value = f"{duration:.2f}" if isinstance(duration, (int, float)) and duration else "-"
        required = "Sim" if entry.get("required", True) else "Não"
        notes: List[str] = []
        if entry.get("skip_reason"):
            notes.append(f"Skipped: {entry['skip_reason']}")
        if entry.get("log_path"):
            notes.append(f"Log: `{entry['log_path']}`")
        metadata = entry.get("metadata") or {}
        if metadata.get("error"):
            notes.append(f"Erro: {metadata['error']}")
        lines.append(
            "| "
            + " | ".join(
                [
                    name,
                    step_status,
                    duration_value,
                    required,
                    "<br />".join(notes) if notes else "",
                ]
            )
            + " |"
        )

    if details_url:
        lines.append("")
        lines.append(f"Logs completos: {details_url}")

    lines.append("")
    lines.append(
        "Gerado por `scripts/ci_lite.py`. Execute novamente após cada mudança relevante"
        " enquanto o GitHub Actions estiver bloqueado por billing."
    )

    return "\n".join(lines)


def _check_run_payload(
    check_name: str,
    sha: str,
    summary: Dict[str, object],
    markdown: str,
    details_url: Optional[str],
) -> Dict[str, object]:
    conclusion = "success" if summary.get("status") == "success" else "failure"
    completed_at = _dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    payload: Dict[str, object] = {
        "name": check_name,
        "head_sha": sha,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": completed_at,
        "output": {
            "title": f"CI Lite {summary.get('status', '').upper()}",
            "summary": markdown,
            "text": textwrap.dedent(
                """
                Resultado manual publicado via scripts/ci_lite_publish.py
                enquanto o GitHub Actions estava indisponível.
                """
            ).strip(),
        },
    }
    if details_url:
        payload["details_url"] = details_url
    return payload


def _post_check_run(repo: str, token: str, payload: Dict[str, object]) -> Dict[str, object]:
    request = urllib.request.Request(
        url=f"https://api.github.com/repos/{repo}/check-runs",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ci-lite-publisher",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Falha ao publicar check run ({exc.code}): {error_body}")


def _comment_payload(markdown: str) -> Dict[str, object]:
    return {
        "body": textwrap.dedent(
            f"""
            ⚠️ *CI hospedado bloqueado por billing*. Resultado manual do `scripts/ci_lite.py`:

            {markdown}
            """
        ).strip()
    }


def _post_comment(repo: str, token: str, issue_number: int, body: str) -> Dict[str, object]:
    request = urllib.request.Request(
        url=f"https://api.github.com/repos/{repo}/issues/{issue_number}/comments",
        data=json.dumps({"body": body}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ci-lite-publisher",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Falha ao publicar comentário ({exc.code}): {error_body}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as exc:
        print(f"[erro] {exc}", file=sys.stderr)
        sys.exit(1)
