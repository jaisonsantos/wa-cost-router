# Guia de Contribuição

## Workflow

1. Fork/clonar repositório.
2. Criar branch a partir de `main`:
   - `feature/<nome-curto>` para features.
   - `fix/<issue>` para correções.
3. Commit mensagens no formato Conventional Commits (`feat:`, `fix:`, `docs:` etc.).
4. Garantir lint/testes locais (quando disponíveis).
5. Abrir Pull Request:
   - Descrever mudança, passos de teste manual e impacto.
   - Referenciar issues relacionadas.

## Padrões de Código

- **Backend**: seguir PEP8, usar `black`/`isort`. Tipagem opcional (pydantic/typing).
- **Frontend**: `eslint` + `prettier`. Componentes com tipagem TS completa.
- **Tests**: (a criar) – preferir Pytest e Vitest.

## Revisão

- Pelo menos 1 revisor.
- Checklist PR:
  - [ ] Migrations atualizadas/descritas.
  - [ ] Contratos API documentados.
  - [ ] Log/telemetria adicionada se pertinente.
  - [ ] Testes manuais descritos.

## Segurança

- Nunca commitar secrets.
- Usar `.env` local e Vault para produção.
- Reportar vulnerabilidades em canal privado (security@empresa.com).

## Releases

- Usar tags semânticas (`vX.Y.Z`).
- Atualizar `docs/CHANGELOG.md` com cada release.
