# Integrações Externas (Ciclo Atual)

Este documento consolida o estado das integrações externas durante o ciclo corrente, com foco
nos conectores CRM priorizados (HubSpot e Pipedrive) e na sincronização incremental do catálogo
de contatos.

## CRM HubSpot

### Visão Geral

- O módulo `app/services/crm` define abstrações padronizadas para provedores CRM e
  centraliza o fluxo de sincronização incremental.
- A sincronização combina webhooks outbound (eventos em tempo real) e um fallback de polling
  agendado que garante consistência quando eventos são perdidos.
- O mapeamento de campos suporta atributos customizados por tenant através de `Provider.meta`.

### Passo a Passo de Configuração

1. **Registrar o provedor CRM**
   - Criar (ou atualizar) um registro em `provider` com `type = "crm"` e `meta.slug = "hubspot"`.
   - Opcionalmente declarar `meta.field_mapping` seguindo o formato abaixo.
2. **Cadastrar credenciais**
   - Utilizar `/providers/credentials` para gravar um payload com `access_token` (private app
     token) e, opcionalmente, `base_url`, `app_id` e `timeout` em segundos.
3. **Configurar webhooks outbound**
   - Invocar `HubSpotProvider.configure_webhook` com a URL pública do callback. O serviço usa
     `CRM_WEBHOOK_SECRET` como segredo para assinatura.
4. **Habilitar sincronização incremental**
   - Chamar `CRMIncrementalSyncService.handle_webhook_event` a partir do endpoint inbound para
     processar notificações.
   - Utilizar o script `python backend/scripts/run_crm_sync.py --provider hubspot --org-id <uuid>`
     para execuções manuais (suporte a `--since` e `--page-size`).
   - Automatizar fallback com `enqueue_polling_cycle` (`app/services/crm/worker.py`), que respeita
     `CRM_POLLING_INTERVAL_SECONDS` antes de publicar jobs na fila `crm_sync` consumida pelo worker
     RQ (`backend/worker.py`).

### Mapeamento de Campos

O dicionário `Provider.meta.field_mapping` aceita duas chaves:

```json
{
  "core": {
    "external_id": "id",
    "email": "properties.email",
    "phone": "properties.phone",
    "first_name": "properties.firstname",
    "last_name": "properties.lastname"
  },
  "custom_attributes": {
    "lifecycle_stage": "properties.lifecyclestage",
    "whatsapp_opt_in": "properties.wa_opt_in"
  }
}
```

- Campos ausentes herdam o mapeamento padrão do provedor.
- Atributos customizados são mesclados em `Contact.attributes`, preservando valores existentes.

### Estrutura do Estado de Sincronização

O módulo persiste o progresso incremental em `Provider.meta.crm_sync`:

```json
{
  "cursor": "<token de paginação>",
  "last_change_at": "2025-10-09T12:34:56+00:00",
  "last_synced_at": "2025-10-09T12:35:01+00:00",
  "last_origin": "polling"
}
```

Esse estado é usado para retomar polling a partir do último cursor válido e para auditar a
origem do último lote processado. O script CLI e o worker retornam/resgatam `SyncResult` já
serializado com essas informações (`processed_contacts`, `has_more`, `last_change_at`).

### Monitoramento e Operação

- Métricas Prometheus `crm_sync_processed_total` e `crm_sync_failures_total` expostas em
  `/admin/metrics` (labels `provider_slug`, `origin`).
- Logs do enfileiramento (`crm_sync_enqueued`, `crm_sync_enqueue_skipped`) ajudam a verificar
  se o intervalo mínimo está sendo respeitado.
- Para validação manual, o script CLI imprime o `SyncResult` em JSON.

## CRM Pipedrive (beta)

### Visão Geral

- Autenticação via token de API e domínio da empresa (`company_domain`).
- Apenas polling incremental está habilitado nesta fase; webhooks permanecem desativados.
- O conector normaliza `primary_email`/`primary_phone` a partir das listas retornadas pelo
  endpoint `/persons`.

### Configuração

1. **Registrar o provedor**
   - `Provider.type = "crm"`, `meta.slug = "pipedrive"`.
2. **Cadastrar credenciais**
   - Payload mínimo: `{ "api_token": "...", "company_domain": "<tenant>.pipedrive.com" }`.
   - Campos opcionais: `timeout`, `base_url` (override do template) e `max_page_size` (<=
     `CRM_PIPEDRIVE_MAX_PAGE_SIZE`).
3. **Polling incremental**
   - Utilizar `python backend/scripts/run_crm_sync.py --provider pipedrive --org-id <uuid>`.
   - `CRMIncrementalSyncService.run_polling_cycle` ignora registros cujo `update_time` seja
     anterior ou igual ao `last_change_at` persistido.

### Limitações

- Sem suporte a webhooks; recomenda-se janelas de polling que mantenham a coleção abaixo de
  `CRM_PIPEDRIVE_MAX_PAGE_SIZE` por execução.
- Campos customizados seguem o mesmo mecanismo de `Provider.meta.field_mapping`.
- Eventos com `marketing_status = null` devem ser descartados na aplicação de regras de opt-in.

## Variáveis de Ambiente

| Variável | Descrição |
| --- | --- |
| `CRM_WEBHOOK_SECRET` | Segredo compartilhado para validar eventos outbound do CRM. |
| `CRM_POLLING_INTERVAL_SECONDS` | Intervalo padrão (em segundos) para rodar o fallback de polling. |
| `CRM_MAX_PAGE_SIZE` | Limite máximo de registros por página durante polling incremental. |
| `CRM_PIPEDRIVE_BASE_URL_TEMPLATE` | Template para montar a URL base do tenant Pipedrive. |
| `CRM_PIPEDRIVE_MAX_PAGE_SIZE` | Valor máximo aceito pelo conector Pipedrive (default 500). |

> As variáveis acima foram adicionadas a `.env.example` e são carregadas em `app.core.config`.

## Próximos Passos

- Implementar endpoints públicos para acionar `CRMIncrementalSyncService` e expor métricas de
  sincronização por tenant.
- Ampliar o registry (`CRMProviderRegistry`) com outros CRMs priorizados (Salesforce, RD Station).
- Revisitar suporte a webhooks Pipedrive assim que a API oficial estiver liberada.
- Consolidar dashboards que correlacionem métricas de sucesso/falha (Prometheus) com eventos de
  webhook para detectar divergências entre webhooks e polling.

