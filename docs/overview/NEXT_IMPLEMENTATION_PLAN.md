# Plano de Próxima Etapa

## Índice
- [Resumo executivo](#resumo-executivo)
- [Épicos e objetivos mensuráveis](#épicos-e-objetivos-mensuráveis)
- [Quadro de tasks priorizadas](#quadro-de-tasks-priorizadas)
- [Mapa de impacto](#mapa-de-impacto)
- [Plano de testes e health-checks](#plano-de-testes-e-health-checks)
- [Backlog sugerido](#backlog-sugerido)
- [Riscos, rollout e rollback](#riscos-rollout-e-rollback)
- [Navegação entre docs](#navegação-entre-docs)

## Resumo executivo
O produto ainda não consegue calcular custos reais por provedor porque os rate cards ficam desacoplados das credenciais (seeds e importadores não vinculam tarifa → provedor) e o motor de roteamento só procura `RateCard.source == provider.name`, o que devolve custo zero e bloqueia o fallback automático.

Além disso, os simuladores exigem categorias em caixa alta, mas o frontend envia `marketing/utility`, e há chamadas sem payload (ex.: `/rules/simulate`) que geram 422 antes mesmo do cálculo.

O modo sandbox para conectores foi entregue: `SANDBOX_PROVIDERS` habilita respostas determinísticas, elimina timeouts e deixa seeds alinhadas ao cenário fake. O próximo passo crítico é persistir eventos/custos reais após o envio (T3) para liberar relatórios consistentes.

No frontend, o `API_BASE_URL` é hardcoded para localhost, impedindo deploy multiambiente, e há bugs de contrato (ex.: modal Gupshup case sensitive, Settings exibe dados estáticos).

Na documentação, o guia de migrations ignora a revisão `003_add_message_job_fk` e o `AGENTE` mantém notas defasadas (ex.: seed com `metadata.create_all`).

O README do Postman promete cobertura total, mas o CSV de exemplo não preenche campos necessários para a nova modelagem (provider).

## Épicos e objetivos mensuráveis
### E1. Routing & costing confiáveis (P0)
**Objetivo mensurável:** `POST /messages/send` deve selecionar um provedor real com tarifa registrada, gerar `MessageEvent`/`CostRecord` com valores > 0 e permitir simulação consistente, validado pela coleção Newman.

### E2. Contratos FE ↔ API e DX (P0)
**Objetivo mensurável:** Fluxos de regras, settings e providers funcionam sem erros 422 e exibem os dados reais; smoke manual cobre simulate (rápida + avançada) e modais de credenciais.

### E3. Segurança & multi-tenant hardening (P0)
**Objetivo mensurável:** Secrets fracos bloqueiam boot em produção, `/admin/metrics` requer credencial, payloads de mensagens e números ficam mascarados; Postman valida resposta 401/403 quando omitido.

### E4. Observabilidade, docs e pipeline (P1)
**Objetivo mensurável:** `make ci`/GitHub Actions continuam verdes após reorganização de docs, métricas de envio expostas (Prometheus) e documentação navegável aponta para assets corretos.

## Quadro de tasks priorizadas
| ID | Título | Prioridade | Owner sugerido | Estimativa | Dependências | Risco | DoD |
|----|--------|------------|----------------|------------|--------------|-------|-----|
| T1 | Vincular rate cards a provedores e corrigir seleção de custos | P0 | Backend | 5d | E1 | Alto (migração de dados) | • Migration Alembic adiciona `provider_id` + backfill idempotente cruzando por nome (fallback seguro).<br>• Atualizar `RoutingEngine`, seeds e importador CSV/API para usar `provider_id` (incluindo fallback por `provider_name` no CSV).<br>• Revisar docs: [`DATA_MODEL`](../architecture/DATA_MODEL.md), [`API_REFERENCE`](../api/API_REFERENCE.md), [`MIGRATIONS`](../operations/MIGRATIONS.md).<br>• Postman: request "Rates - Import CSV" com arquivo de exemplo alinhado ao fluxo automatizado.<br>• `make dev` + `make ci` verdes com base limpa e existente. |
| T2 | Sandbox de conectores e seeds determinísticas | P0 | Backend | 4d | T1 | Médio | ✅ Entregue. Toggle `SANDBOX_PROVIDERS` ativo por padrão no dev/CI, seeds determinísticas e docs/Postman atualizados. |
| T3 | Persistir `MessageEvent` + baseline ao enviar | P0 | Backend | 3d | T1 | Médio | • Após envio, gravar `MessageEvent` com custos baseline/otimizado e atualizar relatórios.<br>• Ajustar queries de `/messages/jobs` e `/reports/summary` para usar novos registros.<br>• Postman valida valores > 0 nas rotas.<br>• Atualizar [`API_REFERENCE`](../api/API_REFERENCE.md) e [`ARCHITECTURE`](../architecture/ARCHITECTURE.md).<br>• `make dev` + `make ci` verdes. |
| T4 | Normalizar categorias e payloads dos simuladores | P0 | Full-stack | 3d | T1 | Baixo | • Backend aceita categorias case-insensitive com default configurável e payload padrão para `/rules/simulate`.<br>• Frontend envia payload real, ajusta toasts/validações e remove TODO de economia.<br>• Postman atualiza requests de simulação com testes de contrato.<br>• Atualizar [`API_REFERENCE`](../api/API_REFERENCE.md) e docs de FE em [`ARCHITECTURE`](../architecture/ARCHITECTURE.md).<br>• `make dev` + `make ci` verdes + smoke FE. |
| T5 | Configuração de base URL e providers UI | P0 | Frontend | 2d | - | Baixo | • Substituir literal `http://localhost:8000` por `import.meta.env.VITE_API_BASE` com fallback seguro.<br>• Modal de credenciais Gupshup case-insensitive orientado por `provider.type`/`metadata`.<br>• Documentar variáveis em [`DEPLOYMENT`](../operations/DEPLOYMENT.md) e [`docs/postman/README.md`](../postman/README.md).<br>• Smoke manual: login → Settings → credenciais 360dialog/Gupshup.<br>• `make dev` + `make ci` verdes. |
| T6 | Settings conectada aos dados reais | P1 | Frontend | 4d | T1, T2 | Médio | • Remover mocks (`ConnectionsState`) e consumir `/integrations/wa/connections`, `/rates`, `/orgs/current`.<br>• Exibir estado/erros reais e atualizar gráficos/listas.<br>• Documentar fluxo com capturas em [`overview/README`](./README.md).<br>• Postman verifica rotas usadas pelo FE.<br>• `make dev` + `make ci` verdes. |
| T7 | Enforcement de secrets fortes | P0 | Backend | 1d | - | Baixo | • Validar em boot (exceto dev) que `APP_SECRET_KEY`/`JWT_SECRET` não usam defaults.<br>• Atualizar `.env.example`, [`SECURITY`](../security/SECURITY.md), [`OPERATIONS`](../operations/OPERATIONS.md).<br>• Postman README destaca requisito.<br>• `make dev` + `make ci` verdes. |
| T8 | Sanitização de PII em payloads e respostas | P0 | Backend | 3d | T3 | Alto | • Helpers mascaram números (`+55*****9999`) e truncam `provider_response` antes de persistir/retornar.<br>• Atualizar schemas de `messages/jobs`, webhooks e logs.<br>• Tests pytest garantindo mascaramento.<br>• Atualizar [`SECURITY`](../security/SECURITY.md), [`API_REFERENCE`](../api/API_REFERENCE.md) e Postman asserts.<br>• `make dev` + `make ci` verdes. |
| T9 | Proteger `/admin/metrics` | P0 | Backend | 1d | - | Baixo | • Implementar autenticação via header/token configurável.<br>• Documentar em [`OPERATIONS`](../operations/OPERATIONS.md) e [`SECURITY`](../security/SECURITY.md).<br>• Postman adiciona requests 200/401.<br>• `make dev` + `make ci` verdes. |
| T10 | Validação E.164 em `POST /messages/send` | P1 | Backend | 2d | T3 | Médio | • Integrar `phonenumbers` para normalizar/rejeitar inválidos.<br>• Atualizar seeds/Postman com números válidos.<br>• Documentar ajustes em [`API_REFERENCE`](../api/API_REFERENCE.md) e [`OPERATIONS`](../operations/OPERATIONS.md).<br>• `make dev` + `make ci` verdes. |
| T11 | Observabilidade de tentativas de envio | P1 | Backend | 3d | T3 | Médio | • Instrumentar métricas Prometheus (sucesso, retries, fallback) e logs estruturados.<br>• Atualizar [`OPERATIONS`](../operations/OPERATIONS.md) com métricas/dashboards.<br>• Postman verifica `/admin/metrics` com token.<br>• `make dev` + `make ci` verdes. |
| T12 | Harmonizar pipeline e docs | P1 | DevOps | 2d | T1–T5 | Baixo | • Consolidar targets `ci`/`ci-pipeline` em Makefile e GitHub Actions.<br>• Atualizar [`MIGRATIONS`](../operations/MIGRATIONS.md) com revisão `003_add_message_job_fk` e mover notas obsoletas do `AGENTE` para [`archive`](../archive).<br>• Atualizar `README.md` raiz e [`overview/README.md`](./README.md) com índice navegável.<br>• `make dev` + `make ci` verdes. |
| T13 | Atualizar coleção Postman e README | P0 | QA | 2d | T1–T5 | Médio | • Incluir todos os endpoints com variáveis (`provider_id`, `metrics_token`, etc.), pre-request scripts e asserts de payload.<br>• Atualizar [`docs/postman/README.md`](../postman/README.md) com execução via Newman e integração ao `Makefile`/CI.<br>• Smoke Newman cobre regras, mensagens, relatórios, admin/metrics.<br>• `make dev` + `make ci` verdes com coleção rodando. |

## Mapa de impacto
| Área | Impacto esperado |
|------|-----------------|
| API backend | Novas migrations, validações, métricas; dependências adicionais (`phonenumbers`). |
| Banco de dados | Alteração da tabela `rate_card`, dados seeds, criação de `MessageEvent` outbound. |
| Frontend | Ajuste de contratos (simulação, settings, providers), configuração por ambiente. |
| Worker | Sandbox reduz necessidade de worker no curto prazo; manter pronto para futura fila. |
| Postman/QA | Novos asserts, variáveis e scripts conforme tasks T1–T13. |
| Docs | Atualização e reorganização (AGENTE, MIGRATIONS, API, OPERATIONS, Postman). |
| CI/CD | Alvos `make` e workflows revisados; execução continua exigindo `make ci`. |
| Segurança | Enforce de secrets, mascaramento PII, proteção `/admin/metrics`. |
| Observabilidade | Métricas Prometheus e logging estruturado para tentativas de envio. |

**Progresso recente (2024-10-07):**
- ✅ T2 entregue — sandbox dos conectores, seeds determinísticas e Newman executando em < 60 s no modo fake.
- ✅ `POST /messages/send` agora captura falhas inesperadas do motor de roteamento/entrega, respondendo 2xx com logs detalhados em vez de 500 na coleção Newman.
- 🔜 Foco imediato em T3 para persistir `MessageEvent`/`CostRecord` reais após envio, destravando relatórios consistentes.

## Plano de testes e health-checks
### Automação local / CI
- ⚠️ `make dev` — aplicar migrations, seed atualizado, subir stack (usar sandbox quando necessário).
- ⚠️ `make ci` — garante lint/build/backend tests + Newman com coleção revisada.

### Smoke manual
- ⚠️ `newman run docs/postman/wa-cost-router.postman_collection.json -e docs/postman/wa-cost-router.postman_environment.json --folder "Messages"` — checar envio + eventos/custos.
- ⚠️ `curl -H "Authorization: Token <METRICS_TOKEN>" http://localhost:8000/admin/metrics` — validar proteção.
- Fluxo web: login → Providers → configurar credenciais fake → Rules simulate (rápida + avançada) → Settings (dados reais).

### Testes unitários
- Backend: pytest para validação de números, mascaramento e sandbox connectors (`backend/tests/test_sandbox_connectors.py`).
- Frontend: React Testing Library para simulador/Settings (renderização com dados reais).

Todos os critérios de DoD incluem `make dev` e `make ci` verdes, além de evidências (logs ou prints) anexadas ao PR.

## Backlog sugerido
Criar os seguintes arquivos em [`docs/backlog/`](../backlog):

1. `20250210-worker-offload.md` (Prioridade P2)
   - **Contexto:** após sandbox, planejar mover envios para RQ worker real para escalar.
   - **Hipótese de valor:** reduzir latência da API e permitir paralelismo controlado.
   - **Escopo inicial:** criar fila `message_send`, endpoint respondendo 202, worker consumindo jobs, garantir idempotência.
   - **DoD:** fila ativa com monitoração, Postman adiciona verificação assíncrona, docs de operações atualizados, `make ci` verde.

2. `20250210-rate-card-multitenant.md` (Prioridade P3)
   - **Contexto:** rate cards ainda globais; clientes grandes podem ter acordos específicos.
   - **Hipótese de valor:** adicionar escopo opcional por organização aumenta flexibilidade comercial.
   - **Escopo inicial:** schema com `org_id` opcional, migração com fallback global, simuladores adaptados.
   - **DoD:** migrations aplicadas, Postman cobre cenário multi-tenant, docs `DATA_MODEL` e `API_REFERENCE` atualizados, `make ci` verde.

3. `20250210-analytics-dashboard-sync.md` (Prioridade P2)
   - **Contexto:** dashboard usa eventos limitados; após T3, alinhar FE com novos campos.
   - **Hipótese de valor:** métricas confiáveis elevam adoção pelos stakeholders.
   - **Escopo inicial:** FE consome `MessageEvent`/`CostRecord` reais, ajustes nas consultas e visualizações.
   - **DoD:** smoke FE com dados reais, Postman valida endpoints, docs em [`overview/README.md`](./README.md) atualizados, `make ci` verde.

## Riscos, rollout e rollback
| Épico | Riscos | Mitigação | Rollout | Rollback |
|-------|--------|-----------|---------|----------|
| E1 | Migração de dados quebrar histórico de rate; sandbox habilitado em prod inadvertidamente. | Scripts de backfill idempotentes, flag sandbox default `false`, feature toggle com testes. | Deploy canário com sandbox desligado e verificação manual de custo > 0 após release. | Downgrade da migration (backup) + flag sandbox revertido. |
| E2 | Mudança de contratos quebrar SPA ou Postman existente. | Atualizar tipos TS e Postman na mesma PR, smoke manual antes do merge. | Feature toggles quando possível, validação em staging. | Reverter build frontend/endpoints mantendo compatibilidade. |
| E3 | Bloqueio por secrets fortes em ambientes de dev/CI. | Documentar defaults aceitos para `ENV=development`, ajustar GitHub secrets antes do merge. | Ativar check somente quando `ENV=production`. | Remover validação (flag) ou redefinir secrets válidos. |
| E4 | Consolidar `ci`/`ci-pipeline` pode quebrar workflow externo. | Notificar time, manter alias temporário, atualizar docs. | Merge com monitoramento do pipeline GitHub; reverter se falhar. | Reverter Makefile/workflow para estado anterior. |

## Navegação entre docs
- [Visão geral](./README.md)
- [Arquitetura](../architecture/ARCHITECTURE.md)
- [Modelagem de Dados](../architecture/DATA_MODEL.md)
- [Referência da API](../api/API_REFERENCE.md)
- [Operações](../operations/OPERATIONS.md)
- [Guia de Migrations](../operations/MIGRATIONS.md)
- [Segurança](../security/SECURITY.md)
- [Postman](../postman/README.md)
- [Backlog Prioritário](../backlog/README.md)

Este plano consolida a próxima etapa crítica antes do rollout externo, garantindo que documentação, scripts, coleção Postman e pipelines permaneçam alinhados ao código.
