from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import asyncio
import hashlib
import json
import logging
from datetime import datetime
import uuid

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

    def __init__(
        self,
        provider_name: str,
        credentials: Dict[str, Any],
        base_url: Optional[str] = None,
        *,
        latency_ms: Optional[int] = None,
        failure_rate: Optional[float] = None,
    ):
        super().__init__(credentials, base_url)
        self.provider_name = provider_name
        self._latency_override = latency_ms
        self._failure_rate_override = failure_rate

    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        latency_ms = self._resolve_latency_ms()
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
        latency_ms = self._resolve_latency_ms()
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
        failure_rate = self._resolve_failure_rate()
        if failure_rate == 0:
            return False

        sample = int(fingerprint[:8], 16) / 0xFFFFFFFF
        return sample < failure_rate

    def _resolve_latency_ms(self) -> int:
        if self._latency_override is not None:
            raw_value = self._latency_override
        else:
            raw_value = settings.SANDBOX_LATENCY_MS
        try:
            latency_ms = int(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid SANDBOX_LATENCY_MS value %r; defaulting to 0 ms",
                raw_value,
            )
            return 0

        return max(latency_ms, 0)

    def _resolve_failure_rate(self) -> float:
        if self._failure_rate_override is not None:
            raw_value = self._failure_rate_override
        else:
            raw_value = settings.SANDBOX_FAILURE_RATE
        try:
            failure_rate = float(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid SANDBOX_FAILURE_RATE value %r; defaulting to 0.0",
                raw_value,
            )
            return 0.0

        return min(max(failure_rate, 0.0), 1.0)


