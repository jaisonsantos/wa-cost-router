# Plano de Próxima Etapa

## Índice
- [Resumo executivo](#resumo-executivo)
- [Épicos e objetivos mensuráveis](#épicos-e-objetivos-mensuráveis)
- [Quadro de tasks priorizadas](#quadro-de-tasks-priorizadas)
- [Mapa de impacto](#mapa-de-impacto)
- [Plano de testes e health-checks](#plano-de-testes-e-health-checks)
- [Backlog sugerido](#backlog-sugerido)
- [Riscos, rollout e rollback](#riscos-rollout-e-rollback)
- [Navegação entre docs](#navegação-entre-docs)

## Resumo executivo
O mapeamento de lacunas em [`docs/analysis/USE_CASE_GAP.md`](../analysis/USE_CASE_GAP.md) evidenciou que o MVP atual atende apenas ao disparo outbound no WhatsApp. Faltam estruturas essenciais para operar em produção com clientes que exigem catálogo de contatos, atendimento multicanal e integração com o CRM já existente.

- **Gestão de contatos (UC-01)**: números ficam isolados em `MessageJob` e não há consentimento, atributos nem API de consulta, inviabilizando segmentação e compliance.
- **Atendimento multicanal (UC-02)**: o roteador não suporta canais inbound nem monitora filas/SLA, obrigando operações a manter pilhas paralelas.
- **Integrações CRM (UC-03)**: não existem conectores ou webhooks outbound para sincronizar tickets, oportunidades e timeline de mensagens.
- **Oferta white-label (UC-04)**: branding fixo, ausência de RBAC granular e relatórios customizados impedem parceiros de revender o produto.

O plano desta etapa prioriza entregar esses blocos para liberar o piloto multicanal com parceiros, mantendo a base técnica alinhada às expectativas comerciais e de governança.

Para acompanhar o progresso por caso de uso, utilize a matriz dedicada em [`USE_CASE_TRACEABILITY`](./USE_CASE_TRACEABILITY.md).

## Épicos e objetivos mensuráveis
### E1. Plataforma de contatos e consentimento (P0)
**Objetivo mensurável:** Catálogo de contatos multi-tenant com APIs de CRUD/importação, timeline vinculada a mensagens e cobertura Newman, atendendo à UC-01 do [`USE_CASE_GAP`](../analysis/USE_CASE_GAP.md).

### E2. Orquestração de atendimento multicanal (P0)
**Objetivo mensurável:** Entradas e saídas em WhatsApp, e-mail e chat web compartilhando contratos unificados, filas e SLAs monitoradas com alertas operacionais, conforme UC-02.

### E3. CRM sincronizado com jornada (P0)
**Objetivo mensurável:** Conectores prioritários (HubSpot/Salesforce) entregam sincronização bidirecional de contatos e tickets com retries monitorados, alinhados à UC-03.

### E4. White-label e governança comercial (P1)
**Objetivo mensurável:** Tenants configuram branding, domínios e perfis de acesso diferenciados, gerando relatórios com identidade do parceiro segundo UC-04.

## Quadro de tasks priorizadas
| ID | Título | Prioridade | Owner sugerido | Estimativa | Dependências | Risco | DoD |
|----|--------|------------|----------------|------------|--------------|-------|-----|
| T1 | Catálogo de contatos multi-tenant | P0 | Backend | 5d | E1 | Alto (migração de dados) | • Caso de uso: UC-01 — Gestão de contatos unificada ([`USE_CASE_GAP`](../analysis/USE_CASE_GAP.md)).<br>• Criar tabela de contatos com `org_id`, atributos customizáveis, opt-in/out e índices de deduplicação.<br>• Expor endpoints REST/CSV para CRUD e importação com validação de consentimento.<br>• Atualizar [`DATA_MODEL`](../architecture/DATA_MODEL.md), [`API_REFERENCE`](../api/API_REFERENCE.md) e exemplos na coleção Postman.<br>• `make dev` + `make ci` verdes com migração aplicada em base existente. |
| T2 | Timeline e vinculação de mensagens a contatos | P0 | Backend | 3d | T1 | Médio | • Caso de uso: UC-01 — Gestão de contatos unificada.<br>• Persistir `contact_id` em `MessageJob`, eventos e relatórios, garantindo retrocompatibilidade via backfill.<br>• Ajustar consultas de relatórios/dashboard para exibir métricas por contato e consentimento.<br>• Atualizar [`API_REFERENCE`](../api/API_REFERENCE.md), [`ARCHITECTURE`](../architecture/ARCHITECTURE.md) e scripts `seed`/Postman.<br>• `make dev` + `make ci` verdes. |
| T3 | Infra de canais inbound/outbound unificados | P0 | Backend | 6d | E2 | Alto (novos conectores) | • Caso de uso: UC-02 — Atendimento multicanal orquestrado.<br>• Implementar abstração de canais com contratos de envio/recebimento e filas por canal (WhatsApp, e-mail, chat web mínimo).<br>• Disponibilizar webhooks inbound com roteamento por `contact_id` e preferências.<br>• Atualizar [`ARCHITECTURE`](../architecture/ARCHITECTURE.md), [`API_REFERENCE`](../api/API_REFERENCE.md) e [`OPERATIONS`](../operations/OPERATIONS.md).<br>• `make dev` + `make ci` verdes + smoke manual validando recebimento inbound. |
| T4 | Monitoramento de SLA e painel de atendimento | P0 | Full-stack | 4d | T3 | Médio | • Caso de uso: UC-02 — Atendimento multicanal orquestrado.<br>• Construir métricas de fila/SLA (tempo primeira resposta, backlog) e expor em dashboard no frontend.<br>• Adicionar alertas Prometheus + documentação operacional para thresholds.<br>• Atualizar [`ARCHITECTURE`](../architecture/ARCHITECTURE.md), [`OPERATIONS`](../operations/OPERATIONS.md) e capturas em [`Ciclo Atual`](./README.md).<br>• `make dev` + `make ci` verdes + smoke FE cobrindo dashboards. |
| T5 | Conectores CRM prioritários e reconciliamento | P0 | Integrations | 5d | E3 | Alto (terceiros) | • Caso de uso: UC-03 — CRM e jornada integrada.<br>• Entregar conectores HubSpot e Salesforce com sync bidirecional de contatos, tickets e oportunidades, incluindo retries/dead-letter.<br>• Expor webhooks configuráveis por tenant e registrar falhas em observabilidade.<br>• Atualizar [`INTEGRATIONS`](../architecture/INTEGRATIONS.md), [`OPERATIONS`](../operations/OPERATIONS.md) e [`SECURITY`](../security/SECURITY.md).<br>• `make dev` + `make ci` verdes + testes Newman simulando callbacks. |
| T6 | White-label, RBAC e branding por tenant | P1 | Frontend/Platform | 4d | E4 | Médio | • Caso de uso: UC-04 — Oferta white-label e governança comercial.<br>• Implementar theming (logo/cores), domínios customizados e RBAC (partner admin, org admin, agent) com auditoria de ações.<br>• Atualizar [`ARCHITECTURE`](../architecture/ARCHITECTURE.md), [`DEPLOYMENT`](../operations/DEPLOYMENT.md) e [`SECURITY`](../security/SECURITY.md).<br>• `make dev` + `make ci` verdes + smoke FE validando troca de branding. |

## Mapa de impacto
| Área | Impacto esperado |
|------|-----------------|
| API backend | Novas entidades de contato, contratos multicanal e webhooks inbound/outbound para CRM. |
| Banco de dados | Tabelas de contatos/timeline, índices de deduplicação e auditoria de consentimento. |
| Frontend | Dashboards de SLA, configurações de branding e ferramentas de gestão de contatos. |
| Integrações | Conectores HubSpot/Salesforce, filas de retry e monitoramento dedicado. |
| Postman/QA | Cenários cobrindo contatos, multicanal e CRM com variáveis por tenant. |
| Docs | Atualização de Data Model, API, Operations, Deployment, Security e novo `analysis/USE_CASE_GAP`. |
| CI/CD | Pipelines cobrindo novos serviços externos simulados e smoke multicanal. |
| Segurança | RBAC partner/org, trilhas de auditoria e política de opt-in/out aplicada. |
| Observabilidade | Métricas de SLA, filas por canal e status de sincronização CRM. |

**Progresso recente (2024-10-07):**
- ✅ Discovery com squads de atendimento, growth e parceiros consolidou os requisitos UC-01 a UC-04 no [`USE_CASE_GAP`](../analysis/USE_CASE_GAP.md).
- ✅ Levantamento de dados históricos exportado do CRM sandbox para suportar modelagem de contatos e timeline.
- ✅ Protótipo de dashboard de SLA validado com equipe de operações para calibrar métricas alvo.
- 🔜 Kick-off de T1/T3 para implementar catálogo de contatos e infraestrutura multicanal antes das integrações CRM.

## Plano de testes e health-checks
### Automação local / CI
- ⚠️ `make dev` — aplicar migrations, seed atualizado, subir stack (usar sandbox quando necessário).
- ⚠️ `make ci` — garante lint/build/backend tests + Newman com coleção revisada.

### Smoke manual
- ⚠️ `newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --folder "Messages"` — checar envio + eventos/custos.
- ⚠️ `curl -H "Authorization: Token <METRICS_TOKEN>" http://localhost:8000/admin/metrics` — validar proteção.
- Fluxo web: login → Providers → configurar credenciais fake → Rules simulate (rápida + avançada) → Settings (dados reais).

### Testes unitários
- Backend: pytest para validação de números, mascaramento e sandbox connectors (`backend/tests/test_sandbox_connectors.py`).
- Frontend: React Testing Library para simulador/Settings (renderização com dados reais).

Todos os critérios de DoD incluem `make dev` e `make ci` verdes, além de evidências (logs ou prints) anexadas ao PR.

## Backlog sugerido
Criar os seguintes arquivos em [`docs/backlog/`](../backlog):

1. `20250210-worker-offload.md` (Prioridade P2)
   - **Contexto:** após sandbox, planejar mover envios para RQ worker real para escalar.
   - **Hipótese de valor:** reduzir latência da API e permitir paralelismo controlado.
   - **Escopo inicial:** criar fila `message_send`, endpoint respondendo 202, worker consumindo jobs, garantir idempotência.
   - **DoD:** fila ativa com monitoração, Postman adiciona verificação assíncrona, docs de operações atualizados, `make ci` verde.

2. `20250210-rate-card-multitenant.md` (Prioridade P3)
   - **Contexto:** rate cards ainda globais; clientes grandes podem ter acordos específicos.
   - **Hipótese de valor:** adicionar escopo opcional por organização aumenta flexibilidade comercial.
   - **Escopo inicial:** schema com `org_id` opcional, migração com fallback global, simuladores adaptados.
   - **DoD:** migrations aplicadas, Postman cobre cenário multi-tenant, docs `DATA_MODEL` e `API_REFERENCE` atualizados, `make ci` verde.

3. `20250210-analytics-dashboard-sync.md` (Prioridade P2)
   - **Contexto:** dashboard usa eventos limitados; após T3, alinhar FE com novos campos.
   - **Hipótese de valor:** métricas confiáveis elevam adoção pelos stakeholders.
   - **Escopo inicial:** FE consome `MessageEvent`/`CostRecord` reais, ajustes nas consultas e visualizações.
   - **DoD:** smoke FE com dados reais, Postman valida endpoints, docs em [`Ciclo Atual`](./README.md) atualizados, `make ci` verde.

## Riscos, rollout e rollback
| Épico | Riscos | Mitigação | Rollout | Rollback |
|-------|--------|-----------|---------|----------|
| E1 | Migrações de contatos podem corromper histórico ou violar LGPD por ausência de consentimento. | Backfill idempotente com dry-run, backups por tenant e validação de opt-in antes de publicar. | Deploy por tenant iniciando pelo sandbox interno com monitoração de duplicatas. | Restaurar backup anterior e reexecutar migração com ajustes. |
| E2 | Inbound channels podem causar sobrecarga ou filas não monitoradas. | Feature flags por canal, limites de throughput e dashboards de SLA com alertas antes do GA. | Ativar canal por parceiro piloto com playbook de observabilidade. | Desabilitar canal via flag e drenar filas pendentes. |
| E3 | Integrações CRM podem falhar por limites de API ou mapeamento inconsistente. | Retries com dead-letter, monitoramento dedicado e homologação conjunta com parceiros. | Habilitar conectores por org com checklist de credenciais e mapping aprovado. | Pausar conector específico e reprocessar mensagens a partir da fila de retry. |
| E4 | Customizações white-label podem quebrar login/domínio ou expor dados entre tenants. | Testes automatizados de RBAC, validação de domínio antes de apontar DNS e auditoria contínua. | Rollout progressivo por parceiro com verificação manual de branding. | Reverter branding para default e restaurar perfis anteriores a partir do backup. |

## Navegação entre docs
- [Visão geral](./README.md)
- [Arquitetura](../architecture/ARCHITECTURE.md)
- [Modelagem de Dados](../architecture/DATA_MODEL.md)
- [Referência da API](../api/API_REFERENCE.md)
- [Operações](../operations/OPERATIONS.md)
- [Guia de Migrations](../operations/MIGRATIONS.md)
- [Segurança](../security/SECURITY.md)
- [Postman](../postman/README.md)
- [Matriz de casos de uso](./USE_CASE_TRACEABILITY.md)
- [Backlog Prioritário](../backlog/README.md)

Este plano consolida a próxima etapa crítica antes do rollout externo, garantindo que documentação, scripts, coleção Postman e pipelines permaneçam alinhados ao código.
