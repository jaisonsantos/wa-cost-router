"""Provider registry metadata and form schemas."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _combine_unique(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _merge_dict(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in extra.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


FieldDict = Dict[str, Any]
SchemaDict = Dict[str, Any]


@dataclass(frozen=True)
class ProviderRegistryEntry:
    required_fields: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    form_schema: Dict[str, Any] = field(default_factory=lambda: {"fields": []})


@dataclass(frozen=True)
class ProviderProfile:
    required_fields: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    form_schema: Dict[str, Any] = field(default_factory=lambda: {"fields": []})


ProviderKey = Tuple[str, str]


def _normalize(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().lower()


def _merge_form_schema(base: SchemaDict, override: SchemaDict) -> SchemaDict:
    merged: SchemaDict = deepcopy(base) if base else {"fields": []}
    override_copy: SchemaDict = deepcopy(override) if override else {"fields": []}

    base_fields: List[FieldDict] = list(merged.get("fields", []))
    override_fields: List[FieldDict] = list(override_copy.get("fields", []))

    fields_by_key: Dict[str, FieldDict] = {}
    order: List[str] = []

    for schema_field in base_fields:
        key = schema_field.get("key")
        if not key:
            continue
        fields_by_key[key] = deepcopy(schema_field)
        order.append(key)

    for schema_field in override_fields:
        key = schema_field.get("key")
        if not key:
            continue
        merged_field = _merge_dict(fields_by_key.get(key, {}), schema_field)
        fields_by_key[key] = merged_field
        if key not in order:
            order.append(key)

    merged_fields = [fields_by_key[key] for key in order]
    merged["fields"] = merged_fields

    for list_key in ("consent_guidance", "testing_instructions"):
        merged_values = merged.get(list_key, []) or []
        override_values = override_copy.get(list_key, []) or []
        merged[list_key] = _combine_unique([*merged_values, *override_values])

    for key, value in override_copy.items():
        if key in {"fields", "consent_guidance", "testing_instructions"}:
            continue
        merged[key] = value

    return merged


SMS_BASE = ProviderRegistryEntry(
    required_fields=["from_number"],
    metadata={
        "channel": "sms",
        "compliance": {
            "opt_in": "É obrigatório possuir opt-in explícito antes de iniciar conversas por SMS.",
        },
    },
    form_schema={
        "title": "Configuração SMS",
        "description": "Informe as credenciais e o remetente em formato E.164.",
        "fields": [
            {
                "key": "from_number",
                "label": "Número remetente (E.164)",
                "type": "tel",
                "placeholder": "+15558675309",
                "mask": "+###############",
                "required": True,
                "help_text": "O número deve estar habilitado no sandbox e registrado em 10DLC quando aplicável.",
                "validation": {
                    "regex": r"^\+[1-9]\d{7,14}$",
                    "message": "Informe um telefone em formato E.164 (ex.: +15558675309).",
                },
            },
        ],
        "consent_guidance": [
            "Certifique-se de que cada destinatário concedeu opt-in documentado para recebimento de SMS.",
        ],
        "testing_instructions": [
            "Utilize o console do provedor para confirmar que o número de teste está autorizado a receber mensagens sandbox.",
        ],
    },
)


SMS_TWILIO = ProviderRegistryEntry(
    required_fields=["account_sid", "auth_token", "from_number"],
    metadata={
        "provider": "twilio",
        "compliance": {
            "registrations": [
                "Para produção, registre campanhas 10DLC e mantenha evidências de consentimento.",
            ],
        },
    },
    form_schema={
        "title": "Twilio SMS Sandbox",
        "fields": [
            {
                "key": "account_sid",
                "label": "Account SID",
                "type": "text",
                "placeholder": "ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                "required": True,
                "help_text": "Identificador principal da conta Twilio (32 caracteres).",
                "validation": {
                    "regex": r"^AC[a-fA-F0-9]{32}$",
                    "message": "Use um Account SID válido iniciando com 'AC'.",
                },
            },
            {
                "key": "auth_token",
                "label": "Auth Token",
                "type": "password",
                "placeholder": "Auth token da conta Twilio",
                "required": True,
                "help_text": "Token secreto usado para assinar webhooks e autenticar requisições.",
                "validation": {
                    "regex": r"^[A-Za-z0-9]{16,64}$",
                    "message": "O Auth Token deve conter apenas letras e números (16-64 caracteres).",
                },
            },
            {
                "key": "from_number",
                "mask": "+###############",
            },
            {
                "key": "inbound_verify_token",
                "label": "Token de verificação inbound",
                "type": "text",
                "placeholder": "token-personalizado",
                "required": False,
                "help_text": "Token utilizado para validar webhooks de entrada no ambiente sandbox.",
                "validation": {
                    "regex": r"^[A-Za-z0-9_\-]{8,64}$",
                    "message": "Use apenas letras, números, hífen ou underscore (8-64 caracteres).",
                },
            },
        ],
        "consent_guidance": [
            "Mapeie opt-ins para números curtos/longos antes de migrar do sandbox para produção.",
        ],
        "testing_instructions": [
            "Envie uma mensagem de teste via API do Twilio após salvar as credenciais.",
            "Valide a assinatura dos webhooks com o Auth Token configurado.",
        ],
    },
)


EMAIL_BASE = ProviderRegistryEntry(
    required_fields=["from_email"],
    metadata={
        "channel": "email",
    },
    form_schema={
        "title": "Configuração de Email",
        "description": "Informe remetente e segredos utilizados para assinar webhooks.",
        "fields": [
            {
                "key": "from_email",
                "label": "Remetente padrão",
                "type": "email",
                "placeholder": "noreply@exemplo.com",
                "required": True,
                "help_text": "Endereço utilizado como remetente principal das notificações.",
                "validation": {
                    "regex": r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
                    "message": "Informe um endereço de e-mail válido.",
                },
            },
        ],
        "consent_guidance": [
            "Utilize double opt-in e registre evidências de consentimento para newsletters.",
        ],
        "testing_instructions": [
            "Envie um e-mail de validação para uma caixa monitorada após atualizar as credenciais.",
        ],
    },
)


EMAIL_SENDGRID = ProviderRegistryEntry(
    required_fields=[
        "api_key",
        "from_email",
        "inbound_signing_secret",
        "webhook_token",
    ],
    metadata={
        "provider": "sendgrid",
        "compliance": {
            "dns": [
                "Habilite SPF e DKIM para o domínio remetente antes de enviar em produção.",
            ],
        },
    },
    form_schema={
        "title": "SendGrid Sandbox",
        "fields": [
            {
                "key": "api_key",
                "label": "API Key",
                "type": "password",
                "placeholder": "SG.xxxxx",
                "required": True,
                "help_text": "Chave de API com permissões para envio e gerenciamento de webhooks.",
                "validation": {
                    "regex": r"^SG\.[A-Za-z0-9_-]{16,128}$",
                    "message": "A API Key deve iniciar com 'SG.' e conter letras, números, '_' ou '-'.",
                },
            },
            {
                "key": "from_email",
            },
            {
                "key": "webhook_token",
                "label": "Token de webhook",
                "type": "text",
                "placeholder": "token-webhook",
                "required": True,
                "help_text": "Utilizado para validar chamadas vindas do inbound Parse/Webhook.",
                "validation": {
                    "regex": r"^[A-Za-z0-9_\-]{12,128}$",
                    "message": "O token deve ter entre 12 e 128 caracteres alfanuméricos, hífen ou underscore.",
                },
            },
            {
                "key": "inbound_signing_secret",
                "label": "Assinatura inbound (Signing Secret)",
                "type": "password",
                "placeholder": "secret123",
                "required": True,
                "help_text": "Segredo usado para validar eventos de inbound Parse ou Event Webhook.",
                "validation": {
                    "regex": r"^[A-Za-z0-9]{16,128}$",
                    "message": "O segredo deve ter entre 16 e 128 caracteres alfanuméricos.",
                },
            },
        ],
        "consent_guidance": [
            "Respeite cancelamentos (unsubscribe) e mantenha listas de supressão sincronizadas.",
            "Documente a política de retenção de logs e máscaras campos sensíveis em testes.",
        ],
        "testing_instructions": [
            "Use o simulador de Event Webhook do SendGrid para validar a assinatura com o segredo configurado.",
        ],
    },
)


WHATSAPP_BASE = ProviderRegistryEntry(
    required_fields=["access_token"],
    metadata={"channel": "whatsapp"},
    form_schema={
        "title": "WhatsApp Business API",
        "fields": [
            {
                "key": "access_token",
                "label": "Access Token",
                "type": "password",
                "placeholder": "Token da API",
                "required": True,
                "help_text": "Token gerado pelo parceiro oficial (ex.: 360dialog).",
            }
        ],
    },
)


WHATSAPP_GUPSHUP = ProviderRegistryEntry(
    required_fields=["api_key", "app_name"],
    metadata={"provider": "gupshup"},
    form_schema={
        "title": "Gupshup WhatsApp",
        "fields": [
            {
                "key": "api_key",
                "label": "API Key",
                "type": "password",
                "placeholder": "API key Gupshup",
                "required": True,
                "help_text": "Chave obtida no portal Gupshup.",
            },
            {
                "key": "app_name",
                "label": "App Name",
                "type": "text",
                "placeholder": "Nome do app",
                "required": True,
                "help_text": "Aplicação configurada na conta Gupshup.",
            },
        ],
    },
)


PROVIDER_TYPE_REGISTRY: Dict[str, ProviderRegistryEntry] = {
    "sms": SMS_BASE,
    "email": EMAIL_BASE,
    "whatsapp": WHATSAPP_BASE,
}


PROVIDER_NAME_OVERRIDES: Dict[ProviderKey, ProviderRegistryEntry] = {
    ("sms", "twilio"): SMS_TWILIO,
    ("sms", "twilio sandbox"): SMS_TWILIO,
    ("email", "sendgrid"): EMAIL_SENDGRID,
    ("email", "sendgrid sandbox"): EMAIL_SENDGRID,
    ("whatsapp", "gupshup"): WHATSAPP_GUPSHUP,
    ("whatsapp", "gupshup sandbox"): WHATSAPP_GUPSHUP,
}


def _resolve_entry(provider_type: str, provider_name: Optional[str]) -> ProviderRegistryEntry:
    normalized_type = _normalize(provider_type) or ""
    base_entry = PROVIDER_TYPE_REGISTRY.get(normalized_type, ProviderRegistryEntry())

    entry = ProviderRegistryEntry(
        required_fields=list(base_entry.required_fields),
        metadata=deepcopy(base_entry.metadata),
        form_schema=deepcopy(base_entry.form_schema),
    )

    normalized_name = _normalize(provider_name)
    if normalized_name:
        override = PROVIDER_NAME_OVERRIDES.get((normalized_type, normalized_name))
        if override:
            entry = ProviderRegistryEntry(
                required_fields=_combine_unique(
                    [*entry.required_fields, *override.required_fields]
                ),
                metadata=_merge_dict(entry.metadata, override.metadata),
                form_schema=_merge_form_schema(entry.form_schema, override.form_schema),
            )

    return entry


def get_provider_profile(
    provider_type: str,
    provider_name: Optional[str] = None,
    provider_meta: Optional[Dict[str, Any]] = None,
) -> ProviderProfile:
    entry = _resolve_entry(provider_type, provider_name)

    meta_required = provider_meta.get("required_fields") if provider_meta else None
    if isinstance(meta_required, list):
        extra_required = [value for value in meta_required if isinstance(value, str)]
    else:
        extra_required = []

    combined_required = _combine_unique([*entry.required_fields, *extra_required])

    merged_meta = _merge_dict(entry.metadata, provider_meta or {})

    return ProviderProfile(
        required_fields=combined_required,
        metadata=merged_meta,
        form_schema=deepcopy(entry.form_schema),
    )


def validate_provider_credentials(
    provider_type: str,
    credentials: Dict[str, Any],
    *,
    provider_name: Optional[str] = None,
    provider_meta: Optional[Dict[str, Any]] = None,
) -> List[str]:
    profile = get_provider_profile(provider_type, provider_name, provider_meta)

    errors: List[str] = []
    fields_by_key: Dict[str, FieldDict] = {
        field.get("key"): field
        for field in profile.form_schema.get("fields", [])
        if isinstance(field, dict) and field.get("key")
    }

    for field_key in profile.required_fields:
        field = fields_by_key.get(field_key, {"label": field_key})
        label = field.get("label", field_key)
        value = credentials.get(field_key)
        if value in (None, ""):
            errors.append(f"O campo '{label}' é obrigatório.")

    for field_key, field in fields_by_key.items():
        validation = field.get("validation")
        if not validation:
            continue
        regex = validation.get("regex")
        message = validation.get("message") or "Formato inválido."
        if not regex:
            continue
        value = credentials.get(field_key)
        if value in (None, ""):
            continue
        if not isinstance(value, str):
            errors.append(f"O campo '{field.get('label', field_key)}' deve ser texto.")
            continue
        if re.fullmatch(regex, value) is None:
            errors.append(message)

    return errors

