[Docs](../current-cycle/README.md) › [Segurança](./SECURITY.md)
# Segurança & Hardening

## Estado Atual

- **Autenticação**: JWT HS256 com expiração 7 dias, `org_id` no payload.
- **Criptografia**: tokens WhatsApp via Fernet (`APP_SECRET_KEY`). Credenciais de provedores criptografadas (migration 002).
- **Multi-tenancy**: filtros `org_id` ativos em providers, routing e mensagens; webhook mapeia `phone_number_id` → `WAConnection` e registra assinaturas HMAC ausentes/inválidas antes de descartar eventos.
- **Logs**: erros do webhook expõem apenas `provider_event_id`/`message_event_id`; respostas de provedores e variáveis de template são persistidas mascaradas.
- **Endpoints sensíveis**: `/admin/metrics` requer header `X-Admin-Token`; configure `METRICS_AUTH_TOKEN` (ou use o fallback local) antes de expor o endpoint. `GET /rates` requer auth.
- **Rate limiting**: Redis limita `POST /messages/send` e `POST /auth/login` por `org_id` com logging estruturado e headers `Retry-After`/`X-RateLimit-Remaining`.

## Ações Recomendadas (Prioridade Alta)

1. ~~**Sanitização de payloads**~~ ✅
   - `DeliveryAttempt.provider_response` e `MessageJob.variables` recebem versões mascaradas automaticamente antes de serem persistidas.
2. ~~**Webhook multi-tenant**~~ ✅
   - Controle implementado: lookup por `phone_number_id`; assinatura HMAC verificada quando presente.
3. **Validação de entradas**
   - Biblioteca `phonenumbers` para E.164.
   - Sanitização de logs (evitar números completos).
4. **Proteção de métricas/admin**
   - ✅ Token dedicado (`X-Admin-Token`) aplicado em `/admin/metrics` com fallback apenas em ambientes `ENVIRONMENT=local/test`.
   - Mover endpoints admin para rede interna.
5. ~~**Rate limiting**~~ ✅
   - Expandir monitoramento (Prometheus/alertas) usando as métricas registradas nos logs estruturados.
6. ~~**Secrets & Config**~~ ✅
   - `Settings` agora rejeita `JWT_SECRET`/`APP_SECRET_KEY` com valores padrão quando `ENVIRONMENT` não estiver em modo desenvolvimento/teste. Gere secrets fortes com `openssl rand -base64 32` e armazene-os em um secrets manager.
   - TLS obrigatório; CORS configurável via env.

## Ações Futuras

- RBAC (owner/member) com autorização por rota.
- Audit log centralizado (credenciais, regras, envios).
- Monitoramento de acesso (alerta para falhas de login).
- Revisão LGPD/GDPR: retenção mínima de dados e consentimento.

## Política de Mascaramento de Payloads

- Telefones armazenados ou serializados pelas rotas de mensagens seguem o formato `+**********XX`, preservando apenas o DDI (quando presente) e os dois últimos dígitos.
- Endereços de e-mail são mascarados como `f***@d***.tld`, exibindo apenas o primeiro caractere do usuário e do domínio.
- Chaves relacionadas a segredos (`token`, `secret`, `password`, `api_key`, etc.) são substituídas por `***redacted***`.
- `MessageJob.variables` e `DeliveryAttempt.provider_response` são higienizados antes do `commit`, evitando que dados sensíveis cheguem ao banco.
- As respostas públicas de `/messages/jobs` e `/messages/jobs/{job_id}` retornam `to_number` e `channel_address` mascarados, alinhando API, banco e coleções Postman com a mesma política.

## Testes de Segurança Recomendados

- **Multi-tenant**: registrar duas orgs, tentar acessar provider/rule de outra via UUID.
- **Idempotência**: enviar mesma chave duas vezes (ver job único).
- **Injection**: payload malicioso em `variables` (validar escapes).
- **Rate limit**: stress `POST /messages/send` após implementar limitação.

## Veja também

- [Operações & runbooks](../operations/OPERATIONS.md)
- [Backlog priorizado](../backlog/README.md)
- [Coleção Postman](../postman/README.md)
