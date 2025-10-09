# ADR 2025-10 — Modelagem de contatos, consentimento e importações

- **Data:** 2025-10-08
- **Status:** Aceito
- **Contexto:**
  - O ciclo atual prioriza a consolidação do catálogo de contatos multi-tenant e da jornada de opt-in/opt-out. Precisávamos formalizar as entidades persistidas para garantir rastreabilidade LGPD/GDPR, deduplicação consistente por organização e suporte a importações auditáveis.
  - Os cards P0 do backlog (`UC-01` e `UC-02`) dependem de um modelo relacional que cubra contatos, histórico de consentimento, segmentação dinâmica e jobs de importação com trilha de auditoria.

## Decisão

1. **Entidades principais**
   - `contact`: representa o perfil base de uma pessoa por organização (`org_id`). Campos principais incluem identificadores externos, dados de contato (e-mail, telefone) e `attributes` flexíveis. Mantemos `status` para habilitar arquivamento sem exclusão física.
   - `contact_channel_opt_in`: versiona os consentimentos por canal/endereço. Inclui `status` (granted/revoked/pending), `version`, `captured_at`, origem (`source`) e metadados de evidência. Possui chave composta (`contact_id`, `channel`, `channel_address`, `version`).
   - `contact_segment`: armazena segmentos de marketing/operacionais com `slug`, `criteria` e `source`. Relaciona-se com `contact` via `contact_segment_membership` (já existente) para permitir histórico de associações.
   - `contact_import_job`: representa importações CSV (ingestão em lote) com status, contagem de linhas, referências a relatórios de erro (`error_report_uri`) e timestamps (`started_at`, `completed_at`).
   - `contact_consent_audit`: trilha de auditoria independente que captura cada ação de consentimento ou revogação com `agent`, `request_ip`, `evidence_uri`, `proof_hash` e payload contextual.

2. **Relacionamentos com `organization`**
   - Todas as entidades usam `org_id` com `ForeignKey('organization.id', ondelete='CASCADE')` para garantir isolamento por tenant.
   - `Organization.contacts` e `Organization.contact_segments` expõem relacionamentos bidirecionais, permitindo eager loading controlado no repositório.
   - `Contact` mantém relacionamentos com `ContactChannelOptIn`, `ContactSegmentMembership` e `ContactConsentAudit` com `cascade='all, delete-orphan'` para evitar lixo lógico.

3. **Requisitos LGPD/GDPR**
   - **Minimização de dados:** `attributes`, `source_metadata` e `proof_hash` são colunas JSON opcionais para armazenar dados necessários, evitando campos rígidos que incentivem coleta excessiva.
   - **Auditabilidade:** toda operação de opt-in/out dispara inserção em `contact_consent_audit`, registrando `agent`, `source` e carimbo temporal (`recorded_at`). Isso atende ao Art. 18 da LGPD e ao princípio de accountability do GDPR.
   - **Direito de revogação:** versões sucessivas em `contact_channel_opt_in` preservam histórico, mas o serviço garante que apenas a versão ativa (`status = granted`) seja utilizada em envios.
   - **Retenção e exclusão:** `contact.status` permite "soft delete" controlado, enquanto `ondelete='CASCADE'` elimina registros dependentes durante solicitações de esquecimento.
   - **Importações idempotentes:** `contact_import_job` rastreia progresso e armazena relatórios de erro para comprovar o tratamento de dados incorretos ou rejeitados.
   - **Consentimento inequívoco:** `legal_basis`, `evidence_uri` e `proof_hash` nos opt-ins armazenam o fundamento jurídico e a evidência da aceitação.

4. **Operacionalização**
   - Migrações Alembic criam índices por `org_id` e `channel_address` para permitir filtros rápidos por consentimento.
   - Repositórios e serviços (já implementados) aplicam validação idempotente e sanitização, reforçando as restrições de compliance.
   - A documentação operacional (`docs/operations/RUNBOOK_CONTACTS.md`) deve referenciar esta decisão ao descrever processos de exportação/remoção.

## Consequências

- O modelo padronizado facilita sincronização com CRMs (HubSpot, Pipedrive) e garante que dados de consentimento sejam transportáveis.
- Há custo adicional de armazenamento ao manter versões históricas e auditoria, mas é compensado pela conformidade.
- Mudanças futuras no catálogo devem avaliar impacto nesta ADR e, se divergirem, produzir uma nova decisão ou apêndice.
