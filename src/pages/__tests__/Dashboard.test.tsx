import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";

const useDashboardMetricsMock = vi.fn();
const useProviderMetricsMock = vi.fn();
const useChannelMetricsMock = vi.fn();
const useQueueMetricsMock = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { email: "admin@demo.local" },
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useApi", () => ({
  useDashboardMetrics: () => useDashboardMetricsMock(),
  useProviderMetrics: () => useProviderMetricsMock(),
  useChannelMetrics: () => useChannelMetricsMock(),
  useQueueMetrics: () => useQueueMetricsMock(),
}));

const renderDashboard = () =>
  render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>,
  );

describe("Dashboard", () => {
  beforeEach(() => {
    useDashboardMetricsMock.mockReset();
    useProviderMetricsMock.mockReset();
    useChannelMetricsMock.mockReset();
    useQueueMetricsMock.mockReset();
  });

  it("renders dashboard metrics when data is available", () => {
    useDashboardMetricsMock.mockReturnValue({
      data: {
        total_messages: 1200,
        total_cost_minor: 150000,
        baseline_cost_minor: 200000,
        saved_minor: 50000,
        success_rate: 97.5,
        avg_latency_ms: 1800,
        top_countries: [
          { country: "BR", cost_minor: 90000, count: 600 },
          { country: "US", cost_minor: 30000, count: 200 },
        ],
        top_templates: [
          { template: "welcome", category: "marketing", cost_minor: 40000, count: 300 },
        ],
        alerts: [
          { type: "warning", message: "Latência alta" },
        ],
        recommendations: ["Aumente fallback em BR"],
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    useProviderMetricsMock.mockReturnValue({
      data: [
        {
          provider_id: "1",
          provider_name: "Meta",
          total_sent: 800,
          success_rate: 98,
          avg_latency_ms: 1500,
          total_cost_minor: 110000,
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    useChannelMetricsMock.mockReturnValue({
      data: [
        {
          channel: "whatsapp",
          conversations_opened: 128,
          conversations_closed: 110,
          backlog: { open: 5, pending: 3, closed: 110 },
          first_response: { average_seconds: 38, sample_size: 110 },
          sla: { target_seconds: 60, within_target: 102, total_tracked: 110, compliance_rate: 92 },
        },
        {
          channel: "email",
          conversations_opened: 90,
          conversations_closed: 70,
          backlog: { open: 14, pending: 5, closed: 70 },
          first_response: { average_seconds: 95, sample_size: 70 },
          sla: { target_seconds: 60, within_target: 48, total_tracked: 70, compliance_rate: 68 },
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    useQueueMetricsMock.mockReturnValue({
      data: [
        {
          channel: "whatsapp",
          backlog: { open: 5, responded: 2, closed: 110, total: 117 },
          first_response: { average_seconds: 40, sample_size: 110 },
          sla: { target_seconds: 60, within_target: 102, total_tracked: 110, compliance_rate: 92 },
        },
        {
          channel: "email",
          backlog: { open: 16, responded: 6, closed: 70, total: 92 },
          first_response: { average_seconds: 95, sample_size: 70 },
          sla: { target_seconds: 60, within_target: 48, total_tracked: 70, compliance_rate: 68 },
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderDashboard();

    expect(screen.getByText("Economia Total (período)")).toBeInTheDocument();
    expect(screen.getAllByText("€500.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Mensagens Processadas")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("BR")).toBeInTheDocument();
    expect(screen.getByText("Meta")).toBeInTheDocument();
    expect(screen.getByText("Aumente fallback em BR")).toBeInTheDocument();
    expect(screen.getByText("Saúde por Canal")).toBeInTheDocument();
    expect(screen.getByText("Monitorando 2 canais")).toBeInTheDocument();
    expect(screen.getAllByText("Whatsapp").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Email").length).toBeGreaterThan(0);
    expect(screen.getByText("Email está com apenas 68.0% dentro do SLA.")).toBeInTheDocument();
    expect(
      screen.getByText("Tempo médio de primeira resposta (95s) excede a meta de 60s."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Email acumula 16 conversas abertas aguardando atendimento."),
    ).toBeInTheDocument();
  });

  it("renders loading skeleton while metrics are loading", () => {
    useDashboardMetricsMock.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
      error: null,
    });

    useProviderMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    useChannelMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    useQueueMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    const { container } = renderDashboard();

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("shows an error state when dashboard metrics fail", () => {
    useDashboardMetricsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      error: new Error("timeout"),
    });

    useProviderMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    useChannelMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    useQueueMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderDashboard();

    expect(
      screen.getByText("Não foi possível carregar as métricas do dashboard"),
    ).toBeInTheDocument();
    expect(screen.getByText("timeout")).toBeInTheDocument();
  });

  it("renders channel specific alerts with correct severity based on SLA and backlog", () => {
    useDashboardMetricsMock.mockReturnValue({
      data: {
        total_messages: 0,
        total_cost_minor: 0,
        baseline_cost_minor: 0,
        saved_minor: 0,
        success_rate: 98,
        avg_latency_ms: 1200,
        top_countries: [],
        top_templates: [],
        alerts: [],
        recommendations: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    useProviderMetricsMock.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
      error: null,
    });

    useChannelMetricsMock.mockReturnValue({
      data: [
        {
          channel: "sms",
          conversations_opened: 80,
          conversations_closed: 74,
          backlog: { open: 6, pending: 2, closed: 74 },
          first_response: { average_seconds: 62, sample_size: 74 },
          sla: { target_seconds: 60, within_target: 58, total_tracked: 74, compliance_rate: 82 },
        },
        {
          channel: "email",
          conversations_opened: 95,
          conversations_closed: 70,
          backlog: { open: 10, pending: 5, closed: 70 },
          first_response: { average_seconds: 91, sample_size: 70 },
          sla: { target_seconds: 60, within_target: 45, total_tracked: 70, compliance_rate: 65 },
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    useQueueMetricsMock.mockReturnValue({
      data: [
        {
          channel: "sms",
          backlog: { open: 9, responded: 3, closed: 74, total: 86 },
          first_response: { average_seconds: 59, sample_size: 74 },
          sla: { target_seconds: 60, within_target: 58, total_tracked: 74, compliance_rate: 82 },
        },
        {
          channel: "email",
          backlog: { open: 16, responded: 6, closed: 70, total: 92 },
          first_response: { average_seconds: 91, sample_size: 70 },
          sla: { target_seconds: 60, within_target: 45, total_tracked: 70, compliance_rate: 65 },
        },
      ],
      isLoading: false,
      isError: false,
      error: null,
    });

    renderDashboard();

    expect(screen.getByText("Alertas por canal")).toBeInTheDocument();
    expect(
      screen.getByText("Sms apresenta queda de SLA (82.0%)."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Sms possui 9 conversas abertas no backlog."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Email está com apenas 65.0% dentro do SLA."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Tempo médio de primeira resposta (91s) excede a meta de 60s."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Email acumula 16 conversas abertas aguardando atendimento."),
    ).toBeInTheDocument();

    const warningBadges = screen.getAllByText("Atenção");
    const criticalBadges = screen.getAllByText("Crítico");

    expect(warningBadges.length).toBeGreaterThan(0);
    expect(criticalBadges.length).toBeGreaterThan(0);
  });
});

