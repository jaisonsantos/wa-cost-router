import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Messages from "@/pages/Messages";

const useMessageJobsMock = vi.fn();
const useMessageJobDetailsMock = vi.fn();

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { email: "admin@demo.local" },
    logout: vi.fn(),
  }),
}));

vi.mock("@/hooks/useApi", () => ({
  useMessageJobs: (params?: unknown) => useMessageJobsMock(params),
  useMessageJobDetails: (jobId: string, params?: unknown) => useMessageJobDetailsMock(jobId, params),
}));

beforeAll(() => {
  if (!window.HTMLElement.prototype.hasPointerCapture) {
    window.HTMLElement.prototype.hasPointerCapture = () => false;
  }
  if (!window.HTMLElement.prototype.releasePointerCapture) {
    window.HTMLElement.prototype.releasePointerCapture = () => {};
  }
  if (!window.HTMLElement.prototype.scrollIntoView) {
    window.HTMLElement.prototype.scrollIntoView = () => {};
  }
});

const renderMessages = () =>
  render(
    <MemoryRouter>
      <Messages />
    </MemoryRouter>,
  );

describe("Messages", () => {
  beforeEach(() => {
    useMessageJobsMock.mockReset();
    useMessageJobDetailsMock.mockReset();
  });

  it("renders job data with channel and direction details and shows conversation history", () => {
    const createdAt = new Date("2024-01-01T12:00:00Z").toISOString();

    const jobSummary = {
      id: "job-1",
      status: "delivered",
      direction: "outbound",
      channel: "whatsapp",
      channel_address: "+5511988888888",
      contact_id: "contact-1",
      contact_name: "Maria Oliveira",
      to_number: "+5511999999999",
      template_id: "welcome_template",
      template_category: "marketing",
      country_iso: "BR",
      created_at: createdAt,
      total_cost_minor: 1200,
    };

    useMessageJobsMock.mockReturnValue({
      data: [jobSummary],
      isLoading: false,
      isError: false,
      error: null,
    });

    useMessageJobDetailsMock.mockReturnValue({
      data: {
        ...jobSummary,
        attempts: [],
        total_cost_minor: 1200,
        conversation_history: [
          {
            channel: "whatsapp",
            contact_address: "+5511988888888",
            contact_name: "Maria Oliveira",
            messages: [
              {
                id: "msg-1",
                direction: "outbound",
                channel: "whatsapp",
                channel_address: "+5511988888888",
                content: "Olá, Maria!",
                timestamp: "2024-01-01T12:10:00Z",
                status: "delivered",
                sender: "Plataforma",
              },
              {
                id: "msg-2",
                direction: "inbound",
                channel: "whatsapp",
                channel_address: "+5511988888888",
                content: "Oi!",
                timestamp: "2024-01-01T12:11:00Z",
              },
            ],
          },
        ],
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    renderMessages();

    expect(screen.getByText("Canal")).toBeInTheDocument();
    expect(screen.getByText("Endereço")).toBeInTheDocument();
    expect(screen.getByText("Contato")).toBeInTheDocument();
    expect(screen.getByText(/whatsapp/i)).toBeInTheDocument();
    expect(screen.getAllByText("Outbound").length).toBeGreaterThan(0);
    expect(screen.getByText("Maria Oliveira")).toBeInTheDocument();

    const lastDetailsCallBeforeClick = useMessageJobDetailsMock.mock.calls.at(-1);
    expect(lastDetailsCallBeforeClick?.[0]).toBe("");
    expect(lastDetailsCallBeforeClick?.[1]).toEqual({ channel: undefined, channel_address: undefined });

    fireEvent.click(screen.getByRole("button", { name: /ver detalhes/i }));

    const lastDetailsCall = useMessageJobDetailsMock.mock.calls.at(-1);
    expect(lastDetailsCall?.[0]).toBe("job-1");
    expect(lastDetailsCall?.[1]).toEqual({ channel: "whatsapp", channel_address: "+5511988888888" });

    expect(screen.getByText("Histórico da Conversa")).toBeInTheDocument();
    expect(screen.getByText("Olá, Maria!")).toBeInTheDocument();
    expect(screen.getAllByText("Inbound").length).toBeGreaterThan(0);
    expect(screen.getByText("Remetente: Plataforma")).toBeInTheDocument();
    expect(screen.getAllByText("contact-1").length).toBeGreaterThan(0);
  });

  it("updates hooks when channel filter changes", async () => {
    const createdAt = new Date("2024-01-01T12:00:00Z").toISOString();

    const jobSummary = {
      id: "job-1",
      status: "delivered",
      direction: "outbound",
      channel: "whatsapp",
      channel_address: "+5511988888888",
      contact_id: "contact-1",
      contact_name: "Maria Oliveira",
      to_number: "+5511999999999",
      template_id: "welcome_template",
      template_category: "marketing",
      country_iso: "BR",
      created_at: createdAt,
      total_cost_minor: 1200,
    };

    useMessageJobsMock.mockReturnValue({
      data: [jobSummary],
      isLoading: false,
      isError: false,
      error: null,
    });

    useMessageJobDetailsMock.mockReturnValue({
      data: {
        ...jobSummary,
        attempts: [],
        total_cost_minor: 1200,
        conversation_history: [],
      },
      isLoading: false,
      isError: false,
      error: null,
    });

    renderMessages();

    const user = userEvent.setup();

    await user.click(screen.getByRole("combobox", { name: "Filtrar por canal" }));
    await user.click(screen.getByRole("option", { name: "Whatsapp" }));

    const lastJobsCall = useMessageJobsMock.mock.calls.at(-1);
    expect(lastJobsCall?.[0]).toMatchObject({ channel: "whatsapp" });

    const lastDetailsCall = useMessageJobDetailsMock.mock.calls.at(-1);
    expect(lastDetailsCall?.[1]).toMatchObject({ channel: "whatsapp", channel_address: undefined });
  });
});
