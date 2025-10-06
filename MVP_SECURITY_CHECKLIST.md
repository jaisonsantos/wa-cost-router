# MVP Security & Hardening Checklist

## ✅ IMPLEMENTADO - Segurança Multi-Tenant

### 1. Isolamento por Organização
- ✅ **Provider**: filtrado por `org_id` em GET /providers
- ✅ **MessageJob**: filtrado por `org_id` em listagem e detalhes
- ✅ **ProviderCredential**: vinculado a `org_id`
- ✅ **RoutingRule**: vinculado a `org_id` (já existente)
- ✅ **MessageEvent**: vinculado a `org_id` (já existente)

### 2. Idempotência e Integridade
- ✅ **Unique Constraint**: `(org_id, idempotency_key)` em `message_job`
  - Previne duplicação de mensagens
  - Garante idempotência por organização
  - Implementado via migration 001

### 3. Auditoria de Custos
- ✅ **price_table_version** em `cost_record`
  - Rastreabilidade de qual versão de preço foi usada
  - Permite reproduzir cálculos históricos
  - Essencial para disputas e compliance

### 4. Credenciais Seguras
- ✅ Credenciais armazenadas em `provider_credential.credentials_encrypted`
- ✅ Unique constraint: `(org_id, provider_id)` - uma credencial por provedor/org
- ⚠️ **TODO**: Implementar criptografia real (atualmente JSON plano)

### 5. Autenticação e Autorização
- ✅ JWT via `get_current_user` dependency
- ✅ Token extraído do header `Authorization: Bearer`
- ✅ `org_id` embedado no token e validado em todas as operações
- ⚠️ **TODO**: Implementar RBAC (Owner vs Member)

## ⚠️ PENDENTE - Hardening Adicional

### 1. Criptografia de Credenciais
```python
# Usar Fernet (já existe no projeto para WhatsApp tokens)
from cryptography.fernet import Fernet
from app.core.config import settings

def encrypt_credentials(data: dict) -> str:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return cipher.encrypt(json.dumps(data).encode()).decode()

def decrypt_credentials(encrypted: str) -> dict:
    cipher = Fernet(settings.ENCRYPTION_KEY)
    return json.loads(cipher.decrypt(encrypted.encode()).decode())
```

### 2. Rate Limiting
- [ ] Limitar requisições por org (ex: 100 req/min)
- [ ] Limitar envios de mensagem por org (ex: 1000 msg/hora)
- [ ] Implementar via middleware ou Redis

### 3. Auditoria Completa
- [ ] Tabela `audit_log` para rastrear ações críticas:
  - Criação/alteração de regras
  - Configuração de credenciais
  - Envios de mensagens
  - Mudanças em providers

### 4. Circuit Breaker
- [ ] Detectar outage de provider (ex: 80% erro em 5 min)
- [ ] Abrir circuito e redirecionar para fallback automaticamente
- [ ] Alertar admin via email/webhook

### 5. Validação de Entrada
- [ ] Validar formatos de números (E.164)
- [ ] Sanitizar variáveis de template
- [ ] Limitar tamanho de payloads (max 1MB)

### 6. HTTPS Obrigatório
- [ ] Forçar HTTPS em produção
- [ ] HSTS headers
- [ ] Certificate pinning para provedores

## 📊 Métricas de Segurança (Monitorar)

### SLOs de Segurança
1. **Zero breach multi-tenant**: nenhuma org deve acessar dados de outra
2. **99.9% idempotência**: duplicações < 0.1%
3. **Audit trail completo**: 100% de custos com `price_table_version`
4. **Credential leak = 0**: nenhuma credencial em logs/responses

### Testes de Segurança
```bash
# 1. Testar isolamento multi-tenant
# Criar 2 orgs, tentar acessar dados da org B com token da org A

# 2. Testar idempotência
# Enviar mesma mensagem 2x com mesmo idempotency_key
# Resultado esperado: 200 OK ambas, mas apenas 1 job criado

# 3. Testar rate limiting
# Fazer 200 requisições em 1 segundo
# Resultado esperado: 429 Too Many Requests após limite

# 4. Testar SQL injection
curl -X POST /messages/send \
  -d '{"to_number": "+55119999'; DROP TABLE message_job;--"}'
# Resultado esperado: validação falha, tabela intacta
```

## 🚨 Checklist Go-Live

Antes de abrir para clientes pagantes:

- [x] Multi-tenancy validado (filtros `org_id`)
- [x] Idempotência implementada (unique constraint)
- [x] Auditoria de custos (price_table_version)
- [ ] Credenciais criptografadas (Fernet)
- [ ] Rate limiting configurado
- [ ] Circuit breaker para fallback automático
- [ ] Logs não expõem dados sensíveis
- [ ] HTTPS forçado em produção
- [ ] Backup automatizado do banco
- [ ] Plano de resposta a incidentes
- [ ] GDPR/LGPD compliance (se aplicável)

## 📚 Referências

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- Multi-tenancy patterns: https://docs.microsoft.com/azure/architecture/patterns/
- Fernet encryption: https://cryptography.io/en/latest/fernet/
