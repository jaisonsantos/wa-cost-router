import type { ReactElement } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import userEvent from "@testing-library/user-event";
import ImportWizard from "../ImportWizard";
import type { ContactImportJob } from "@/types/api";

const { mockCreateContactImport, mockGetContactImportJob } = vi.hoisted(() => ({
  mockCreateContactImport: vi.fn(),
  mockGetContactImportJob: vi.fn(),
}));

const { mockUseAuth } = vi.hoisted(() => ({
  mockUseAuth: vi.fn(() => ({
    organization: { id: "org", name: "Org" },
    user: { email: "user@example.com" },
    logout: vi.fn(),
  })),
}));

vi.mock("@/lib/api", () => ({
  api: {
    createContactImport: mockCreateContactImport,
    getContactImportJob: mockGetContactImportJob,
  },
  API_BASE_URL: "http://localhost:8000",
}));

vi.mock("@/contexts/AuthContext", () => ({
  useAuth: mockUseAuth,
}));

vi.mock("@/hooks/use-toast", () => ({
  toast: vi.fn(),
}));

const createClient = () =>
  new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

const renderWizard = (ui: ReactElement = <ImportWizard />) => {
  const client = createClient();
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
};

describe("ImportWizard", () => {
  let originalWebSocket: typeof WebSocket;

  beforeAll(() => {
    originalWebSocket = global.WebSocket;
    class MockWebSocket {
      static lastUrl: string | null = null;
      onopen: (() => void) | null = null;
      onmessage: ((event: { data: string }) => void) | null = null;
      onerror: (() => void) | null = null;
      onclose: (() => void) | null = null;
      constructor(url: string) {
        MockWebSocket.lastUrl = url;
        setTimeout(() => {
          this.onopen?.();
        }, 0);
      }
      close() {
        this.onclose?.();
      }
    }
    // @ts-expect-error overriding for tests
    global.WebSocket = MockWebSocket;
  });

  afterAll(() => {
    global.WebSocket = originalWebSocket;
  });

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem("token", "test-token");
  });

  it("parses CSV and shows preview", async () => {
    const csvContent = "full_name,email,phone\nAna Example,ana@example.com,+5511999999999";
    const file = new File([csvContent], "contacts.csv", { type: "text/csv" });
    const textMock = vi.fn().mockResolvedValue(csvContent);
    Object.defineProperty(file, "text", { value: textMock, configurable: true });
    const user = userEvent.setup();

    renderWizard();

    const input = screen.getByLabelText(/Arquivo CSV/i) as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => {
      expect(textMock).toHaveBeenCalled();
    });

    expect(await screen.findByText(/Mapeamento de colunas/)).toBeInTheDocument();
    expect(screen.getAllByText("full_name").length).toBeGreaterThan(0);

    // Avança para pré-visualização
    const nextButton = await screen.findByText(/Avançar para pré-visualização/i);
    await user.click(nextButton);

    expect(await screen.findByText(/Mostrando 1 de 1 registros/)).toBeInTheDocument();
    expect(screen.getByText("Ana Example")).toBeInTheDocument();
  });

  it("envia arquivo normalizado e acompanha status", async () => {
    const csvContent = "full_name,email\nAna Example,ana@example.com";
    const file = new File([csvContent], "contacts.csv", { type: "text/csv" });
    const textMock = vi.fn().mockResolvedValue(csvContent);
    Object.defineProperty(file, "text", { value: textMock, configurable: true });
    const user = userEvent.setup();

    const job: ContactImportJob = {
      id: "job-1",
      org_id: "org",
      requested_by: "user",
      input_uri: "s3://imports/contacts.csv",
      status: "processing",
      total_rows: 1,
      processed_rows: 1,
      error_rows: 0,
      error_report_uri: null,
      source: "import",
      source_metadata: null,
      started_at: "2025-10-08T12:00:00Z",
      completed_at: null,
      created_at: "2025-10-08T12:00:00Z",
      updated_at: "2025-10-08T12:00:00Z",
    };

    mockCreateContactImport.mockResolvedValue(job);
    mockGetContactImportJob.mockResolvedValue(job);

    renderWizard();

    const input = screen.getByLabelText(/Arquivo CSV/i) as HTMLInputElement;
    await user.upload(input, file);

    await waitFor(() => {
      expect(textMock).toHaveBeenCalled();
    });

    const previewButton = await screen.findByText(/Avançar para pré-visualização/i);
    await user.click(previewButton);

    const confirmButton = await screen.findByRole("button", { name: /Confirmar importação/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(mockCreateContactImport).toHaveBeenCalled();
    });

    expect(await screen.findByText(/Status da importação/)).toBeInTheDocument();
    expect(screen.getByText(/1 de 1 linhas processadas/)).toBeInTheDocument();
  });

  afterEach(() => {
    localStorage.clear();
  });
});
