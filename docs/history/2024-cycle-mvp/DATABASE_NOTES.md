# Notas de Banco de Dados — Ciclo 2024 (MVP)

## 2024-10 — Catálogo de Contatos Multi-tenant

### Resumo das Tabelas
- **`contact`**: catálogo principal de contatos por organização (`org_id`) com atributos PII opcionais, estado (`status`), metadados livres (`attributes`) e trilha de auditoria (`source`, `source_metadata`, `proof_hash`, `created_at`, `updated_at`). Índices em `org_id`, `external_id`, `email` e `phone` aceleram buscas determinísticas e deduplicação.
- **`contact_channel_opt_in`**: versiona consentimentos por canal/endereço. Mantém referência explícita ao contato, base legal (`legal_basis`) e evidencia de captura (`evidence_uri`, `proof_hash`). Índices em `org_id`, `contact_id` e `channel_address` garantem consultas rápidas por tenant e canal.
- **`contact_segment`**: define segmentos reutilizáveis com `slug` único por organização e critérios estruturados (`criteria`). Inclui as mesmas colunas de auditoria dos contatos.
- **`contact_segment_membership`**: liga contatos a segmentos com validade temporal (`valid_from`, `valid_to`) e origem de inclusão (`membership_origin`). É versionada por (`contact_id`, `segment_id`, `valid_from`).
- **`contact_import_job`**: registra execuções de importação, volumes processados e links de relatórios de erro. Usa enumeração de status (`pending`, `validating`, `processing`, `completed`, `failed`) e índices em (`org_id`, `status`).

Todas as tabelas utilizam chaves primárias UUID e `org_id` com `ON DELETE CASCADE` para preservar isolamento multi-tenant e simplificar limpeza.

### Auditoria e Prova de Consentimento
- `source` e `source_metadata` permitem identificar a origem operacional (seed, importação CSV, webhook, etc.).
- `proof_hash` armazena o hash criptográfico (SHA-256) do payload de consentimento ou do arquivo importado, seguindo orientação do time de Compliance.
- `created_at`/`updated_at` são `TIMESTAMP WITH TIME ZONE` com `server_default=now()` para garantir trilha temporal mesmo sem camada de aplicação.
- `captured_at` em `contact_channel_opt_in` registra o momento de aceite do titular.

### Seeds Determinísticos
- IDs fixos foram definidos para organização, usuário administrador, contato demo, segmento piloto e job de importação.
- Hashes SHA-256 são calculados a partir de strings estáticas (`contact:dona-dana:seed:v1`, etc.) para permitir verificação cruzada em auditorias.
- Os timestamps usam `2024-01-15T00:00:00Z` como marco de referência do piloto, mantendo consistência entre ambientes.
- Executar `docker compose run backend python scripts/seed.py` continuará idempotente, garantindo que registros já existentes sejam reaproveitados.

### Migração
- Revisão Alembic `007_add_contact_domain` adiciona enumerações e tabelas com os índices descritos acima.
- O downgrade remove as estruturas e tipos enumerados (`contactstatusenum`, `optinstatusenum`, `contactimportstatusenum`).
- Dependências: nenhuma migração adicional necessária além da `006_relax_wa_verify_token_scope`.

### Próximos Passos
- Implementar API pública para ingestão de contatos referenciando as novas entidades.
- Conectar jobs de importação ao pipeline de sanitização e relatórios de erro (pendente integração com storage S3 gerenciado).
- Validar com Compliance o ciclo de vida do `proof_hash` e política de retenção nas tabelas de opt-in.
