[Docs](../current-cycle/README.md) › [Segurança](./SECURITY.md)
# Segurança & Hardening

## Estado Atual

- **Autenticação**: JWT HS256 com expiração 7 dias, `org_id` no payload.
- **Criptografia**: tokens WhatsApp via Fernet (`APP_SECRET_KEY`). Credenciais de provedores criptografadas (migration 002).
- **Multi-tenancy**: filtros `org_id` ativos em providers, routing e mensagens; webhook mapeia `phone_number_id` → `WAConnection` e registra assinaturas HMAC ausentes/inválidas antes de descartar eventos.
- **Logs**: erros do webhook expõem apenas `provider_event_id`/`message_event_id`; provider responses ainda persistem dados completos.
- **Endpoints sensíveis**: `/admin/metrics` público; `GET /rates` agora requer auth.
- **Rate limiting**: Redis limita `POST /messages/send` e `POST /auth/login` por `org_id` com logging estruturado e headers `Retry-After`/`X-RateLimit-Remaining`.

## Ações Recomendadas (Prioridade Alta)

1. **Sanitização de payloads**
   - Aplicar máscara/anonimização em `DeliveryAttempt.provider_response` e `MessageJob.variables`.
2. ~~**Webhook multi-tenant**~~ ✅
   - Controle implementado: lookup por `phone_number_id`; assinatura HMAC verificada quando presente.
3. **Validação de entradas**
   - Biblioteca `phonenumbers` para E.164.
   - Sanitização de logs (evitar números completos).
4. **Proteção de métricas/admin**
   - Autenticação (basic auth ou token) em `/admin/metrics`.
   - Mover endpoints admin para rede interna.
5. ~~**Rate limiting**~~ ✅
   - Expandir monitoramento (Prometheus/alertas) usando as métricas registradas nos logs estruturados.
6. **Secrets & Config**
   - Enforce override de `JWT_SECRET`/`APP_SECRET_KEY` em produção (ver backlog P1 "enforce secret strength").
   - TLS obrigatório; CORS configurável via env.

## Ações Futuras

- RBAC (owner/member) com autorização por rota.
- Audit log centralizado (credenciais, regras, envios).
- Monitoramento de acesso (alerta para falhas de login).
- Revisão LGPD/GDPR: retenção mínima de dados e consentimento.

## Testes de Segurança Recomendados

- **Multi-tenant**: registrar duas orgs, tentar acessar provider/rule de outra via UUID.
- **Idempotência**: enviar mesma chave duas vezes (ver job único).
- **Injection**: payload malicioso em `variables` (validar escapes).
- **Rate limit**: stress `POST /messages/send` após implementar limitação.

## Veja também

- [Operações & runbooks](../operations/OPERATIONS.md)
- [Backlog priorizado](../backlog/README.md)
- [Coleção Postman](../postman/README.md)
