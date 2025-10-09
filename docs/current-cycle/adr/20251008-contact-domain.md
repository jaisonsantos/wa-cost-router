# ADR 2025-10-08 — Domínio de Contatos e Consentimento

## Contexto

O piloto externo do WA Cost Router exige um catálogo de contatos multi-tenant com versionamento de consentimento e integrações
com CRM. Até então, apenas números telefônicos residiam nos jobs de mensagem, inviabilizando deduplicação, importação em massa
e rastreabilidade LGPD/GDPR. O discovery com squads de Operações, Growth e Privacidade determinou os seguintes requisitos:

- Centralizar contatos por `organization` preservando atributos customizáveis e status do ciclo de vida.
- Registrar opt-ins multicanal com histórico completo (quem concedeu, quando, origem, evidências).
- Segmentar contatos de forma flexível para campanhas e rotas de atendimento.
- Orquestrar importações idempotentes com relatório de erros e monitoramento assíncrono.
- Manter trilha de auditoria de consentimento para consultas de privacidade e sincronização com CRMs.

## Decisão

1. **Entidades principais**
   - `contact`: perfil do titular vinculado à organização, contendo campos básicos (`full_name`, `email`, `phone`), atributos
     flexíveis (`attributes`), metadados de origem e `status` (`active`, `inactive`, `archived`).
   - `contact_channel_opt_in`: versão do consentimento por canal/endereço (`whatsapp`, `sms`, `email`). Controla `status`
     (`granted`, `revoked`, `pending`), `legal_basis`, `source_metadata` e incrementa `version` a cada mudança.
   - `contact_segment`: agrupador lógico com `slug`, `criteria` (JSON) e vínculo 1:1 opcional com `contact_segment_policy`.
   - `contact_segment_membership`: associação versionada (`valid_from`, `valid_to`) entre contatos e segmentos, permitindo trilha
     histórica.
   - `contact_import_job`: job RQ para importação CSV com contagem de linhas, status (`pending` → `validating` → `processing`
     → `completed`/`failed`) e URIs de insumo/relatório.
   - `contact_consent_audit`: auditoria imutável com `channel`, `status`, `agent`, `request_ip`, `evidence_uri` e vínculo opcional
     à versão de opt-in correspondente.

2. **Relacionamentos chave**
   - Todas as entidades herdam `org_id` (`organization.id`) garantindo isolamento por tenant.
   - `contact_channel_opt_in` e `contact_segment_membership` usam FKs `ON DELETE CASCADE` para preservar consistência ao remover
     contatos, enquanto `contact_consent_audit.opt_in_id` utiliza `SET NULL` para manter trilha mesmo após reprocessamentos.
   - `contact_segment_policy.segment_id` é `UNIQUE`, garantindo apenas uma política ativa por segmento.

3. **Requisitos LGPD/GDPR incorporados**
   - Versionamento de consentimento (`version`, `captured_at`, `proof_hash`) com auditoria imutável (`contact_consent_audit`).
   - Campos `legal_basis`, `source_metadata` e `evidence_uri` para comprovar finalidade e origem, alinhando-se ao art. 7º (LGPD) e
     art. 6º (GDPR).
   - Registro de `request_ip`/`agent` para responsabilização e atendimento a solicitações de titulares (art. 18 LGPD / art. 15 GDPR).
   - `contact_import_job` mantém `requested_by` e `error_report_uri` para evidenciar consentimento prévio e cumprir obrigação de
     prestação de contas.
   - Políticas de segmento armazenam limites e exclusões (`opt_out`) para evitar comunicações indevidas, base para "privacy by
     design".

4. **Implementação**
   - Migrations Alembic `007_add_contact_domain`, `008_add_contact_consent_audit` e `009_add_contact_segment_policy` criam tabelas,
     índices (`org_id`, `channel_address`, `recorded_at`) e enums (`contactstatusenum`, `optinstatusenum`, `contactimportstatusenum`).
   - Modelos SQLAlchemy refletem o design com `relationship` bidirecional para uso no repositório/serviços.
   - Schemas Pydantic (`backend/app/schemas/contacts.py`) padronizam payloads de API e previnem vazamento de dados sensíveis.
   - Serviços (`ContactRepository`, `ConsentService`, `ContactSegmentService`, `ContactPreferenceResolver`) encapsulam CRUD,
     versionamento e filtros por canal/segmento.

5. **Integração operacional**
   - Importações CSV são executadas via worker RQ (`contact_import_job`) com validação de cabeçalhos obrigatórios (`full_name`) e
     relatório de inconsistências armazenado no storage temporário.
   - Histórico de consentimento é exposto via API/SPA e utilizado pelo motor de roteamento, bloqueando envios quando não há opt-in
     ativo e disparando fluxo automático de solicitação (`contact_opt_in_request`).
   - Conectores HubSpot/Pipedrive reutilizam o catálogo e sincronizam alterações incrementais com base em `crm_sync` no metadado do
     provedor.

## Consequências

- **Positivas**: garante rastreabilidade LGPD/GDPR ponta a ponta, habilita importação/segmentação multi-tenant e integrações CRM
  sem duplicar lógica de consentimento. Facilita expansão para novos canais e políticas de retenção.
- **Negativas**: aumento da complexidade operacional (migrations encadeadas, monitoramento de jobs RQ, storage de evidências) e
  necessidade de sanitização rigorosa nos logs. Exige atualização contínua dos playbooks e monitoramento de índices.
- **Próximos passos**: completar hardening do webhook multi-tenant, finalizar circuit breaker multicanal e expandir cobertura de
  integrações CRM conforme roadmap.
