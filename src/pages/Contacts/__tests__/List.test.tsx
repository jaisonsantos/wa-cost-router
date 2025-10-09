import type { ReactElement } from "react";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import ContactListPage from "../List";
import type { Contact, ContactListResponse } from "@/types/api";

const { mockUseContactList } = vi.hoisted(() => ({
  mockUseContactList: vi.fn(),
}));

const { mockUseAuth } = vi.hoisted(() => ({
  mockUseAuth: vi.fn(() => ({
    organization: { id: "org", name: "Org" },
    user: { email: "user@example.com" },
    logout: vi.fn(),
  })),
}));

vi.mock("@/services/contacts", () => ({
  useContactList: mockUseContactList,
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: mockUseAuth,
}));

const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });

const renderWithQueryClient = (ui: ReactElement) => {
  const client = createQueryClient();
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
};

type ContactFixture = Partial<Contact> & Pick<Contact, "id" | "org_id" | "status">;

const buildContact = (overrides: ContactFixture): Contact => ({
  id: "contact-id",
  org_id: "org",
  status: "active",
  source: "manual",
  created_at: "2024-01-01T00:00:00.000Z",
  updated_at: "2024-01-01T00:00:00.000Z",
  attributes: null,
  source_metadata: null,
  proof_hash: null,
  channel_opt_ins: [],
  segments: [],
  notes: [],
  ...overrides,
});

const buildResponse = (items: ContactFixture[]): ContactListResponse => ({
  items: items.map((item) => buildContact(item)),
  limit: 25,
  offset: 0,
  count: items.length,
});

describe("ContactListPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseContactList.mockReset();
  });

  it("renders contacts with opt-in badges", () => {
    mockUseContactList.mockReturnValue({
      data: buildResponse([
        {
          id: "1",
          org_id: "org",
          full_name: "Ana Silva",
          email: "ana@example.com",
          phone: "+5511999999999",
          status: "active",
          channel_opt_ins: [
            {
              channel: "whatsapp",
              channel_address: "+5511999999999",
              status: "granted",
              version: 1,
            },
          ],
        },
      ]),
      isLoading: false,
      isFetching: false,
      error: null,
    });

    renderWithQueryClient(<ContactListPage />);

    expect(screen.getByRole("heading", { name: "Contatos" })).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /Ana Silva/ });
    expect(within(row).getByText(/whatsapp • granted/i)).toBeInTheDocument();
  });

  it("shows loading skeletons while fetching", () => {
    mockUseContactList.mockReturnValue({
      data: undefined,
      isLoading: true,
      isFetching: true,
      error: null,
    });

    const { container } = renderWithQueryClient(<ContactListPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });

  it("renders error state", () => {
    mockUseContactList.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new Error("boom"),
    });

    renderWithQueryClient(<ContactListPage />);
    expect(screen.getByText(/Falha ao carregar contatos: boom/)).toBeInTheDocument();
  });
});
