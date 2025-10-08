"""Exceções específicas para integrações CRM."""


class CRMError(Exception):
    """Erro base para integrações CRM."""


class ProviderNotRegisteredError(CRMError):
    """Indica que não há provedor registrado para o slug solicitado."""

    def __init__(self, slug: str):
        super().__init__(f"Provedor CRM '{slug}' não está registrado no registry.")
        self.slug = slug


class ProviderNotConfiguredError(CRMError):
    """Indica que o provedor CRM não foi configurado para o tenant."""

    def __init__(self, slug: str):
        super().__init__(f"Provedor CRM '{slug}' não está configurado para o tenant informado.")
        self.slug = slug


class CredentialsNotConfiguredError(CRMError):
    """Indica que as credenciais não foram cadastradas ou estão inativas."""

    def __init__(self, slug: str):
        super().__init__(f"Credenciais ativas não encontradas para o provedor CRM '{slug}'.")
        self.slug = slug


class FieldMappingError(CRMError):
    """Falha ao aplicar mapeamento de campos customizados."""

    def __init__(self, message: str):
        super().__init__(message)


class ProviderSyncError(CRMError):
    """Erro ao executar sincronização incremental com o provedor."""

    def __init__(self, slug: str, message: str):
        super().__init__(f"[{slug}] {message}")
        self.slug = slug
        self.message = message
