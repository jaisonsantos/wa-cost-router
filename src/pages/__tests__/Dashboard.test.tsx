import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "@/pages/Dashboard";

const useDashboardMetricsMock = vi.fn();
const useProviderMetricsMock = vi.fn();

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

    renderDashboard();

    expect(screen.getByText("Economia Total (período)")).toBeInTheDocument();
    expect(screen.getAllByText("€500.00").length).toBeGreaterThan(0);
    expect(screen.getByText("Mensagens Processadas")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
    expect(screen.getByText("BR")).toBeInTheDocument();
    expect(screen.getByText("Meta")).toBeInTheDocument();
    expect(screen.getByText("Aumente fallback em BR")).toBeInTheDocument();
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

    renderDashboard();

    expect(
      screen.getByText("Não foi possível carregar as métricas do dashboard"),
    ).toBeInTheDocument();
    expect(screen.getByText("timeout")).toBeInTheDocument();
  });
});

