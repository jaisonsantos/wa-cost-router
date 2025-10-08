# USE_CASE_GAP — Lacunas para Piloto Multicanal

## Sumário executivo
O discovery com as equipes de atendimento e growth apontou que o MVP atual atende apenas ao envio de mensagens outbound no WhatsApp. Os fluxos reais dos clientes dependem de um catálogo de contatos persistente, histórico de atendimentos multicanal e sincronização bidirecional com CRMs já consolidados. Além disso, os parceiros esperam uma experiência white-label para revender o roteador sob a própria marca e portais de gestão com permissões isoladas por tenant.

As lacunas a seguir priorizam o que precisa ser ajustado antes de escalar o piloto externo.

## UC-01 — Gestão de contatos unificada
- **Sintomas**: Contatos existem apenas como números avulsos no `MessageJob`, não há deduplicação nem atributos (tags, opt-in, idioma). Importações CSV não vinculam telefone a perfis e não há API para consultas.
- **Impacto**: Times de atendimento não conseguem reutilizar histórico ou segmentar disparos. Há risco de reenviar mensagens para contatos opt-out.
- **Requisitos imediatos**:
  - Esquema de contatos com `org_id`, metadados customizáveis e timestamps de opt-in/out.
  - APIs de CRUD e importação/exportação com validações de duplicidade e consentimento.
  - Vincular mensagens e templates ao `contact_id` para construir timeline.
- **Documentos a atualizar**: [`docs/architecture/DATA_MODEL.md`](../architecture/DATA_MODEL.md), [`docs/api/API_REFERENCE.md`](../api/API_REFERENCE.md), [`docs/postman/README.md`](../postman/README.md).

## UC-02 — Atendimento multicanal orquestrado
- **Sintomas**: O roteador só envia mensagens outbound via WhatsApp. Não existem conectores inbound, nem suporte a e-mail, SMS ou chat web. Filas de atendimento e SLAs não são monitorados.
- **Impacto**: Operações que combinam atendimento humano com bots ou trocas em outros canais precisam manter stacks paralelos, perdendo a economia prometida.
- **Requisitos imediatos**:
  - Abstração de canais com contratos unificados de envio/recebimento.
  - Webhooks e filas por canal com roteamento baseado em `contact_id` e preferências.
  - Painéis de SLA e alertas para filas ativas (tempo de primeira resposta, backlog).
- **Documentos a atualizar**: [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md), [`docs/api/API_REFERENCE.md`](../api/API_REFERENCE.md), [`docs/operations/OPERATIONS.md`](../operations/OPERATIONS.md).

## UC-03 — CRM e jornada integrada
- **Sintomas**: Não há sincronização com CRMs (HubSpot, Salesforce, RD Station). Eventos de mensagens não são conciliados com oportunidades e a criação de tickets exige esforço manual.
- **Impacto**: Equipes de vendas e suporte perdem rastreabilidade da jornada e não conseguem automatizar follow-ups ou SLAs.
- **Requisitos imediatos**:
  - Webhooks outbound e conectores para CRMs priorizados.
  - Mapeamento de campos entre contatos, negócios e tickets.
  - Estratégia de reconciliamento (retry, dead-letter) e monitoramento de falhas.
- **Documentos a atualizar**: [`docs/architecture/INTEGRATIONS.md`](../architecture/INTEGRATIONS.md) *(a criar se inexistente)*, [`docs/operations/OPERATIONS.md`](../operations/OPERATIONS.md), [`docs/security/SECURITY.md`](../security/SECURITY.md).

## UC-04 — Oferta white-label e governança comercial
- **Sintomas**: Branding fixo, domínios padrão e ausência de perfis de permissão impedem parceiros de revender o produto. Não existe catálogo de planos ou relatórios customizáveis por tenant.
- **Impacto**: Resellers não conseguem aderir ao piloto e clientes finais ficam com experiência inconsistente com a marca contratada.
- **Requisitos imediatos**:
  - Theming, domínios customizados e assets (logo, cores) configuráveis por organização.
  - RBAC administrativo (partner admin, org admin, agent) com auditoria.
  - Relatórios exportáveis com carimbo da marca e metadados de plano.
- **Documentos a atualizar**: [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md), [`docs/operations/DEPLOYMENT.md`](../operations/DEPLOYMENT.md), [`docs/security/SECURITY.md`](../security/SECURITY.md).

## Próximos passos recomendados
1. Atualizar o [plano de implementação](../current-cycle/NEXT_IMPLEMENTATION_PLAN.md) com épicos e tasks alinhados a estes casos de uso.
2. Revisar o [roadmap do ciclo](../roadmap/ROADMAP.md) para incorporar fases específicas de contatos, CRM e white-label.
3. Formalizar requisitos regulatórios (LGPD, opt-in) em [`docs/security/SECURITY.md`](../security/SECURITY.md) antes de testes com clientes reais.
