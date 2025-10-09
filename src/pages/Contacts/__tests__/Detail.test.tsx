import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { vi } from "vitest";
import ContactDetailPage from "../Detail";
import type { Contact, ContactConsentHistoryResponse } from "@/types/api";

const { mockUseContact, mockUseContactConsentHistory } = vi.hoisted(() => ({
  mockUseContact: vi.fn(),
  mockUseContactConsentHistory: vi.fn(),
}));

const { mockUseAuth } = vi.hoisted(() => ({
  mockUseAuth: vi.fn(() => ({
    organization: { id: "org", name: "Org" },
    user: { email: "user@example.com" },
    logout: vi.fn(),
  })),
}));

vi.mock("@/services/contacts", () => ({
  useContact: mockUseContact,
  useContactConsentHistory: mockUseContactConsentHistory,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: mockUseAuth,
}));

const createClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

const renderWithProviders = (ui: ReactElement, { initialEntries = ["/contacts/1"] } = {}) => {
  const client = createClient();
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route path="/contacts/:contactId" element={ui} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
};

describe("ContactDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseContact.mockReset();
    mockUseContactConsentHistory.mockReset();
  });

  it("renders contact information and consent history", () => {
    const contact: Contact = {
      id: "1",
      org_id: "org",
      full_name: "João Silva",
      email: "joao@example.com",
      phone: "+5511888888888",
      status: "active",
      source: "import",
      created_at: "2025-10-08T12:00:00Z",
      updated_at: "2025-10-08T12:10:00Z",
      channel_opt_ins: [
        {
          id: "opt-1",
          channel: "whatsapp",
          channel_address: "+5511888888888",
          status: "granted",
          version: 2,
          captured_at: "2025-10-08T12:00:00Z",
          source: "import",
        },
      ],
      attributes: {
        segments: [
          {
            id: "seg-1",
            name: "VIP",
            slug: "vip",
          },
        ],
        notes: [
          {
            id: "note-1",
            content: "Primeira importação",
            author: "Ops",
            created_at: "2025-10-08T12:00:00Z",
          },
        ],
      },
    } as Contact;

    const history: ContactConsentHistoryResponse = {
      items: [
        {
          id: "audit-1",
          opt_in_id: "opt-1",
          opt_in_version: 2,
          channel: "whatsapp",
          channel_address: "+5511888888888",
          status: "granted",
          source: "import",
          agent: "ops",
          recorded_at: "2025-10-08T12:00:00Z",
          request_ip: "203.0.113.1",
          evidence_uri: "https://example.com/evidence.pdf",
          proof_hash: null,
          context: {},
        },
      ],
      count: 1,
    };

    mockUseContact.mockReturnValue({ data: contact, isLoading: false, error: null });
    mockUseContactConsentHistory.mockReturnValue({ data: history, isLoading: false, error: null });

    renderWithProviders(<ContactDetailPage />);

    expect(screen.getByRole("heading", { name: "João Silva" })).toBeInTheDocument();
    const phoneElements = screen.getAllByText("+5511888888888");
    expect(phoneElements.length).toBeGreaterThan(0);
    expect(screen.getByText(/whatsapp • granted/i)).toBeInTheDocument();

    expect(screen.getByText(/Histórico de consentimento/)).toBeInTheDocument();
    expect(screen.getByText("ops")).toBeInTheDocument();
  });

  it("shows error when contact fails to load", () => {
    mockUseContact.mockReturnValue({ data: undefined, isLoading: false, error: new Error("not found") });
    mockUseContactConsentHistory.mockReturnValue({ data: undefined, isLoading: false, error: null });

    renderWithProviders(<ContactDetailPage />);

    expect(screen.getByText(/Não foi possível carregar o contato/)).toBeInTheDocument();
  });
});
