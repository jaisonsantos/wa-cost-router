# USE_CASE_GAP — Lacunas para Piloto Multicanal

## Sumário executivo
O discovery com as equipes de atendimento e growth apontou que o MVP inicial atendia apenas ao envio de mensagens outbound no WhatsApp. Desde então o catálogo multi-tenant, o motor multicanal e os webhooks auditáveis foram concluídos, liberando UC-01 e UC-02 para o piloto externo. Os fluxos reais dos clientes agora dependem de sincronização com CRMs consolidados e de recursos white-label para parceiros.

As lacunas a seguir priorizam o que ainda precisa ser ajustado antes de encerrar o ciclo, concentrando-se em UC-03 e UC-04.

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

## Aprendizados recentes (UC-01 e UC-02)
- **Consentimento multicanal precisa de defaults seguros** — Normalizar endereços (`E.164`, lower-case e-mail) antes da validação evitou falsos negativos na auditoria e garantiu idempotência dos webhooks. Documentamos o fluxo completo em [`docs/api/API_REFERENCE.md`](../api/API_REFERENCE.md) e [`docs/operations/OPERATIONS.md`](../operations/OPERATIONS.md).
- **SLA em tempo quase real exige rebuild incremental** — O worker de conversas passou a recalcular `sla_snapshot` com janelas configuráveis, permitindo dashboards que combinam custos, backlog e FRT (`/reports/channel-metrics`). O desenho técnico está consolidado em [`docs/architecture/ARCHITECTURE.md`](../architecture/ARCHITECTURE.md).
- **Evidências padronizadas aceleram aceite** — Os scripts de captura (`scripts/capture-screenshots.mjs`) foram integrados ao checklist operacional, permitindo anexar dashboards e regras simuladas no encerramento do caso de uso.

## Próximos passos recomendados
1. Atualizar o [plano de implementação](../current-cycle/NEXT_IMPLEMENTATION_PLAN.md) com épicos e tasks alinhados a estes casos de uso.
2. Revisar o [roadmap do ciclo](../roadmap/ROADMAP.md) para incorporar fases específicas de contatos, CRM e white-label.
3. Formalizar requisitos regulatórios (LGPD, opt-in) em [`docs/security/SECURITY.md`](../security/SECURITY.md) antes de testes com clientes reais.
