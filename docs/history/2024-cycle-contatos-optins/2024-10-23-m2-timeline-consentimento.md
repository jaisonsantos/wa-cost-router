# Snapshot — M2 — Timeline e consentimento (2024-10-23)

## Resumo
- Endpoint `/contacts/{id}/consents` ampliado para versionamento completo com evidências (`channel`, `proof_type`, `proof_url`).
- Timeline de contatos publicada na SPA com filtros por organização e eventos críticos destacados.
- Auditoria de consentimentos integrada ao pipeline de logs mascarados, preparando a revisão de compliance do marco M4.

## Entregáveis concluídos
- Novo playbook de consentimento documentado em [`docs/operations/OPERATIONS.md`](../../operations/OPERATIONS.md#consentimento-multi-tenant).
- Eventos de auditoria enviados ao tópico `audit.optin` com retentativa e alerta no Grafana (`dashboard Opt-in Health`).
- Painel "Consentimentos ativos" disponível na aba de contatos do frontend com dados paginados e exportação CSV.

## Evidências
- Sessão de UAT com parceiros piloto registrou 12 opt-ins reais (IDs anexados no relatório QA-2024-10-23).
- Alarmes de ausência de prova de consentimento permaneceram zerados por 48h consecutivas após o rollout.

## Impacto nos casos de uso
- UC-01 passa para **pronto para handover ao piloto externo**, restando apenas dependências de sanitização para o go-live.
- UC-02 recebe insumos para iniciar o roteamento multi-tenant com verificação de consentimento ativo.

## Próximos passos imediatos
- Configurar webhook multi-tenant (M3) consumindo os eventos `audit.optin` para reforçar validações.
- Atualizar matrizes de rastreabilidade e roadmap com os marcos entregues.
