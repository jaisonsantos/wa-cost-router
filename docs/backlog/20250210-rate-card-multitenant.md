# 20250210 - Rate cards por organização (P3)

## Contexto
Atualmente os rate cards são globais, impossibilitando acordos comerciais específicos por cliente. Com a evolução do produto, precisamos permitir tarifas por organização mantendo fallback global.

## Hipótese de valor
Oferecer tarifação customizada por organização amplia flexibilidade comercial, viabiliza contratos enterprise e reduz disputas de cobrança.

## Escopo inicial
- Estender modelo `rate_card` para aceitar `org_id` opcional (FK) com fallback global.
- Criar migrations Alembic para incluir coluna, índices e backfill seguro.
- Ajustar importador CSV/API para aceitar escopo de organização.
- Atualizar simuladores e motor de roteamento para respeitar tarifação por organização.
- Revisar seeds para contemplar exemplos multi-tenant.

## Dependências
- Conclusão de T1 (rate card vinculado a provider) e validação dos simuladores (T4).

## DoD
- `make dev` e `make ci` verdes, migrations aplicáveis em base limpa e existente.
- Postman com cenários multi-tenant (variável `org_id`) e asserts diferenciando tarifas.
- Documentação atualizada em [`docs/architecture/DATA_MODEL.md`](../architecture/DATA_MODEL.md), [`docs/api/API_REFERENCE.md`](../api/API_REFERENCE.md) e [`docs/operations/MIGRATIONS.md`](../operations/MIGRATIONS.md).
- Guia de cobrança revisado em [`docs/pricing/PRICING_BILLING.md`](../pricing/PRICING_BILLING.md).
- Evidências anexadas no PR demonstrando cálculo distinto por organização.
