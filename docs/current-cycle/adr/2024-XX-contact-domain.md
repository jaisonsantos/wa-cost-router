# ADR 2024-XX — Domínio de Contatos Multi-tenant

## Contexto
A evolução do catálogo multi-tenant de contatos requer uma padronização das entidades centrais, dos fluxos de consentimento (opt-in/out) e das integrações com provedores externos. A definição antecipada desses elementos é necessária para desbloquear as frentes priorizadas no ciclo atual e reduzir riscos de conformidade com a LGPD.

## Visão Geral da Solução
- Consolidar um domínio de contatos único por organização, com isolamento lógico por `org_id` e relacionamento explícito com segmentos dinâmicos.
- Normalizar consentimentos (opt-ins) por canal, permitindo múltiplas origens (WhatsApp, SMS, e-mail) e versionamento dos estados de consentimento.
- Expor contratos estáveis para ingestão (importações CSV/API), enriquecimento incremental e sincronização bidirecional com CRMs externos.
- Garantir que todo processamento persista metadados de auditoria (`created_by`, `created_at`, `source`, `legal_basis`).

## Entidades e Relacionamentos
- **Contact** (`id`, `org_id`, atributos PII, `status`): identifica de forma única cada pessoa no tenant.
  - **Decisão**: chave primária `id` em formato UUID v7 para suportar ordenação temporal e distribuição multi-região.
- **ContactChannel** (`contact_id`, `channel`, `address`, `is_primary`): normaliza diferentes meios de contato evitando duplicidade de colunas.
- **ContactOptIn** (`contact_channel_id`, `channel`, `status`, `version`, `source`, `captured_at`, `legal_basis`, `evidence_uri`): registra consentimentos específicos por canal.
  - **Decisão**: opt-ins são normalizados por canal e amarrados à entidade `ContactChannel`, permitindo coexistência de múltiplos estados por canal (ex.: WhatsApp permitido, SMS negado).
- **Segment** (`id`, `org_id`, `name`, critérios dinâmicos): representa agrupamentos reutilizáveis.
- **ContactSegment** (`contact_id`, `segment_id`, `membership_origin`, `valid_from`, `valid_to`): relaciona contatos aos segmentos.
  - **Decisão**: contatos pertencem a organizações via `org_id` e relacionam-se a segmentos por meio da tabela de junção `ContactSegment`, garantindo rastreabilidade multi-tenant.

## Integrações Planejadas
- **Ingestão externa**: endpoints REST e jobs de importação que aceitam arquivos CSV pré-validados, com deduplicação por `org_id` + identificadores preferenciais (`email`, `wa_msisdn`).
- **Provedores WhatsApp Business**: sincronização de opt-ins via webhooks autenticados, armazenando evidências fornecidas pelos provedores.
- **CRMs prioritários**: conectores pull/push que convertem opt-ins normalizados em campos específicos de cada CRM (Salesforce, HubSpot), mantendo correspondência por UUID.
- **Serviço de custos**: reutilização do `RoutingEngine` para aplicar políticas de envio baseadas em segmentos e consentimentos ativos.

## Compliance e LGPD
- Minimização de dados: armazenar apenas atributos necessários por caso de uso, com mascaramento em logs e sanitação automática de payloads sensíveis.
- Governança de consentimento: versionamento obrigatório de `ContactOptIn` com retenção de evidências e possibilidade de auditorias por `org_id`.
- Direitos dos titulares: endpoints para consulta, retificação e exclusão que respeitam SLA de atendimento e notificam integrações conectadas.
- Base legal: registro explícito de `legal_basis` e `source` em cada opt-in, acompanhado de `evidence_uri` quando aplicável.
- Retenção e descarte: políticas configuráveis por organização, com jobs agendados para anonimização/eliminação conforme prazos acordados.

## Aprovação Necessária
Nenhum desenvolvimento deve iniciar antes da coleta formal de aprovação das seguintes áreas:
- **Produto**: validação de alcance funcional, roadmap de integrações e impacto em segmentos.
- **Engenharia**: revisão do desenho de entidades, performance esperada e implicações operacionais (migrations, seeds, limites de throughput).
- **Jurídico/Compliance**: confirmação de aderência à LGPD, processos de consentimento e requisitos de retenção/prova.

## Status
- **Proposta** — aguardando validação cruzada entre Produto, Engenharia e Jurídico.

## Consequências
- Adoção de UUID v7 como padrão reduz colisões e facilita particionamento, mas exige suporte nativo nas migrations e nas integrações com CRMs.
- Normalização de opt-ins aumenta a granularidade de consentimento, demandando ajustes nas APIs e na UI para seleção por canal.
- O relacionamento explícito com segmentos garante alinhamento com campanhas e roteamento, porém requer governança adicional para evitar deriva de critérios.
