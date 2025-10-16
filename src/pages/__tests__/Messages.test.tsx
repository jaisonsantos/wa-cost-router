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
  useCreateBillingPortal: () => ({ mutateAsync: vi.fn(), isPending: false }),
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

  it("filters jobs client-side when channel filter changes", async () => {
    const createdAt = new Date("2024-01-01T12:00:00Z").toISOString();

    const whatsappJob = {
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

    const emailJob = {
      id: "job-2",
      status: "processing",
      direction: "outbound",
      channel: "email",
      channel_address: "cliente@example.com",
      contact_id: "contact-2",
      contact_name: "Cliente",
      to_number: null,
      template_id: "email_digest",
      template_category: "utility",
      country_iso: "US",
      created_at: createdAt,
      total_cost_minor: null,
    };

    useMessageJobsMock.mockReturnValue({
      data: [whatsappJob, emailJob],
      isLoading: false,
      isError: false,
      error: null,
    });

    useMessageJobDetailsMock.mockReturnValue({
      data: {
        ...whatsappJob,
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

    expect(screen.getByText("cliente@example.com")).toBeInTheDocument();

    await user.click(screen.getByRole("combobox", { name: "Filtrar por canal" }));
    await user.click(screen.getByRole("option", { name: "Whatsapp" }));

    expect(screen.getByText("+5511988888888")).toBeInTheDocument();
    expect(screen.queryByText("cliente@example.com")).not.toBeInTheDocument();

    const lastDetailsCall = useMessageJobDetailsMock.mock.calls.at(-1);
    expect(lastDetailsCall?.[1]).toMatchObject({ channel: "whatsapp", channel_address: undefined });

    useMessageJobsMock.mock.calls.forEach(([params]) => {
      if (params) {
        expect((params as Record<string, unknown>).channel).toBeUndefined();
      }
    });
  });

  it("shows unique channel options and resets filters when selecting all channels", async () => {
    const createdAt = new Date("2024-01-01T12:00:00Z").toISOString();

    const jobs = [
      {
        id: "job-whatsapp",
        status: "processing",
        direction: "outbound",
        channel: "whatsapp",
        channel_address: "+5511988888888",
        contact_id: null,
        contact_name: null,
        to_number: "+5511988888888",
        template_id: "welcome_whatsapp",
        template_category: "marketing",
        country_iso: "BR",
        created_at: createdAt,
        total_cost_minor: null,
      },
      {
        id: "job-email",
        status: "delivered",
        direction: "outbound",
        channel: "email",
        channel_address: "cliente@example.com",
        contact_id: "contact-email",
        contact_name: "Contato Email",
        to_number: null,
        template_id: "email_digest",
        template_category: "utility",
        country_iso: "US",
        created_at: createdAt,
        total_cost_minor: 250,
      },
      {
        id: "job-sms",
        status: "failed",
        direction: "outbound",
        channel: "sms",
        channel_address: "+15551234567",
        contact_id: null,
        contact_name: null,
        to_number: "+15551234567",
        template_id: "otp_sms",
        template_category: "utility",
        country_iso: "US",
        created_at: createdAt,
        total_cost_minor: null,
      },
      {
        id: "job-email-duplicate",
        status: "failed",
        direction: "outbound",
        channel: "email",
        channel_address: "duplicado@example.com",
        contact_id: null,
        contact_name: null,
        to_number: null,
        template_id: "email_digest",
        template_category: "utility",
        country_iso: "US",
        created_at: createdAt,
        total_cost_minor: null,
      },
    ];

    useMessageJobsMock.mockReturnValue({
      data: jobs,
      isLoading: false,
      isError: false,
      error: null,
    });

    useMessageJobDetailsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      error: null,
    });

    renderMessages();

    const user = userEvent.setup();

    await user.click(screen.getByRole("combobox", { name: "Filtrar por canal" }));

    const optionTexts = screen
      .getAllByRole("option")
      .map((option) => option.textContent?.trim())
      .filter(Boolean) as string[];

    expect(optionTexts[0]).toBe("Todos os canais");
    expect(optionTexts.slice(1)).toEqual(["Email", "Sms", "Whatsapp"]);

    await user.click(screen.getByRole("option", { name: "Sms" }));

    expect(screen.getAllByText("+15551234567").length).toBeGreaterThan(0);
    expect(screen.queryByText("cliente@example.com")).not.toBeInTheDocument();

    let lastDetailsCall = useMessageJobDetailsMock.mock.calls.at(-1);
    expect(lastDetailsCall?.[1]).toMatchObject({ channel: "sms", channel_address: undefined });

    await user.click(screen.getByRole("combobox", { name: "Filtrar por canal" }));
    await user.click(screen.getByRole("option", { name: "Todos os canais" }));

    expect(screen.getByText("cliente@example.com")).toBeInTheDocument();

    lastDetailsCall = useMessageJobDetailsMock.mock.calls.at(-1);
    expect(lastDetailsCall?.[1]).toMatchObject({ channel: undefined, channel_address: undefined });

    useMessageJobsMock.mock.calls.forEach(([params]) => {
      if (params) {
        expect((params as Record<string, unknown>).channel).toBeUndefined();
      }
    });
  });
});
