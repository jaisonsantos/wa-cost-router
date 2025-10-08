# Pós-mortem — Plano de Próxima Etapa

## Sumário da iteração
- **Período:** 30/09/2024 – 11/10/2024 (janela de hardening pré-piloto externo).
- **Responsáveis principais:** Tech Lead (Squad Core Routing), PM (Squad Operações) e QA Lead (Squad Quality Enablement).
- **Escopo planejado:** Executar o plano de próxima etapa para entregar os épicos E1–E4 — catálogo de contatos multi-tenant, orquestração multicanal inbound/outbound, conectores CRM e oferta white-label — habilitando o piloto multicanal com parceiros.

## 1. Visão geral
A iteração fechou o planejamento original com forte desvio para mitigações de segurança e multi-tenant identificadas durante o piloto interno. As squads priorizaram ajustes estruturais (ex.: segregação por `org_id`, criptografia de credenciais e contratos de mensagens) para conter riscos imediatos, mas os épicos planejados permaneceram majoritariamente em estado preparatório.

Principais conclusões:
- O plano original superestimou a capacidade de executar épicos verdes enquanto pendências críticas de hardening (webhook multi-tenant, sanitização de PII e proteção de métricas administrativas) continuavam bloqueando o piloto externo.
- Entregas técnicas não previstas — como reforço de multi-tenant na API e criptografia de credenciais legadas — consumiram o buffer destinado aos épicos E1–E4.
- A rastreabilidade de casos de uso permanece relevante: a matriz em [`USE_CASE_TRACEABILITY.md`](./USE_CASE_TRACEABILITY.md) continua como fonte de verdade para status e dependências.

## 2. Status dos épicos planejados
| Épico | Objetivo original | Status final | Entregas principais | Pendências e motivos |
| --- | --- | --- | --- | --- |
| **E1. Plataforma de contatos e consentimento** | Catálogo multi-tenant com APIs de CRUD/importação, timeline e consentimento. | **Parcial** — discovery e modelagem revisados; sem entregas em produção. | Documentação de requisitos consolidada, análise de migração e ajustes preliminares de seeds. | `T1`/`T2` continuam abertos por risco de migração sem sanitização (`20251006-sanitizacao-pii`) e falta de estratégia de backfill controlado. |
| **E2. Orquestração de atendimento multicanal** | Canais inbound/outbound (WhatsApp, e-mail, chat) com filas e SLAs monitorados. | **Parcial** — protótipo de SLA validado; infraestrutura multicanal não concluída. | Retenção de métricas exploratórias e revisão do roteador para respeitar `org_id`. | Webhook WhatsApp multi-tenant (`20251006-webhook-multi-tenant`) e circuito de provedores (`20251006-circuit-breaker`) seguem bloqueando o rollout. |
| **E3. CRM sincronizado com jornada** | Conectores HubSpot/Salesforce com sync bidirecional e retries monitorados. | **Não iniciado** — aguardando conclusão de E1/E2. | Nenhuma entrega. | Dependências diretas de catálogo/timeline e infraestrutura multicanal, além de requisitos de auditoria ainda não endereçados. |
| **E4. White-label e governança comercial** | Branding por tenant, RBAC granular e relatórios customizados. | **Não iniciado** — aguardando base multi-tenant estabilizada. | Nenhuma entrega. | Prioridade redirecionada para hardening de segurança e multicanal; backlog de RBAC permanece aberto (`20251006-proteger-admin-metrics`). |

## 3. Entregas confirmadas
Mesmo fora do escopo original, as squads registraram avanços críticos para a saúde do MVP:
- **Roteamento e providers multi-tenant:** todos os endpoints de providers e o `RoutingEngine` agora impõem `org_id`, evitando vazamentos entre clientes.
- **Criptografia de credenciais:** `ProviderCredential.credentials_encrypted` foi migrado para armazenamento criptografado com Fernet, incluindo backfill (`migration 002`).
- **Contratos de mensagens revisados:** endpoints alinharam `is_configured`, `provider_name` e agregados de custo para o frontend, reduzindo divergências de contrato.
- **Endereçamento de exposição pública:** `GET /rates` passou a exigir autenticação, eliminando acesso público inadvertido.

## 4. Itens em aberto e justificativas
| ID | Título | Status atual | Justificativa de não entrega |
| --- | --- | --- | --- |
| T1 | Catálogo de contatos multi-tenant | Não iniciado | Migração arriscada sem sanitização de PII e sem estratégia de deduplicação segura; esforço deslocado para hardening imediato. |
| T2 | Timeline e vinculação de mensagens | Não iniciado | Depende de T1 e de ajustes nas consultas de relatórios; sem base confiável para retroalimentar contatos. |
| T3 | Infra de canais inbound/outbound unificados | Não iniciado | Webhook multi-tenant e circuito de provedores ainda sem implementação, impossibilitando ativação de canais inbound. |
| T4 | Monitoramento de SLA e painel | Não iniciado | Sem infraestrutura multicanal para gerar métricas reais; protótipo permanece apenas exploratório. |
| T5 | Conectores CRM prioritários | Não iniciado | Sem catálogo/timeline consolidados e sem política de retries auditável; riscos de compliance com parceiros. |
| T6 | White-label, RBAC e branding | Não iniciado | Bloqueado pelos itens de segurança (proteção `/admin/metrics`, RBAC) e por ausência de catálogo multicanal. |

## 5. Riscos e aprendizados
- **Dependências subestimadas:** A ausência de sanitização e isolamento completo entre tenants inviabilizou iniciar migrações sensíveis, reiterando a necessidade de tratar P0s de segurança antes de novos épicos.
- **Buffer insuficiente para hardening:** Sem reserva explícita para correções emergenciais, o escopo planejado foi consumido por débitos identificados no piloto interno.
- **Rastreabilidade deve guiar priorização:** A matriz de casos de uso continua essencial para entender impactos; qualquer replanejamento precisa manter links vivos com backlog e roadmap.

## 6. Continuidade e próximos passos
- **Rastreabilidade:** Consulte [`USE_CASE_TRACEABILITY.md`](./USE_CASE_TRACEABILITY.md) para acompanhar a evolução de UC-01 a UC-04 e os vínculos com backlog e roadmap após este pós-mortem.
- **Replanejamento:** As prioridades revisadas para retomar o piloto externo estão documentadas no [`IMPLEMENTATION_PLAN_ROLLING.md`](./IMPLEMENTATION_PLAN_ROLLING.md), que consolida o novo plano de implementação.
- **Hand-off:** Registrar decisões adicionais no `docs/current-cycle/AGENTE.md` e alinhar squads sobre as pendências críticas (`20251006-webhook-multi-tenant`, `20251006-sanitizacao-pii`, `20251006-proteger-admin-metrics`, `20251006-circuit-breaker`) antes de abrir o piloto externo.

Este pós-mortem encerra o planejamento original e fornece o contexto necessário para a continuidade do ciclo.
