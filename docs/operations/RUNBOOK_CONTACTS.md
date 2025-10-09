[Docs](../current-cycle/README.md) › [Operações](./OPERATIONS.md) › Contatos
# Runbook — Catálogo de Contatos Multi-tenant

Este runbook descreve como operar a importação de contatos, executar rollback seguro e responder solicitações relacionadas à LGPD no catálogo multi-tenant. Ele deve ser atualizado sempre que o pipeline ou os conectores mudarem.

## Visão geral

- **Escopo**: contatos com consentimento auditável, armazenados por `org_id` e sincronizados com provedores WhatsApp/CRM.
- **Times responsáveis**:
  - **Dados & Ingestão**: manter pipelines de importação e reconciliação.
  - **Operações**: monitorar execuções, aprovar rollbacks e orquestrar exclusões sob demanda.
  - **Privacidade & Compliance**: validar respostas LGPD e revisar políticas de retenção.

## Procedimento de importação controlada

1. **Pré-checagens** (Dados & Ingestão)
   - ✅ Confirmar janela de manutenção e volume estimado com o time solicitante.
   - ✅ Validar arquivo/fonte via `make contacts-validate` (estrutura, encoding UTF-8, cabeçalhos obrigatórios: `external_id`, `phone`, `consent_state`, `org_id`).
   - ✅ Garantir que não existem jobs `contacts_import` ativos para o mesmo `org_id` via `GET /admin/jobs?type=contacts_import&status=running`.
2. **Execução** (Dados & Ingestão)
   - Subir o arquivo para o bucket S3 interno (`s3://wa-cost-router-imports/<org_id>/<timestamp>.csv`).
   - Criar job via API administrativa: `POST /admin/contacts/import` com payload `{ "org_id": "...", "source_uri": "s3://...", "dry_run": false }`.
   - Monitorar logs do worker (`make logs worker`) e acompanhar métricas `contacts_import_processed_total`.
3. **Validação pós-importação** (Operações)
   - Revisar relatório gerado em `s3://wa-cost-router-imports/<org_id>/<timestamp>-report.json`.
   - Executar `GET /admin/contacts/stats?org_id=...` confirmando contagens e taxa de deduplicação.
   - Informar time solicitante sobre conclusão e próximos passos (opt-in flows ou integrações CRM).

## Rollback de importação

> Aplicável apenas até 24 h após a importação ou enquanto o consentimento não for propagado a sistemas externos.

1. **Avaliar impacto** (Operações + Privacidade & Compliance)
   - Verificar se houve notificações enviadas a partir dos contatos importados (consultar `message_log` por `org_id`).
   - Mapear dependências afetadas (CRM, automações ativas, opt-ins).
2. **Executar rollback** (Dados & Ingestão)
   - Criar snapshot `SELECT * FROM contacts WHERE org_id = ...` para evidência.
   - Rodar script administrativo `python backend/scripts/rollback_contacts_import.py --org-id ... --batch-id ...`.
   - Confirmar remoção com `GET /admin/contacts/stats` e atualização de métricas.
3. **Comunicar stakeholders** (Operações)
   - Notificar squads impactadas e registrar incidente em `docs/operations/incidents/<ano>/`.
   - Atualizar o backlog de follow-ups (deduplicação, regras de validação, etc.).

## Atendendo solicitações LGPD

| Tipo de solicitação | SLA | Responsável primário | Passos-chave |
|---------------------|-----|----------------------|--------------|
| Confirmação de tratamento | 7 dias corridos | Privacidade & Compliance | Validar consentimento ativo, gerar relatório de tratamento por `org_id` e enviar resposta ao requisitante. |
| Correção de dados | 5 dias úteis | Dados & Ingestão | Executar `PATCH /admin/contacts/{id}` com campos ajustados, registrar justificativa e evidência. |
| Portabilidade | 15 dias corridos | Dados & Ingestão + Operações | Exportar CSV filtrado, anonimizar metadados sensíveis e enviar via canal seguro. |
| Exclusão total (direito ao esquecimento) | 10 dias corridos | Operações (execução) + Privacidade (auditoria) | Seguir processo de exclusão sob demanda descrito abaixo, armazenando comprovantes. |

- Todas as solicitações devem ser registradas no sistema de tickets (`LGPD-###`) e vinculadas ao `org_id` e contato.
- O time de Privacidade aprova ou rejeita a solicitação antes da execução.
- Logs e relatórios devem ser arquivados por 5 anos em repositório controlado de compliance.

## Retenção e exclusão sob demanda

- **Retenção padrão**: contatos inativos (sem opt-in válido há 18 meses) são marcados semanalmente pelo job `contacts_retention_audit`. Dados são pseudonimizados após 30 dias e excluídos definitivamente após 180 dias.
- **Exclusão sob demanda (LGPD / contractual)**:
  1. Privacidade cria ticket `LGPD-DEL-<org_id>-<id>` e valida legitimidade da solicitação.
  2. Operações agenda a janela e bloqueia novos envios para o contato (`POST /admin/contacts/block`).
  3. Dados & Ingestão executa `python backend/scripts/delete_contact.py --contact-id ... --hard-delete` garantindo remoção em lote do catálogo e da fila de opt-ins.
  4. Operações dispara `DELETE /admin/consents/{contact_id}` para revogar registros associados.
  5. Privacidade revisa logs (`audit_log`) e anexa evidência de destruição antes de encerrar o ticket.
- **Responsabilidades cruzadas**:
  - Dados & Ingestão garante que jobs automáticos respeitam flags `retention_hold` e `privacy_lock` aplicadas por Privacidade.
  - Operações monitora métricas `contacts_retention_pending_total` e escalona se pendências > 48h.
  - Privacidade revisa políticas trimestralmente e atualiza o runbook conforme mudanças legais.

## Checklist rápido

- [ ] Fonte validada (`make contacts-validate`) e janela de importação confirmada.
- [ ] Job de importação criado e monitorado com métricas atualizadas.
- [ ] Relatório pós-importação revisado e stakeholders notificados.
- [ ] Rotas de rollback documentadas com snapshot antes/depois.
- [ ] Solicitações LGPD registradas, auditadas e respondidas dentro do SLA.
- [ ] Retenção automática e exclusões sob demanda auditadas pelo time de Privacidade.
