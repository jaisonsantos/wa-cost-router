# CHANGELOG — Ciclo Atual

## 2025-10-09

### Documentação
- Reescrevemos a referência de API com payloads detalhados, respostas de sucesso/erro e filtros opcionais, cobrindo autenticação, contatos, relatórios, integrações e webhook de opt-in.

### Ferramentas
- Sincronizamos a coleção Postman com os contratos atuais: ajustes de testes (org/health check/webhook), remoção de headers inválidos e assinatura automática do webhook do WhatsApp.

### Backend
- Tornamos os endpoints de contatos e segmentos resilientes a registros legados, saneando campos JSON opcionais e evitando respostas 500 nos fluxos de listagem e criação exercitados pelo CI.
- Ajustamos a listagem de contatos para deduplicar resultados antes da paginação e manter a ordenação em PostgreSQL, eliminando os 500 no `GET /contacts` durante o pipeline.
- Criamos a migration `009_add_contact_segment_policy` para persistir políticas de segmentos e destravar os fluxos de `PUT`/`DELETE` exercitados pela coleção Newman.
