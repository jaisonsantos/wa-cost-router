import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import Providers from "@/pages/Providers";
import { Provider } from "@/types/api";

const useProvidersMock = vi.fn();
const useSetProviderCredentialsMock = vi.fn();
const useHealthCheckProviderMock = vi.fn();
const { toastMock } = vi.hoisted(() => ({ toastMock: vi.fn() }));

vi.mock("@/hooks/useApi", () => ({
  useProviders: () => useProvidersMock(),
  useSetProviderCredentials: () => useSetProviderCredentialsMock(),
  useHealthCheckProvider: () => useHealthCheckProviderMock(),
  useCreateBillingPortal: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/hooks/use-toast", () => ({
  toast: toastMock,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { email: "admin@demo.local" },
    logout: vi.fn(),
  }),
}));

const renderProviders = () =>
  render(
    <MemoryRouter>
      <Providers />
    </MemoryRouter>,
  );

const twilioProvider: Provider = {
  id: "twilio-1",
  name: "Twilio Sandbox",
  type: "sms",
  status: "active",
  is_configured: false,
  has_credentials: false,
  avg_latency_ms: null,
  metadata: {
    provider: "twilio",
    channels: {
      sms: { inbound_numbers: [] },
    },
    compliance: {
      registrations: ["Registre 10DLC antes de sair do sandbox."],
    },
  },
  required_fields: ["account_sid", "auth_token", "from_number"],
  provider_form_schema: {
    title: "Twilio SMS Sandbox",
    fields: [
      {
        key: "account_sid",
        label: "Account SID",
        type: "text",
        required: true,
        validation: {
          regex: "^AC[a-fA-F0-9]{32}$",
          message: "Account SID inválido.",
        },
      },
      {
        key: "auth_token",
        label: "Auth Token",
        type: "password",
        required: true,
        validation: {
          regex: "^[A-Za-z0-9]{16,64}$",
          message: "Auth Token deve conter 16-64 caracteres.",
        },
      },
      {
        key: "from_number",
        label: "Número remetente (E.164)",
        type: "tel",
        mask: "+###############",
        required: true,
        validation: {
          regex: "^\\+[1-9]\\d{7,14}$",
          message: "Informe um telefone em formato E.164.",
        },
      },
    ],
    consent_guidance: ["Certifique-se do opt-in documentado."],
  },
};

const sendgridProvider: Provider = {
  id: "sendgrid-1",
  name: "SendGrid Sandbox",
  type: "email",
  status: "active",
  is_configured: true,
  has_credentials: true,
  avg_latency_ms: null,
  metadata: {
    provider: "sendgrid",
    compliance: {
      dns: ["Configure SPF e DKIM."],
      consent: ["Mantenha listas de supressão em dia."],
    },
  },
  required_fields: ["api_key", "from_email", "webhook_token", "inbound_signing_secret"],
  provider_form_schema: {
    title: "SendGrid Sandbox",
    fields: [
      {
        key: "api_key",
        label: "API Key",
        type: "password",
        required: true,
        validation: {
          regex: "^SG\\.[A-Za-z0-9_-]{16,128}$",
          message: "API Key inválida.",
        },
      },
      {
        key: "from_email",
        label: "Remetente padrão",
        type: "email",
        required: true,
        validation: {
          regex: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$",
          message: "E-mail inválido.",
        },
      },
      {
        key: "webhook_token",
        label: "Token de webhook",
        type: "text",
        required: true,
        validation: {
          regex: "^[A-Za-z0-9_\\-]{12,128}$",
          message: "Token inválido.",
        },
      },
      {
        key: "inbound_signing_secret",
        label: "Assinatura inbound (Signing Secret)",
        type: "password",
        required: true,
        validation: {
          regex: "^[A-Za-z0-9]{16,128}$",
          message: "Segredo inválido.",
        },
      },
    ],
    consent_guidance: ["Utilize double opt-in."],
    testing_instructions: ["Teste o Event Webhook."],
  },
};

describe("Providers page", () => {
  beforeEach(() => {
    useProvidersMock.mockReset();
    useSetProviderCredentialsMock.mockReset();
    useHealthCheckProviderMock.mockReset();
    toastMock.mockReset();

    useHealthCheckProviderMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useSetProviderCredentialsMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
  });

  it("renders dynamic Twilio form with validation and mask", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ status: "credentials_saved" });
    useSetProviderCredentialsMock.mockReturnValue({ mutateAsync, isPending: false });
    useProvidersMock.mockReturnValue({ data: [twilioProvider], isLoading: false });

    renderProviders();

    await userEvent.click(screen.getByRole("button", { name: /Configurar/i }));

    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findAllByText(/obrigatório/i)).toHaveLength(3);
    expect(mutateAsync).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Account SID"), "AC" + "1".repeat(32));
    await userEvent.type(screen.getByLabelText("Auth Token"), "A".repeat(16));
    const fromNumberInput = screen.getByLabelText("Número remetente (E.164)") as HTMLInputElement;
    await userEvent.type(fromNumberInput, "15558675309");
    expect(fromNumberInput.value).toBe("+15558675309");

    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        providerId: "twilio-1",
        credentials: {
          account_sid: "AC" + "1".repeat(32),
          auth_token: "A".repeat(16),
          from_number: "+15558675309",
        },
      });
    });
  });

  it("displays consent guidance for SendGrid and validates email", async () => {
    const mutateAsync = vi.fn().mockResolvedValue({ status: "credentials_saved" });
    useSetProviderCredentialsMock.mockReturnValue({ mutateAsync, isPending: false });
    useProvidersMock.mockReturnValue({ data: [sendgridProvider], isLoading: false });

    renderProviders();

    await userEvent.click(screen.getByRole("button", { name: /Configurar/i }));
    expect(screen.getByText("Diretrizes de consentimento")).toBeInTheDocument();
    expect(screen.getByText("Utilize double opt-in.")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("API Key"), "SG.invalid");
    await userEvent.type(screen.getByLabelText("Remetente padrão"), "invalid-email");
    await userEvent.type(screen.getByLabelText("Token de webhook"), "token-123");
    await userEvent.type(screen.getByLabelText("Assinatura inbound (Signing Secret)"), "short");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    expect(await screen.findByText(/API Key inválida/)).toBeInTheDocument();
    expect(await screen.findByText(/E-mail inválido/)).toBeInTheDocument();
    expect(mutateAsync).not.toHaveBeenCalled();

    await userEvent.clear(screen.getByLabelText("API Key"));
    await userEvent.type(screen.getByLabelText("API Key"), "SG." + "a".repeat(20));
    await userEvent.clear(screen.getByLabelText("Remetente padrão"));
    await userEvent.type(screen.getByLabelText("Remetente padrão"), "noreply@example.com");
    await userEvent.clear(screen.getByLabelText("Token de webhook"));
    await userEvent.type(screen.getByLabelText("Token de webhook"), "token-123456");
    await userEvent.clear(screen.getByLabelText("Assinatura inbound (Signing Secret)"));
    await userEvent.type(screen.getByLabelText("Assinatura inbound (Signing Secret)"), "A".repeat(24));

    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledWith({
        providerId: "sendgrid-1",
        credentials: {
          api_key: "SG." + "a".repeat(20),
          from_email: "noreply@example.com",
          webhook_token: "token-123456",
          inbound_signing_secret: "A".repeat(24),
        },
      });
    });
  });
});

