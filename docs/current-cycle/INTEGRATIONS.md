# Integrações Externas (Ciclo Atual)

Este documento consolida o estado das integrações externas durante o ciclo corrente, com foco
no conector CRM priorizado (HubSpot) e na sincronização incremental do catálogo de contatos.

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
   - Agendar `CRMIncrementalSyncService.run_polling_cycle` usando `CRM_POLLING_INTERVAL_SECONDS`
     como intervalo base para fallback.

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
origem do último lote processado.

## Variáveis de Ambiente

| Variável | Descrição |
| --- | --- |
| `CRM_WEBHOOK_SECRET` | Segredo compartilhado para validar eventos outbound do CRM. |
| `CRM_POLLING_INTERVAL_SECONDS` | Intervalo padrão (em segundos) para rodar o fallback de polling. |
| `CRM_MAX_PAGE_SIZE` | Limite máximo de registros por página durante polling incremental. |

> As variáveis acima foram adicionadas a `.env.example` e são carregadas em `app.core.config`.

## Próximos Passos

- Implementar endpoints públicos para acionar `CRMIncrementalSyncService` e expor métricas de
  sincronização por tenant.
- Ampliar o registry (`CRMProviderRegistry`) com outros CRMs priorizados (Salesforce, RD Station).
- Instrumentar monitoramento para reconciliar divergências entre webhooks e polling.

