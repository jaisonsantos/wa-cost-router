import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Rules from "@/pages/Rules";

const useRulesMock = vi.fn();
const useToggleRuleMock = vi.fn();
const useSimulateRulesMock = vi.fn();
const useCreateRuleMock = vi.fn();
const useUpdateRuleMock = vi.fn();
const useProvidersMock = vi.fn();
const useDashboardMetricsMock = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { email: "admin@demo.local" },
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useApi", () => ({
  useRules: () => useRulesMock(),
  useToggleRule: () => useToggleRuleMock(),
  useSimulateRules: () => useSimulateRulesMock(),
  useCreateRule: () => useCreateRuleMock(),
  useUpdateRule: () => useUpdateRuleMock(),
  useProviders: () => useProvidersMock(),
  useDashboardMetrics: () => useDashboardMetricsMock(),
  useCreateBillingPortal: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("@/components/AdvancedSimulator", () => ({
  __esModule: true,
  default: () => <div data-testid="advanced-simulator" />,
}));

vi.mock("@/components/RuleFormDialog", () => ({
  __esModule: true,
  default: () => <div data-testid="rule-form-dialog" />,
}));

const renderRules = () =>
  render(
    <MemoryRouter>
      <Rules />
    </MemoryRouter>,
  );

describe("Rules page", () => {
  beforeEach(() => {
    useRulesMock.mockReset();
    useToggleRuleMock.mockReset();
    useSimulateRulesMock.mockReset();
    useCreateRuleMock.mockReset();
    useUpdateRuleMock.mockReset();
    useProvidersMock.mockReset();
    useDashboardMetricsMock.mockReset();
  });

  it("renders quick simulation results using backend data", () => {
    const simulateMutate = vi.fn();

    useRulesMock.mockReturnValue({
      data: [
        {
          id: "rule-1",
          name: "Regra BR",
          is_enabled: true,
          priority: 10,
          conditions: [],
          actions: {},
        },
      ],
      isLoading: false,
    });

    useProvidersMock.mockReturnValue({ data: [] });

    useDashboardMetricsMock.mockReturnValue({
      data: {
        top_countries: [
          { country: "BR", cost_minor: 90000, count: 300 },
          { country: "US", cost_minor: 60000, count: 150 },
        ],
        top_templates: [
          { template: "promo", category: "Marketing", cost_minor: 40000, count: 200 },
        ],
        total_messages: 450,
      },
    });

    useSimulateRulesMock.mockReturnValue({
      mutate: simulateMutate,
      mutateAsync: vi.fn().mockResolvedValue({ baseline: 150000, optimized: 100000, saved: 50000 }),
      data: { baseline: 150000, optimized: 100000, saved: 50000 },
      isPending: false,
      isError: false,
      error: null,
    });

    useToggleRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCreateRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    renderRules();

    expect(simulateMutate).toHaveBeenCalledWith({
      countries: ["BR", "US"],
      volumes: { BR: 300, US: 150 },
      category: "marketing",
    });

    expect(screen.getAllByText("€500.00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("450").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/33\.3%/).length).toBeGreaterThan(0);
    expect(screen.getByTestId("advanced-simulator")).toBeInTheDocument();
  });

  it("renders loading state when rules are loading", () => {
    useRulesMock.mockReturnValue({ data: undefined, isLoading: true });
    useProvidersMock.mockReturnValue({ data: [] });
    useDashboardMetricsMock.mockReturnValue({ data: undefined });
    useSimulateRulesMock.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      data: undefined,
      isPending: false,
      isError: false,
      error: null,
    });
    useToggleRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCreateRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    const { container } = renderRules();

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("disables quick simulation when no baseline data is available", () => {
    const simulateMutate = vi.fn();

    useRulesMock.mockReturnValue({
      data: [
        {
          id: "rule-1",
          name: "Regra BR",
          is_enabled: true,
          priority: 10,
          conditions: [],
          actions: {},
        },
      ],
      isLoading: false,
    });

    useProvidersMock.mockReturnValue({ data: [] });

    useDashboardMetricsMock.mockReturnValue({
      data: {
        top_countries: [],
        top_templates: [],
        total_messages: 0,
      },
    });

    useSimulateRulesMock.mockReturnValue({
      mutate: simulateMutate,
      mutateAsync: vi.fn(),
      data: undefined,
      isPending: false,
      isError: true,
      error: new Error("falha"),
    });

    useToggleRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useCreateRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });
    useUpdateRuleMock.mockReturnValue({ mutateAsync: vi.fn(), isPending: false });

    renderRules();

    const quickButton = screen.getByRole("button", { name: /executar/i });
    expect(quickButton).toBeDisabled();
    expect(simulateMutate).not.toHaveBeenCalled();
    expect(screen.getByText("falha")).toBeInTheDocument();
  });
});

