from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
import logging
from datetime import datetime

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


def get_connector(provider_name: str, credentials: Dict[str, Any], base_url: Optional[str] = None) -> ProviderConnector:
    """Factory para obter conector apropriado"""
    connectors = {
        "360dialog": Dialog360Connector,
        "gupshup": GupshupConnector
    }
    
    connector_class = connectors.get(provider_name.lower())
    if not connector_class:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    return connector_class(credentials, base_url)
