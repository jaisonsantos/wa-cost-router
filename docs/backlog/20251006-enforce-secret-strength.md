---
title: "Enforce secrets fortes (APP_SECRET_KEY / JWT_SECRET)"
type: hardening
prio: P1
estimate: "1d"
owner: "unassigned"
depends_on: []
---

## Contexto

A migration [`002_encrypt_provider_credentials`](../../backend/alembic/versions/002_encrypt_provider_credentials.py) usa `APP_SECRET_KEY` para criptografar credenciais. Atualmente aceitamos defaults fracos (`please-change-me`). Precisamos garantir que ambientes de produção não iniciem com secrets inseguros.

## Escopo

- Validar secrets na inicialização (FastAPI) e abortar com erro claro caso valores default sejam detectados.
- Documentar processo de rotação e requisitos mínimos (tamanho, entropia) em [Segurança](../security/SECURITY.md).
- Atualizar `.env.example` com instruções destacadas.
- Garantir que seeds/tests continuem funcionando em ambiente local.

## Acceptance Criteria

- Aplicação não inicia em produção (`ENV != development`) com secrets padrão.
- Logs informam como gerar novos secrets (ex.: `openssl rand -base64 32`).
- Guia de operações e Postman README mencionam necessidade de definir secrets antes de rodar.

## Subtasks

- [ ] Criar validação em `app/core/config.py` ou na inicialização do app.
- [ ] Atualizar documentação relevante (`docs/security/SECURITY.md`, `docs/operations/OPERATIONS.md`).
- [ ] Ajustar `docker-compose.yml` para usar secrets seguros via `.env`.

## Referências

- [Segurança](../security/SECURITY.md)
- [Operações](../operations/OPERATIONS.md)
- Migration: [`002_encrypt_provider_credentials`](../../backend/alembic/versions/002_encrypt_provider_credentials.py)

## Out of Scope

- Integração com vault/secret manager corporativo (será tratado em roadmap de deploy).