class TwilioConnector(ProviderConnector):
    """Conector para envio de SMS via Twilio."""

    def __init__(
        self,
        credentials: Dict[str, Any],
        base_url: Optional[str] = None,
        *,
        transport: Optional[httpx.BaseTransport] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        default_base_url = base_url or "https://api.twilio.com/2010-04-01"
        super().__init__(credentials, default_base_url)
        self._transport = transport
        self._http_client = http_client

    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        start = datetime.now()
        account_sid, auth_token = self._resolve_auth()
        payload = self._build_payload(to_number, variables or {})

        try:
            async with self._get_client(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/Accounts/{account_sid}/Messages.json",
                    data=payload,
                    auth=(account_sid, auth_token),
                )

            latency_ms = int((datetime.now() - start).total_seconds() * 1000)
            if response.status_code in (200, 201, 202):
                data = response.json()
                return {
                    "success": True,
                    "provider_message_id": data.get("sid"),
                    "latency_ms": latency_ms,
                    "response": data,
                }

            error_message = self._extract_error_message(response)
            return {
                "success": False,
                "error_code": str(response.status_code),
                "error_message": error_message,
                "latency_ms": latency_ms,
                "response": self._safe_response_json(response),
            }
        except Exception as exc:
            logger.error("Twilio send error: %s", exc)
            return {
                "success": False,
                "error_code": "CONNECTOR_ERROR",
                "error_message": str(exc),
                "latency_ms": int((datetime.now() - start).total_seconds() * 1000),
            }

    async def health_check(self) -> Dict[str, Any]:
        start = datetime.now()
        account_sid, auth_token = self._resolve_auth()
        try:
            async with self._get_client(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/Accounts/{account_sid}.json",
                    auth=(account_sid, auth_token),
                )

            latency_ms = int((datetime.now() - start).total_seconds() * 1000)
            payload = self._safe_response_json(response)
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "response": payload,
            }
        except Exception as exc:
            logger.error("Twilio health check error: %s", exc)
            return {
                "healthy": False,
                "error": str(exc),
            }

    def _resolve_auth(self) -> tuple[str, str]:
        account_sid = (self.credentials or {}).get("account_sid")
        auth_token = (self.credentials or {}).get("auth_token")
        if not account_sid or not auth_token:
            raise ValueError("Twilio credentials must include account_sid and auth_token")
        return account_sid, auth_token

    def _build_payload(self, to_number: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        if not to_number:
            raise ValueError("Recipient phone number is required for Twilio SMS")

        from_number = variables.get("from_number") or (self.credentials or {}).get("from_number")
        messaging_service_sid = (
            variables.get("messaging_service_sid")
            or (self.credentials or {}).get("messaging_service_sid")
        )
        if not from_number and not messaging_service_sid:
            raise ValueError("Twilio requires from_number or messaging_service_sid")

        body = (
            variables.get("body")
            or variables.get("text")
            or variables.get("message")
            or variables.get("content")
        )
        if not body:
            raise ValueError("Twilio SMS payload must include message body")

        payload: Dict[str, Any] = {
            "To": to_number,
            "Body": body,
        }

        if from_number:
            payload["From"] = from_number
        if messaging_service_sid:
            payload["MessagingServiceSid"] = messaging_service_sid

        status_callback = variables.get("status_callback")
        if status_callback:
            payload["StatusCallback"] = status_callback

        return payload

    @asynccontextmanager
    async def _get_client(self, *, timeout: float):
        if self._http_client is not None:
            yield self._http_client
            return

        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            yield client

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            data = response.json()
        except json.JSONDecodeError:
            return response.text

        message = data.get("message") or data.get("detail")
        if message:
            return str(message)
        return response.text or "Unknown Twilio error"

    @staticmethod
    def _safe_response_json(response: httpx.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"raw": response.text}
        return payload


class SendGridConnector(ProviderConnector):
    """Conector para envio de e-mails via SendGrid"""

    def __init__(
        self,
        credentials: Dict[str, Any],
        base_url: Optional[str] = None,
        *,
        transport: Optional[httpx.BaseTransport] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        default_base_url = getattr(settings, "SENDGRID_BASE_URL", "https://api.sendgrid.com/v3")
        super().__init__(credentials, base_url or default_base_url)
        self._transport = transport
        self._http_client = http_client

    async def send_message(
        self,
        to_number: str,
        template_id: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        start = datetime.now()
        recipient = (to_number or "").strip()
        if not recipient:
            raise ValueError("Recipient email is required for SendGridConnector")

        try:
            payload = self._build_payload(recipient, template_id, variables or {})
            headers = self._build_headers()

            async with self._get_client(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/mail/send",
                    headers=headers,
                    json=payload,
                )

            latency_ms = int((datetime.now() - start).total_seconds() * 1000)
            if response.status_code in (200, 202):
                provider_message_id = response.headers.get("X-Message-Id") or self._generate_message_id()
                response_payload: Dict[str, Any]
                try:
                    response_payload = response.json()
                except json.JSONDecodeError:
                    response_payload = {}
                return {
                    "success": True,
                    "provider_message_id": provider_message_id,
                    "latency_ms": latency_ms,
                    "response": response_payload,
                }

            error_message = self._extract_error_message(response)
            return {
                "success": False,
                "error_code": str(response.status_code),
                "error_message": error_message,
                "latency_ms": latency_ms,
                "response": self._safe_response_json(response),
            }
        except Exception as exc:
            logger.error("SendGrid send error: %s", exc)
            return {
                "success": False,
                "error_code": "CONNECTOR_ERROR",
                "error_message": str(exc),
                "latency_ms": int((datetime.now() - start).total_seconds() * 1000),
            }

    async def health_check(self) -> Dict[str, Any]:
        start = datetime.now()
        try:
            async with self._get_client(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/user/account",
                    headers=self._build_headers(),
                )

            latency_ms = int((datetime.now() - start).total_seconds() * 1000)
            payload = self._safe_response_json(response)
            return {
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "response": payload,
            }
        except Exception as exc:
            logger.error("SendGrid health check error: %s", exc)
            return {
                "healthy": False,
                "error": str(exc),
            }

    @asynccontextmanager
    async def _get_client(self, *, timeout: float):
        if self._http_client is not None:
            yield self._http_client
            return

        async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as client:
            yield client

    def _build_headers(self) -> Dict[str, str]:
        api_key = (
            (self.credentials or {}).get("api_key")
            or getattr(settings, "SENDGRID_API_KEY", None)
        )
        if not api_key:
            raise ValueError("SendGrid API key is required")

        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, recipient: str, template_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        from_email = variables.get("from_email") or (self.credentials or {}).get("from_email")
        if not from_email:
            from_email = getattr(settings, "SENDGRID_DEFAULT_SENDER_EMAIL", None)
        if not from_email:
            raise ValueError("Sender email is required for SendGridConnector")

        personalization: Dict[str, Any] = {
            "to": [{"email": recipient}],
        }

        dynamic_template_data = variables.get("dynamic_template_data")
        if dynamic_template_data is None:
            reserved_keys = {
                "from_email",
                "subject",
                "html_content",
                "text_content",
                "dynamic_template_data",
            }
            dynamic_template_data = {
                key: value for key, value in variables.items() if key not in reserved_keys
            }

        if dynamic_template_data:
            personalization["dynamic_template_data"] = dynamic_template_data

        payload: Dict[str, Any] = {
            "personalizations": [personalization],
            "from": {"email": from_email},
        }

        if template_id:
            payload["template_id"] = template_id

        subject = variables.get("subject")
        if subject:
            payload["subject"] = subject

        content_blocks = []
        html_content = variables.get("html_content") or variables.get("content_html")
        if html_content:
            content_blocks.append({"type": "text/html", "value": html_content})

        text_content = variables.get("text_content")
        if text_content:
            content_blocks.append({"type": "text/plain", "value": text_content})

        if content_blocks:
            payload["content"] = content_blocks

        return payload

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            data = response.json()
        except json.JSONDecodeError:
            return response.text

        errors = data.get("errors")
        if isinstance(errors, list) and errors:
            first_error = errors[0]
            if isinstance(first_error, dict):
                message = first_error.get("message") or first_error.get("detail")
                if message:
                    return str(message)
            return str(first_error)
        return response.text or "Unknown SendGrid error"

    @staticmethod
    def _safe_response_json(response: httpx.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            payload = {"raw": response.text}
        return payload

    @staticmethod
    def _generate_message_id() -> str:
        return f"sg-{uuid.uuid4().hex[:12]}"


def get_connector(
    provider_name: str,
    credentials: Dict[str, Any],
    base_url: Optional[str] = None,
    *,
    provider_type: Optional[str] = None,
    sandbox_options: Optional[Dict[str, Any]] = None,
) -> ProviderConnector:
    """Factory para obter conector apropriado respeitando o modo sandbox"""

    if settings.SANDBOX_PROVIDERS:
        sandbox_options = sandbox_options or {}
        return SandboxProviderConnector(
            provider_name,
            credentials,
            base_url,
            latency_ms=sandbox_options.get("latency_ms"),
            failure_rate=sandbox_options.get("failure_rate"),
        )

    connectors = {
        "360dialog": Dialog360Connector,
        "gupshup": GupshupConnector,
        "sendgrid": SendGridConnector,
        "email": SendGridConnector,
        "twilio": TwilioConnector,
        "sms": TwilioConnector,
    }

    lookup_keys = []
    if provider_type:
        lookup_keys.append(provider_type.lower())
    if provider_name:
        lookup_keys.append(provider_name.lower())

    for key in lookup_keys:
        connector_class = connectors.get(key)
        if connector_class:
            return connector_class(credentials, base_url)

    raise ValueError(f"Unknown provider: {provider_name}")


async def run_health_check(
    provider_name: str,
    credentials: Dict[str, Any],
    base_url: Optional[str] = None,
    *,
    provider_type: Optional[str] = None,
    sandbox_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Helper to execute connector health checks with factory resolution."""

    connector = get_connector(
        provider_name,
        credentials,
        base_url,
        provider_type=provider_type,
        sandbox_options=sandbox_options,
    )
    return await connector.health_check()
