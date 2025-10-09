# Observabilidade — Contatos & Opt-ins

Este guia descreve métricas, logs e alertas usados para acompanhar o rollout multi-tenant do catálogo de contatos e dos fluxos de opt-in.

## Métricas chave

| Métrica | Fonte | Dimensões | Descrição |
| --- | --- | --- | --- |
| `contacts_import_total` | Worker `contacts_import` | `org_id`, `status` (`processed`, `failed`) | Volume total de registros processados por execução. |
| `contacts_import_failed_total` | Worker `contacts_import` | `org_id`, `error_code` | Quantidade de registros descartados durante a importação. |
| `contacts_import_retry_queue_size` | Redis / job scheduler | `org_id` | Quantidade de itens aguardando reprocessamento. |
| `consent_event_total` | API pública | `org_id`, `source`, `state` | Eventos de consentimento ingeridos (opt-in/out). |
| `consent_event_processing_latency_seconds` | Pipeline de eventos | `org_id`, `source` | Latência p95 entre recebimento e persistência do consentimento. |
| `consent_policy_violation_total` | Serviço de governança | `org_id`, `violation_type` | Total de violações de política detectadas (ex.: envio sem opt-in). |
| `contacts_opt_in_rollout_enabled` | Config server | `org_id` | Flag booleana indicando se o tenant está com o novo fluxo ativo. |

### Métricas derivadas

- **Taxa de falha na importação** = `contacts_import_failed_total / contacts_import_total`.
- **Tempo médio para concluir opt-in** = `avg(consent_event_processing_latency_seconds)` filtrando por `state=confirmed`.
- **Cobertura de rollout** = `count(distinct org_id where contacts_opt_in_rollout_enabled=1)`.

## Dashboards

1. **Rollout multi-tenant (Grafana)**
   - Painel com gráfico de barras de `contacts_opt_in_rollout_enabled` por `org_id`.
   - Séries de tempo para `consent_event_total` e `consent_event_processing_latency_seconds` (p50/p95).
   - Tabela de saúde da importação com `contacts_import_total`, `contacts_import_failed_total` e taxa de falha por tenant.
2. **Importações (DataDog / Grafana)**
   - Drill-down mostrando `contacts_import_retry_queue_size`.
   - Distribuição de `error_code` para as falhas mais frequentes.

## Alertas recomendados

| Alerta | Condição | Severidade | Ação sugerida |
| --- | --- | --- | --- |
| **Falhas na importação de contatos** | `contacts_import_failed_total` > 50 por tenant em janela de 15 min OU taxa de falha > 5% | Alta | Congelar novas importações para o tenant e seguir checklist de correção no runbook. |
| **Fila de reprocessamento crescente** | `contacts_import_retry_queue_size` crescimento sustentado por 3 janelas consecutivas | Média | Escalonar para Dados & Ingestão verificar gargalos e reprocessar jobs manualmente. |
| **Latência elevada no opt-in** | p95 de `consent_event_processing_latency_seconds` > 120s por 10 minutos | Média | Investigar workers de consentimento e checar dependências externas. |
| **Violação de política de consentimento** | `consent_policy_violation_total` > 0 | Crítica | Acionar Privacidade & Compliance, suspender envios automáticos. |

## Logs e traces

- **Ingestão de contatos**: `backend/app/services/contacts/importer.py` emite logs estruturados com `org_id`, `job_id`, `error_code`.
- **Eventos de consentimento**: logs de `opt_in_request_service` incluem `contact_id` e `consent_version`.
- **Tracing distribuído**: habilitar `traceparent` em chamadas do webhook WhatsApp para rastrear fluxo end-to-end.

## KPIs operacionais

- **Disponibilidade do pipeline de importação** ≥ 99% durante a janela comercial.
- **SLA de propagação de opt-in** < 5 minutos para 95% dos eventos.
- **Zero envios sem opt-in válido** durante o rollout (monitorado via `consent_policy_violation_total`).

## Referências

- [Runbook do catálogo de contatos](./RUNBOOK_CONTACTS.md)
- [Plano de implementação do ciclo](../current-cycle/NEXT_IMPLEMENTATION_PLAN.md)
