# Plano de Implementação — Ciclo Contatos/Opt-ins

## Sumário da iteração
- **Período:** 14/10/2024 – 08/11/2024 (janela de preparação para piloto externo com foco em contatos/opt-ins).
- **Escopo principal:** Disponibilizar catálogo multi-tenant de contatos com gestão completa de consentimentos e integrações mínimas necessárias para validação com parceiros piloto.
- **Responsáveis:**
  - **Tech Lead (Squad Core Routing):** Orquestra migrações, APIs e webhook WA.
  - **PM (Squad Operações):** Coordena alinhamento com compliance e parceiros piloto.
  - **QA Lead (Squad Quality Enablement):** Formaliza cenários de aceite, monitora auditoria de opt-ins e sanitização de PII.

## 1. Objetivos e critérios de sucesso
- Catálogo de contatos multi-tenant disponível via API e UI, com importação em massa validada e deduplicação por `org_id`.
- Registro de consentimento com trilha auditável (timestamp, origem, prova de aceitação) acessível via relatórios e API.
- Webhook WhatsApp multi-tenant operando com roteamento por `phone_id → org_id` e validação de consentimento antes de respostas automatizadas.
- Sanitização de payloads/logs contendo PII aplicada aos novos fluxos e documentada em playbooks operacionais.
- Conectores CRM priorizados (HubSpot) sincronizando opt-ins em modo beta, destravando o planejamento dos épicos E3/E4.
- Confirmação explícita no [índice do backlog por caso de uso](../backlog/INDEX_BY_USE_CASE.md) de que os cards marcados como **P0** em UC-01/UC-02 atingiram estado "Concluído" antes do encerramento do ciclo.

## 2. Escopo e entregas previstas
| Frente | Entrega | Critério de aceite |
| --- | --- | --- |
| **Catálogo multi-tenant (P0)** | Nova tabela `contact_profile` com migração assistida, API CRUD e importação CSV validada. | ✅ Entregue em 08/10 — revisões Alembic `007-009` publicadas, import worker com relatório de erros em [`docs/operations/MIGRATIONS.md`](../operations/MIGRATIONS.md) e card [`20251006-migration-base`](../backlog/20251006-migration-base.md) marcado como concluído.
| **Timeline e consentimento (P0)** | Endpoint `/contacts/{id}/consents` com versionamento, gravação da origem e exposição no frontend. | ✅ Entregue — histórico exposto via schemas de [`backend/app/schemas/contacts.py`](../../backend/app/schemas/contacts.py) e documentação do fluxo em [`docs/operations/RUNBOOK_CONTACTS.md`](../operations/RUNBOOK_CONTACTS.md); card [`20251008-contact-opt-in`](../backlog/20251008-contact-opt-in.md) concluído.
| **Webhook WA (P0)** | Mapeamento dinâmico `phone_id` ↔ `org_id` com isolamento de payloads e enriquecimento de consentimento. | 🔄 Em andamento — consentimento já integrado ao roteamento, aguardando finalizar backlog [`20251006-webhook-multi-tenant`](../backlog/20251006-webhook-multi-tenant.md).
| **Sanitização e governança (P0)** | Middleware de sanitização, rotinas de limpeza e atualização dos playbooks de incidentes. | 🔄 Em execução — controles LGPD reforçados em [`docs/security/PRIVACY_CONTROLS.md`](../security/PRIVACY_CONTROLS.md) e runbook atualizado; falta concluir sanitização de logs (`20251006-sanitizacao-pii`).
| **CRM HubSpot (P1)** | Sync inicial de opt-ins/opt-outs com fila de retries e monitoramento básico. | ✅ Beta disponível — serviços em [`backend/app/services/crm/`](../../backend/app/services/crm/) operando com incremental sync e configuração documentada em [`docs/operations/INTEGRATIONS.md`](../operations/INTEGRATIONS.md).

## 3. Sequenciamento e marcos
| Marco | Data-alvo | Descrição | Dependências |
| --- | --- | --- | --- |
| **M1 — Migração e API base** | 18/10 | Criar schema, migrar dados existentes e expor endpoints CRUD com validações. | Sanitização de PII (card `20251006-sanitizacao-pii`). |
| **M2 — Timeline e consentimento** | 23/10 | Implementar versionamento de consentimento, UI e eventos de auditoria. | M1 concluído; ajustes de contratos frontend (`20251006-contratos-api-fe`). |
| **M3 — Webhook WA multi-tenant** | 28/10 | Roteamento por `org_id`, validação de opt-in e fallback de provedores. | Circuit breaker (`20251006-circuit-breaker`) e mapa de phone ids. |
| **M4 — Sanitização e playbooks** | 30/10 | Middleware de mascaramento, retenção e atualização de docs operacionais. | M1–M3 entregues para validar cenários reais. |
| **M5 — Beta com HubSpot** | 08/11 | Sync parcial de opt-ins e relatório consolidado para parceiros piloto. | M2 concluído, credenciais configuradas (`20251006-proteger-admin-metrics`). |

## 4. Dependências críticas e alinhamento
- **Segurança e compliance:** Cards `20251006-sanitizacao-pii`, `20251006-proteger-admin-metrics` e `20251006-enforce-secret-strength` promovidos a **P0**; execução coordenada com time de segurança.
- **Frontend:** Adequação dos contratos (`20251006-contratos-api-fe`) e exposição do histórico de consentimento em `src/pages/Contacts` até M2.
- **Observabilidade:** Integração com logs mascarados e métricas de opt-ins documentada em `docs/operations/OPERATIONS.md`.
- **CRM:** Disponibilidade do conector HubSpot e acordos de dados com parceiros antes de M5.

## 5. Plano de validação e aceite
1. **QA funcional:** Casos automatizados cobrindo importação, deduplicação e fluxo completo de opt-in/out (happy path + rejeições).
2. **QA segurança:** Revisão de sanitização e rotinas de expurgo com o time de segurança antes do go-live.
3. **UAT com parceiros:** Executar checklist de consentimento com dois parceiros piloto entre 04/11 e 08/11, registrando evidências.
4. **Observabilidade:** Dashboards de opt-ins ativos por `org_id` publicados no Grafana interno.
5. **Go/No-Go:** Reunião 08/11 com PM, Tech Lead e Security para liberar o piloto externo.

## 6. Comunicação e governança
- Atualizar o status diário no canal `#proj-wa-optin` destacando progresso dos P0 e riscos.
- Registrar decisões relevantes no [`docs/current-cycle/AGENTE.md`](./AGENTE.md) e refletir impactos no backlog (`docs/backlog/README.md`).
- Revisar o roadmap quinzenalmente, garantindo que dependências para E3/E4 permaneçam bloqueadas até que os critérios deste plano sejam cumpridos.
