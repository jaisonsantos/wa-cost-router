# Status de Implementação - WA Cost Router

**Data da Última Atualização**: 2025-10-07

Consulte a situação detalhada dos casos de uso e suas dependências na [matriz de rastreabilidade atualizada](../../current-cycle/USE_CASE_TRACEABILITY.md).

## Visão geral por fase

| Fase | Status real | Observações principais |
| --- | --- | --- |
| Fase 1 – Autenticação e ponte FE/BE | ✅ Concluída | Fluxos de login/registro com JWT, proteção de rotas (`PrivateRoute`) e hooks do React Query operacionais. |
| Fase 2 – Funcionalidades core | ⚠️ Parcial | Regras, provedores, integrações WA e importação de tarifas estão funcionais, mas permanecem lacunas de multi-tenant no webhook e exportações. |
| Fase 3 – Dashboard e métricas avançadas | ⚠️ Parcial | APIs de métricas e simuladores entregues, porém análises dependem de dados limitados e faltam exports/insights de SLA previstos. |
| Fase 4 – Backend MVP completo | ⚠️ Parcial | Pipeline de envio, conectores e criptografia prontos; hardening (sanitização, proteção `/admin/metrics`, testes reais) segue pendente. |

---

## Fase 1 – Autenticação e Integração Frontend-Backend (Status: concluída)

### Entregas confirmadas
- Autenticação JWT com fluxo de registro e login (`/auth/register`, `/auth/login`) e armazenamento seguro via `AuthContext`/localStorage.
- Proteção de rotas com `PrivateRoute`, interceptação de 401 no client (`src/lib/api.ts`) e logout consistente.
- Dashboard inicial, hooks (`useSummary`, `useEvents`) e demais páginas consumindo APIs reais.

### Lacunas relevantes
- Nenhuma lacuna crítica registrada para esta fase após o hardening do MVP.

---

## Fase 2 – Funcionalidades Core (Status: parcial)

### Entregas confirmadas
- Página de Regras com CRUD completo, toggle, simulador e formulário visual (`RuleFormDialog`).
- Página de Configurações consumindo `POST /integrations/wa/connections`, importação CSV em `/rates/import_csv` e listagem de tariffs (`useRates`).
- Página de Provedores com criação, configuração de credenciais criptografadas e health check assíncrono.

### Itens parciais ou não implementados
- **Parcial** – Webhook WhatsApp ainda depende de `phone_id` global; falta o mapeamento multi-tenant solicitado no gap analysis para isolar conexões entre organizações.
- **Parcial** – Sanitização/anonimização de payloads (`MessageEvent.attributes`, variáveis de template) ainda não ocorre, mantendo o risco de PII em claro.
- **Não implementado** – Botão de “Exportar CSV” em `Reports.tsx` é apenas visual; backend/frontend não expõem a exportação planejada.

---

## Fase 3 – Dashboard e Métricas Avançadas (Status: parcial)

### Entregas confirmadas
- Endpoints `/reports/summary` e `/reports/dashboard-metrics` calculando baseline vs. otimizado, taxa de sucesso e agregações.
- Simulador avançado (`/rules/simulate-advanced`) com breakdown por país/provedor e componente React dedicado.
- Página de Reports com filtros de período e visualizações de custos/savings.

### Itens parciais ou não implementados
- **Parcial** – Métricas dependem de eventos gerados pelo próprio router; ainda não há ingestão consolidada de contatos ou canais inbound para alimentar KPIs multicanal (UC-01/UC-02).
- **Parcial** – Recomendações e alertas exibidos são heurísticos; ausência de monitoramento real de SLA/filas limita o valor prometido.
- **Não implementado** – Exportação de relatórios (CSV/Excel) e drill-down detalhado continuam pendentes conforme planejado.

---

## Fase 4 – Backend MVP Completo (Status: parcial)

### Entregas confirmadas
- Pipeline de envio (`POST /messages/send`) com idempotência, motor de roteamento (`RoutingEngine`), retries e fallback.
- Persistência completa de `MessageJob`, `DeliveryAttempt`, `CostRecord` e gravação de eventos via webhook.
- Conectores para 360dialog, Gupshup e sandbox, além de credenciais criptografadas com Fernet (`security.py`) e migrations 000–006 versionando o schema.

### Itens parciais ou não implementados
- **Parcial** – Execução de migrations/seeds continua manual; falta automatização/verificação contínua em pipelines.
- **Parcial** – Rotas administrativas (`/admin/metrics`) seguem sem autenticação, contrariando o hardening previsto.
- **Parcial** – Sanitização de entradas (E.164, variáveis de template) e rate limiting por organização ainda não foram implementados.
- **Não implementado** – Testes de envio contra provedores reais (fora do sandbox) permanecem pendentes para homologação.

---

## Desvios vs. plano original
- **UC-01 – Gestão de contatos unificada:** não implementado. Ainda não existem modelos/APIs de contatos, importação com deduplicação ou timeline por `contact_id`, bloqueando integrações previstas.
- **UC-02 – Atendimento multicanal orquestrado:** não implementado. O roteador continua restrito ao WhatsApp outbound, sem conectores inbound, filas ou SLA monitorado.
- **UC-03 – CRM e jornada integrada:** não implementado. Conectores HubSpot/Salesforce, mapeamento de campos e estratégia de retries permanecem apenas no backlog.
- **UC-04 – Oferta white-label e governança comercial:** não implementado. Theming por tenant, RBAC avançado, catálogo de planos e auditoria seguem ausentes.
- **Segurança & Operações:** parcial. Sanitização de PII, proteção de `/admin/metrics`, rate limiting, bem como monitoramento automatizado das migrations ainda não atendem ao plano original.

