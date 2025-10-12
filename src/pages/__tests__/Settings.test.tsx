import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Settings from "@/pages/Settings";

const useRatesMock = vi.fn();
const useCurrentOrgMock = vi.fn();
const useImportRatesCSVMock = vi.fn();
const useCreateWAConnectionMock = vi.fn();
const useConnectionsMock = vi.fn();
const useTestConnectionMock = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { email: "admin@demo.local" },
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useApi", () => ({
  useRates: () => useRatesMock(),
  useCurrentOrg: () => useCurrentOrgMock(),
  useImportRatesCSV: () => useImportRatesCSVMock(),
  useCreateWAConnection: () => useCreateWAConnectionMock(),
  useConnections: () => useConnectionsMock(),
  useTestConnection: () => useTestConnectionMock(),
}));

const renderSettings = () =>
  render(
    <MemoryRouter>
      <Settings />
    </MemoryRouter>,
  );

describe("Settings connections", () => {
  beforeEach(() => {
    useRatesMock.mockReturnValue({ data: [], isLoading: false });
    useCurrentOrgMock.mockReturnValue({
      data: { id: "org-1", name: "Demo Org", user_email: "admin@demo.local", role: "owner" },
      isLoading: false,
    });
    useImportRatesCSVMock.mockReturnValue({ mutateAsync: vi.fn() });
    useCreateWAConnectionMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useTestConnectionMock.mockReturnValue({ mutate: vi.fn(), isPending: false, variables: undefined });
    useConnectionsMock.mockReset();
  });

  it("renders loading state for connection statuses", () => {
    useConnectionsMock.mockReturnValue({ data: undefined, isLoading: true, error: null });

    renderSettings();

    expect(screen.getAllByText("Carregando").length).toBeGreaterThan(0);
  });

  it("displays badges for healthy, warning, and error statuses", () => {
    const now = new Date().toISOString();
    useConnectionsMock.mockReturnValue({
      data: [
        {
          id: "wa-1",
          channel: "whatsapp",
          display_name: "WhatsApp",
          status: "healthy",
          connected: true,
          has_credentials: true,
          metadata: { business_id: "biz", phone_id: "phone" },
          last_health_check: { healthy: true, checked_at: now },
        },
        {
          id: "email-1",
          channel: "email",
          display_name: "Email",
          status: "warning",
          connected: true,
          has_credentials: true,
          metadata: { provider_name: "SendGrid", provider_id: "email-1" },
          last_health_check: { healthy: true, status_code: 299, checked_at: now },
        },
        {
          id: "sms-1",
          channel: "sms",
          display_name: "SMS",
          status: "error",
          connected: true,
          has_credentials: true,
          metadata: { provider_name: "Twilio", provider_id: "sms-1" },
          last_health_check: { healthy: false, error: "Timeout", checked_at: now },
        },
        {
          id: "tg-1",
          channel: "telegram",
          display_name: "Telegram",
          status: "disconnected",
          connected: false,
          has_credentials: false,
          metadata: {},
          last_health_check: null,
        },
      ],
      isLoading: false,
      error: null,
    });

    renderSettings();

    expect(screen.getByText("Saudável")).toBeInTheDocument();
    expect(screen.getByText("Atenção")).toBeInTheDocument();
    expect(screen.getByText("Falha")).toBeInTheDocument();
    expect(screen.getAllByText("Desconectado").length).toBeGreaterThan(0);
    expect(screen.getByText(/Erro: Timeout/)).toBeInTheDocument();
    expect(screen.getByText("Testar Email")).toBeInTheDocument();
  });

  it("shows error banner when connections fetch fails", () => {
    useConnectionsMock.mockReturnValue({ data: [], isLoading: false, error: new Error("Falha ao carregar") });

    renderSettings();

    expect(screen.getByText("Falha ao carregar")).toBeInTheDocument();
  });
});
