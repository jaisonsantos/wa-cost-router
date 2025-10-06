# Migration Guide - WA Cost Router

## Última Atualização: 2025-10-06

Este guia contém as instruções para executar as migrations necessárias após as últimas implementações.

## 🗄️ Migrations Pendentes

### Migration 001: Add MVP Models

Esta migration adiciona os campos necessários para o cálculo de economia real e organização de provedores.

**Mudanças:**
1. Adiciona `baseline_cost_minor` à tabela `message_event` para cálculo de economia
2. Adiciona `org_id` à tabela `provider` para multi-tenancy
3. Atualiza constraints do `provider` para permitir múltiplas orgs
4. **NOVO**: Adiciona unique constraint `(org_id, idempotency_key)` em `message_job` para garantir idempotência
5. **NOVO**: Adiciona `price_table_version` em `cost_record` para auditoria de preços

## 📋 Como Executar

### 1. Parar os serviços
```bash
docker-compose down
```

### 2. Rodar a migration
```bash
# Iniciar apenas o banco
docker-compose up -d db

# Esperar o banco inicializar (5-10 segundos)
sleep 10

# Rodar a migration
docker-compose run --rm api alembic upgrade head
```

### 3. Popular dados seed (provedores)
```bash
# Executar script de seed para criar provedores padrão
docker-compose run --rm api python scripts/seed_providers.py
```

### 4. Reiniciar todos os serviços
```bash
docker-compose up -d
```

## 🔍 Verificar se funcionou

### Verificar tabelas
```bash
docker-compose exec db psql -U postgres -d wa_cost_router -c "\d message_event"
docker-compose exec db psql -U postgres -d wa_cost_router -c "\d provider"
```

Você deve ver:
- `baseline_cost_minor` na tabela `message_event`
- `org_id` na tabela `provider`
- Unique constraint `_org_idempotency_uc` na tabela `message_job`
- `price_table_version` na tabela `cost_record`

### Verificar provedores
```bash
docker-compose exec db psql -U postgres -d wa_cost_router -c "SELECT id, name, type, status FROM provider;"
```

Você deve ver os provedores:
- 360dialog (type: whatsapp)
- Gupshup (type: whatsapp)

## ⚠️ Troubleshooting

### Erro: "relation already exists"
Se a migration falhar porque as tabelas já existem, você pode precisar criar uma migration personalizada ou alterar manualmente:

```bash
docker-compose exec db psql -U postgres -d wa_cost_router
```

Então execute:
```sql
-- Adicionar baseline_cost_minor se não existir
ALTER TABLE message_event ADD COLUMN IF NOT EXISTS baseline_cost_minor INTEGER;

-- Adicionar org_id ao provider se não existir
ALTER TABLE provider ADD COLUMN IF NOT EXISTS org_id UUID;

-- Atualizar provedores existentes com org_id da primeira org
UPDATE provider 
SET org_id = (SELECT id FROM organization LIMIT 1) 
WHERE org_id IS NULL;

-- Tornar org_id obrigatório
ALTER TABLE provider ALTER COLUMN org_id SET NOT NULL;

-- Remover constraint antiga e adicionar nova
ALTER TABLE provider DROP CONSTRAINT IF EXISTS provider_name_key;
ALTER TABLE provider ADD CONSTRAINT _org_provider_name_uc UNIQUE (org_id, name);
```

### Erro: "alembic command not found"
Certifique-se de que está executando dentro do container:
```bash
docker-compose run --rm api alembic upgrade head
```

### Verificar logs
```bash
docker-compose logs api
```

## 🎯 Próximos Passos

Após executar as migrations com sucesso:

1. ✅ **Backend APIs implementadas**:
   - `/messages/send` - Envio com roteamento + idempotência + retry + fallback
   - `/messages/jobs` - Listar jobs
   - `/messages/jobs/{id}` - Detalhes + tentativas
   - `/providers` - CRUD com segurança multi-tenant
   - `/reports/dashboard-metrics` - Métricas de economia
   - `/reports/provider-metrics` - Performance por provedor
   - `/rules/simulate-advanced` - Simulador com breakdown

2. ✅ **Frontend completo** conectado aos backends

3. ✅ **Segurança implementada**:
   - Multi-tenancy: filtros `org_id` em todos os endpoints
   - Idempotência: unique constraint `(org_id, idempotency_key)`
   - Auditoria: `price_table_version` em custos

4. 🔄 **Testar fluxo E2E**:
   - Login → Dashboard (métricas reais)
   - Providers → Configurar 360dialog/Gupshup
   - Rules → Criar regra BR/ES → Simular economia
   - Messages → Enviar teste → Verificar job/attempts/fallback

## 📚 Referências

- Arquivo da migration: `backend/alembic/versions/001_add_mvp_models.py`
- Models atualizados: `backend/app/models/models.py`
- Documentação Alembic: https://alembic.sqlalchemy.org/
