[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md) › Integrações CRM
# INTEGRATIONS.md — HubSpot & Pipedrive

Este guia descreve como configurar as integrações CRM suportadas no piloto (HubSpot e Pipedrive) utilizando o catálogo de contatos multi-tenant.

## 1. Pré-requisitos

- Contatos importados via `/contacts/imports` com opt-ins válidos (`status=granted`).
- Provedores CRM cadastrados (`type="crm"`) em `/providers` com `meta.slug` igual a `hubspot` ou `pipedrive`.
- Worker RQ ativo (`python backend/worker.py`) para processar filas `default` e `crm_sync`.
- Variáveis de ambiente:
  - `CRM_MAX_PAGE_SIZE` (default 100).
  - `CRM_POLLING_INTERVAL_SECONDS` (janela mínima entre enfileiramentos de polling).
  - `CRM_WEBHOOK_SECRET` (utilizada para validação de webhooks HubSpot; no sandbox local utilizamos `demo-crm-webhook-secret`, alinhado com a coleção Postman).
  - `CRM_PIPEDRIVE_BASE_URL_TEMPLATE` (formato padrão para montar a URL do tenant Pipedrive).
  - `CRM_PIPEDRIVE_MAX_PAGE_SIZE` (limite superior aceito pelo conector Pipedrive).

## 2. HubSpot

> **Nota:** quando `SANDBOX_PROVIDERS=true`, o ambiente cria automaticamente um provedor "HubSpot Sandbox" com credenciais fake e contatos de demonstração. O seed (`backend/scripts/seed.py`) cobre a organização demo e, para qualquer nova organização criada via `/auth/register`, o primeiro webhook ou ciclo de polling em `/integrations/crm/hubspot/*` auto provisiona o provedor/credenciais antes de aplicar as alterações — garantindo que os fluxos da coleção Postman/Newman funcionem sem passos manuais.

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
   - O endpoint FastAPI `POST /integrations/crm/hubspot/webhook` agora valida `X-HubSpot-Signature` calculando `hex(hmac_sha256(secret, raw_body))` com `CRM_WEBHOOK_SECRET`. Requisições rejeitadas retornam `401` e são logadas com `provider_slug`/`org_id`.
   - Eventos válidos respondem com o resumo `SyncResult` (`processed_contacts`, `last_change_at`, `origin`, etc.) utilizado também na telemetria.
3. **Sincronização incremental**
   - Webhooks ingerem eventos imediatos (`origin=webhook`).
   - Polling pode ser disparado manualmente via script `python backend/scripts/run_crm_sync.py` (suporte a `--provider`, `--org-id`, `--since`, `--page-size`) ou via API `POST /integrations/crm/hubspot/poll`.
   - Enfileiramento automático deve usar `enqueue_polling_cycle` em `app/services/crm/worker.py`, que respeita `CRM_POLLING_INTERVAL_SECONDS` e publica jobs na fila `crm_sync`.
   - Estado persistido em `Provider.meta.crm_sync` (`cursor`, `last_change_at`).
4. **Monitoramento**
   - Métricas `crm_sync_processed_total` e `crm_sync_failures_total` (labels `provider_slug`, `origin`) expostas em `/admin/metrics`.
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
   - Pipedrive não envia webhooks na fase beta. Agendar `python backend/scripts/run_crm_sync.py --provider pipedrive --org-id <uuid>` ou usar `enqueue_polling_cycle` com intervalo >= `CRM_POLLING_INTERVAL_SECONDS`.
   - O serviço reconcilia contatos por `external_id`/`email` e atualiza opt-ins quando `marketing_status` mudar.
3. **Limitações conhecidas**
   - Campos customizados devem ser configurados manualmente (`Provider.meta.field_mapping.custom_attributes`).
   - Eventos com `marketing_status=null` são ignorados para evitar opt-outs indevidos.
   - Como o conector depende de polling, o atraso mínimo entre execuções deve respeitar `CRM_PIPEDRIVE_MAX_PAGE_SIZE` para evitar lacunas em tenants com alto volume.

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
