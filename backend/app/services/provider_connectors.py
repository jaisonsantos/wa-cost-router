from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import hashlib
import json
import logging
from datetime import datetime

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

class ProviderConnector(ABC):
    """Interface abstrata para conectores de provedores"""
    
    def __init__(self, credentials: Dict[str, Any], base_url: Optional[str] = None):
        self.credentials = credentials
        self.base_url = base_url
    
    @abstractmethod
    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Envia mensagem via provedor"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Verifica saúde do provedor"""
        pass


class Dialog360Connector(ProviderConnector):
    """Conector para 360Dialog (WhatsApp)"""
    
    def __init__(self, credentials: Dict[str, Any], base_url: Optional[str] = None):
        super().__init__(credentials, base_url or "https://waba.360dialog.io/v1")
    
    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        start = datetime.now()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "to": to_number,
                    "type": "template",
                    "template": {
                        "name": template_id,
                        "language": {"code": variables.get("language", "en")},
                        "components": self._build_components(variables)
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "Authorization": f"Bearer {self.credentials.get('access_token')}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                latency_ms = int((datetime.now() - start).total_seconds() * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "provider_message_id": data.get("messages", [{}])[0].get("id"),
                        "latency_ms": latency_ms,
                        "response": data
                    }
                else:
                    return {
                        "success": False,
                        "error_code": str(response.status_code),
                        "error_message": response.text,
                        "latency_ms": latency_ms
                    }
        
        except Exception as e:
            logger.error(f"360Dialog send error: {str(e)}")
            return {
                "success": False,
                "error_code": "CONNECTOR_ERROR",
                "error_message": str(e),
                "latency_ms": int((datetime.now() - start).total_seconds() * 1000)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/configs/webhook",
                    headers={"Authorization": f"Bearer {self.credentials.get('access_token')}"}
                )
                
                return {
                    "healthy": response.status_code == 200,
                    "status_code": response.status_code,
                    "latency_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
    
    def _build_components(self, variables: Dict[str, Any]) -> list:
        """Constrói componentes do template"""
        components = []
        
        if variables.get("body_params"):
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in variables["body_params"]]
            })
        
        return components


class GupshupConnector(ProviderConnector):
    """Conector para Gupshup (WhatsApp)"""
    
    def __init__(self, credentials: Dict[str, Any], base_url: Optional[str] = None):
        super().__init__(credentials, base_url or "https://api.gupshup.io/sm/api/v1")
    
    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        start = datetime.now()
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "channel": "whatsapp",
                    "source": self.credentials.get("source_number"),
                    "destination": to_number,
                    "message": {
                        "type": "template",
                        "template": {
                            "id": template_id,
                            "params": variables.get("body_params", [])
                        }
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/template/msg",
                    headers={
                        "apikey": self.credentials.get("api_key"),
                        "Content-Type": "application/json"
                    },
                    json=payload
                )
                
                latency_ms = int((datetime.now() - start).total_seconds() * 1000)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": data.get("status") == "submitted",
                        "provider_message_id": data.get("messageId"),
                        "latency_ms": latency_ms,
                        "response": data
                    }
                else:
                    return {
                        "success": False,
                        "error_code": str(response.status_code),
                        "error_message": response.text,
                        "latency_ms": latency_ms
                    }
        
        except Exception as e:
            logger.error(f"Gupshup send error: {str(e)}")
            return {
                "success": False,
                "error_code": "CONNECTOR_ERROR",
                "error_message": str(e),
                "latency_ms": int((datetime.now() - start).total_seconds() * 1000)
            }
    
    async def health_check(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/users/{self.credentials.get('app_name')}",
                    headers={"apikey": self.credentials.get("api_key")}
                )
                
                return {
                    "healthy": response.status_code == 200,
                    "status_code": response.status_code,
                    "latency_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0
                }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }


class SandboxProviderConnector(ProviderConnector):
    """Conector fake usado quando SANDBOX_PROVIDERS estiver habilitado."""

    def __init__(self, provider_name: str, credentials: Dict[str, Any], base_url: Optional[str] = None):
        super().__init__(credentials, base_url)
        self.provider_name = provider_name

    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        latency_ms = max(settings.SANDBOX_LATENCY_MS, 0)
        if latency_ms:
            await asyncio.sleep(latency_ms / 1000)

        fingerprint = self._build_fingerprint(to_number, template_id, variables)
        should_fail = self._should_fail(fingerprint)

        response_payload = {
            "provider": self.provider_name,
            "template_id": template_id,
            "to": to_number,
            "variables": variables,
            "mode": "sandbox",
        }

        if should_fail:
            return {
                "success": False,
                "error_code": "SANDBOX_FAILURE",
                "error_message": "Sandbox configured failure",
                "latency_ms": latency_ms,
                "response": response_payload,
            }

        provider_message_id = f"sndbx-{fingerprint[:12]}"
        return {
            "success": True,
            "provider_message_id": provider_message_id,
            "latency_ms": latency_ms,
            "response": {
                **response_payload,
                "provider_message_id": provider_message_id,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        latency_ms = max(settings.SANDBOX_LATENCY_MS, 0)
        if latency_ms:
            await asyncio.sleep(latency_ms / 1000)

        return {
            "healthy": True,
            "status_code": 200,
            "latency_ms": latency_ms,
            "mode": "sandbox",
        }

    def _build_fingerprint(self, to_number: str, template_id: str, variables: Dict[str, Any]) -> str:
        serialized = json.dumps({
            "provider": self.provider_name,
            "to": to_number,
            "template_id": template_id,
            "variables": variables,
        }, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _should_fail(self, fingerprint: str) -> bool:
        failure_rate = min(max(settings.SANDBOX_FAILURE_RATE, 0.0), 1.0)
        if failure_rate == 0:
            return False

        sample = int(fingerprint[:8], 16) / 0xFFFFFFFF
        return sample < failure_rate


def get_connector(provider_name: str, credentials: Dict[str, Any], base_url: Optional[str] = None) -> ProviderConnector:
    """Factory para obter conector apropriado respeitando o modo sandbox"""

    if settings.SANDBOX_PROVIDERS:
        return SandboxProviderConnector(provider_name, credentials, base_url)

    connectors = {
        "360dialog": Dialog360Connector,
        "gupshup": GupshupConnector
    }

    connector_key = provider_name.lower()
    connector_class = connectors.get(connector_key)
    if not connector_class:
        raise ValueError(f"Unknown provider: {provider_name}")

    return connector_class(credentials, base_url)
