[Docs](../current-cycle/README.md) › [Segurança](./SECURITY.md) › Privacidade
# Controles de Privacidade — Catálogo de Contatos

Este documento consolida controles preventivos e detectivos necessários para operar o catálogo multi-tenant de contatos de forma alinhada à LGPD.

## Checklist — Importação e Consentimento

- [ ] Dados & Ingestão valida a fonte com `make contacts-validate` e registra evidência no ticket da solicitação.
- [ ] Operações confirma que o `org_id` possui consentimento base cadastrado e política de privacidade publicada.
- [ ] Privacidade revisa o modelo de consentimento anexado à importação (opt-in explícito, idioma e finalidade).
- [ ] ADR [`20251008-contact-domain`](../current-cycle/adr/20251008-contact-domain.md) referenciado no ticket para comprovar salvaguardas LGPD/GDPR.
- [ ] Logs estruturados (`consent_event_id`) ativados e retidos por 24 meses no data lake seguro.
- [ ] Métricas `contacts_import_processed_total` e `contacts_consent_conflicts_total` monitoradas com alertas ≥ P1.

## Checklist — Proteções em Produção

- [ ] Criptografia em repouso habilitada no bucket `wa-cost-router-imports` com chaves gerenciadas pelo time de Segurança.
- [ ] Acesso ao bucket restrito via IAM a perfis `contacts-importer` (Dados & Ingestão) e `privacy-reviewer` (Privacidade).
- [ ] Tokens de API administrativa rotacionados a cada 90 dias e armazenados no cofre central (`vault/wa-router/contacts`).
- [ ] Feature flag `privacy_lock` aplicada para contatos em análise ou disputa legal.
- [ ] Auditoria semanal da tabela `audit_log` garantindo que eventos de importação possuem `actor_org_id` e `trace_id` preenchidos.
- [ ] Revisar semanalmente o histórico de consentimento (`contact_consent_audit`) via `GET /contacts/{id}/consents/history` garantindo presença de `agent`, `request_ip` e `evidence_uri`.
- [ ] Integradores CRM (HubSpot/Pipedrive) operando com escopos mínimos e tokens expiram automaticamente após 90 dias (`crm_sync` → `token_expires_at`).

## Checklist — Retenção e Exclusão

- [ ] Job `contacts_retention_audit` executa semanalmente e publica relatório para Operações.
- [ ] Pendências de retenção > 48h escaladas automaticamente para Privacidade & Compliance.
- [ ] Exclusões sob demanda registradas em ticket `LGPD-DEL-*` com aprovação explícita de Privacidade antes da execução.
- [ ] Scripts `delete_contact.py` e `rollback_contacts_import.py` executados a partir de ambiente controlado (bastion) com MFA.
- [ ] Evidências de destruição armazenadas no cofre de compliance por 5 anos.

## Checklist — Respostas a Titulares

- [ ] Canal oficial para requisições LGPD divulgado e monitorado (formulário + e-mail dedicado).
- [ ] SLA monitorado no dashboard de compliance com alertas para prazos a vencer em 48h.
- [ ] Relatórios gerados para titulares anonimiza metadados sensíveis (IDs internos, tokens de sessão).
- [ ] Comunicação de retorno aprovada por Privacidade & Compliance antes do envio.
- [ ] Encerramento do ticket inclui verificação de que consentimentos relacionados foram atualizados ou revogados.
