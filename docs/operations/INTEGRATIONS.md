[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md) › Integrações CRM
# INTEGRATIONS.md — HubSpot & Pipedrive

Este guia descreve como configurar as integrações CRM suportadas no piloto (HubSpot e Pipedrive) utilizando o catálogo de contatos multi-tenant.

## 1. Pré-requisitos

- Contatos importados via `/contacts/imports` com opt-ins válidos (`status=granted`).
- Provedores CRM cadastrados (`type="crm"`) em `/providers` com `meta.slug` igual a `hubspot` ou `pipedrive`.
- Worker RQ ativo (`python backend/worker.py`) para processar filas `default` e `crm_sync`.
- Variáveis de ambiente:
  - `CRM_MAX_PAGE_SIZE` (default 100).
  - `CRM_SYNC_INTERVAL_SECONDS` (janela de polling para fallback).
  - `CRM_WEBHOOK_SECRET` (utilizada para validação de webhooks HubSpot).

## 2. HubSpot

1. **Credenciais**
   - Gerar token de Private App (`crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.schemas.contacts.read`).
   - `POST /providers/{provider_id}/credentials` com payload:
     ```json
     {
       "provider_id": "<uuid>",
       "credentials": {
         "access_token": "<token>",
         "base_url": "https://api.hubapi.com",
         "app_id": "<opcional>"
       }
     }
     ```
2. **Webhooks**
   - Configurar callback via `HubSpotProvider.configure_webhook` (script `python backend/scripts/configure_hubspot_webhook.py`).
   - O endpoint FastAPI deve aceitar `POST /integrations/crm/hubspot/webhook` com assinatura HMAC usando `CRM_WEBHOOK_SECRET`.
3. **Sincronização incremental**
   - Webhooks ingerem eventos imediatos (`origin=webhook`).
   - Polling é acionado pelo comando `python backend/scripts/run_crm_sync.py --provider hubspot --org-id <uuid>` (ou scheduler).
   - Estado persistido em `Provider.meta.crm_sync` (`cursor`, `last_change_at`).
4. **Monitoramento**
   - Métricas `crm_sync_processed_total`, `crm_sync_failures_total` (labels `provider_slug`, `origin`).
   - Logs estruturados incluem `crm_change_id`, `external_id`, `opt_in_status` resultante.

## 3. Pipedrive (beta)

1. **Credenciais**
   - Criar token de API Pipedrive com escopos `deals:read`, `persons:read`, `persons:write`.
   - Payload de credenciais:
     ```json
     {
       "provider_id": "<uuid>",
       "credentials": {
         "api_token": "<token>",
         "company_domain": "<slug>.pipedrive.com"
       }
     }
     ```
2. **Polling**
   - Pipedrive não envia webhooks na fase beta. Agendar `python backend/scripts/run_crm_sync.py --provider pipedrive --org-id <uuid>` a cada 15 minutos.
   - O serviço reconcilia contatos por `external_id`/`email` e atualiza opt-ins quando `marketing_status` mudar.
3. **Limitações conhecidas**
   - Campos customizados devem ser configurados manualmente (`Provider.meta.field_mapping.custom_attributes`).
   - Eventos com `marketing_status=null` são ignorados para evitar opt-outs indevidos.

## 4. Troubleshooting

| Sintoma | Ação |
| --- | --- |
| `ProviderNotConfiguredError` ao rodar o sync | Verificar se o provedor `type="crm"` está ativo e `meta.slug` corresponde ao registro na `CRMProviderRegistry`. |
| `401 Unauthorized` nas chamadas HubSpot | Validar token e permissões do Private App; tokens expirados devem ser rotacionados manualmente. |
| Eventos duplicados no catálogo | Checar `contact_consent_audit` e `ContactChannelOptIn.version`; as operações são idempotentes via `change_id`. |
| Webhook HubSpot rejeitado (401) | Conferir assinatura HMAC e `CRM_WEBHOOK_SECRET`; revisar logs do worker para detalhes. |

## 5. Referências

- Serviços CRM: [`backend/app/services/crm/`](../../backend/app/services/crm/)
- Repositório de contatos: [`backend/app/services/contacts/repository.py`](../../backend/app/services/contacts/repository.py)
- Testes: [`backend/tests/services/test_contacts_repository.py`](../../backend/tests/services/test_contacts_repository.py), [`backend/tests/services/test_consent_service.py`](../../backend/tests/services/test_consent_service.py)
- Postman: pasta **Contacts** na coleção `docs/postman/wa-cost-router.postman_collection.json`
