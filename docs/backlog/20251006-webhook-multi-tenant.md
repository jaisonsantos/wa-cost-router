---
title: "Hardening multi-tenant do webhook WhatsApp"
type: feature
prio: P1
estimate: "3d"
owner: "unassigned"
depends_on: []
---

## Contexto

O endpoint [`POST /integrations/wa/webhook`](../api/API_REFERENCE.md) grava eventos com `org_id` hardcoded (`00000000-0000-0000-0000-000000000000`), permitindo que mensagens de um tenant contaminem dados de outro. A verificação de assinatura Meta também não é validada, abrindo espaço para abuso.

## Escopo

- Mapear `phone_id` recebido no payload para `org_id` usando `WAConnection`.
- Validar assinatura/headers Meta (ex.: `X-Hub-Signature-256`) com secret por organização.
- Rejeitar eventos inválidos com resposta 403 e log estruturado.
- Atualizar seeds/migrations caso seja necessário armazenar secrets adicionais.

## Acceptance Criteria

- Eventos criados a partir do webhook referenciam o `org_id` correto.
- Requisições com assinatura inválida retornam 403 e não inserem registros.
- Coleção Postman atualizada com exemplo de webhook assinado.
- Documentação de integração WhatsApp atualizada em [API Reference](../api/API_REFERENCE.md) e [Operações](../operations/OPERATIONS.md).

## Subtasks

- [x] Criar tabela/coluna para armazenar secret de validação por conexão WA.
- [x] Implementar verificação da assinatura (compatível com Meta Cloud API).
- [x] Resolver TODO no código do webhook (`org_id` hardcoded) usando lookup por `phone_id`.
- [x] Adicionar logs mascarados (`message_event_id` apenas) em caso de erro.
- [ ] Atualizar Postman request **WA - Webhook Receive** com headers/variáveis necessárias.
- [x] Escrever guia de operação em `docs/operations/OPERATIONS.md` descrevendo rotação de secrets.

## Referências

- [Integrações WhatsApp](../api/API_REFERENCE.md)
- [Segurança](../security/SECURITY.md)
- [Coleção Postman](../postman/README.md)
- Código: [`backend/app/api/integrations.py`](../../backend/app/api/integrations.py)

## Out of Scope

- Implementar ingestão de mensagens inbound além da gravação de `MessageEvent`.
- Construir UI para gerenciamento de conexões WA.
