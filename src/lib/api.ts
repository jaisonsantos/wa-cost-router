import {
  AdvancedSimulationRequest,
  AdvancedSimulationResponse,
  CreateWAConnectionPayload,
  DashboardMetrics,
  Event,
  EventsQueryParams,
  ImportRatesResponse,
  MessageJobDetail,
  MessageJobsQueryParams,
  MessageJobSummary,
  Organization,
  Provider,
  ProviderCredentialInput,
  ProviderHealth,
  ProviderMetric,
  RateEntry,
  Rule,
  RuleCreatePayload,
  RuleUpdatePayload,
  SendMessageRequest,
  SendMessageResponse,
  SetProviderCredentialsResponse,
  SimulateRulesResult,
  SummaryResponse,
  TokenResponse,
  WAConnectionResponse,
} from "@/types/api";

const API_BASE_URL = "http://localhost:8000";

interface ApiOptions extends RequestInit {
  requiresAuth?: boolean;
}

class ApiClient {
  private getHeaders(requiresAuth: boolean = true): HeadersInit {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
    };

    if (requiresAuth) {
      const token = localStorage.getItem("token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }

    return headers;
  }

  private async request<T>(endpoint: string, options: ApiOptions = {}): Promise<T> {
    const { requiresAuth = true, ...fetchOptions } = options;

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      headers: {
        ...this.getHeaders(requiresAuth),
        ...fetchOptions.headers,
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/login";
      }
      const error = await response.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    const data = (await response.json()) as T;
    return data;
  }

  // Auth
  async login(email: string, password: string): Promise<TokenResponse> {
    return this.request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      requiresAuth: false,
    });
  }

  async register(email: string, password: string, org_name: string): Promise<TokenResponse> {
    return this.request<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, org_name }),
      requiresAuth: false,
    });
  }

  // Organizations
  async getCurrentOrg(): Promise<Organization> {
    return this.request<Organization>("/orgs/current");
  }

  // Reports
  async getSummary(from?: string, to?: string): Promise<SummaryResponse> {
    const params = new URLSearchParams();
    if (from) params.append("from", from);
    if (to) params.append("to", to);
    const query = params.toString() ? `?${params}` : "";
    return this.request<SummaryResponse>(`/reports/summary${query}`);
  }

  // Events
  async getEvents(params: EventsQueryParams = {}): Promise<Event[]> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, value.toString());
    });
    const query = searchParams.toString() ? `?${searchParams}` : "";
    return this.request<Event[]>(`/events${query}`);
  }

  // Rules
  async getRules(): Promise<Rule[]> {
    return this.request<Rule[]>("/rules");
  }

  async createRule(rule: RuleCreatePayload): Promise<Rule> {
    return this.request<Rule>("/rules", {
      method: "POST",
      body: JSON.stringify(rule),
    });
  }

  async updateRule(ruleId: string, updates: RuleUpdatePayload): Promise<{ status: string }> {
    return this.request<{ status: string }>(`/rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  }

  async toggleRule(ruleId: string): Promise<{ is_enabled: boolean }> {
    return this.request<{ is_enabled: boolean }>(`/rules/${ruleId}/toggle`, {
      method: "POST",
    });
  }

  async simulateRules(): Promise<SimulateRulesResult> {
    return this.request<SimulateRulesResult>("/rules/simulate", {
      method: "POST",
    });
  }

  // Rates
  async getRates(): Promise<RateEntry[]> {
    return this.request<RateEntry[]>("/rates");
  }

  async importRatesCSV(file: File): Promise<ImportRatesResponse> {
    const formData = new FormData();
    formData.append("file", file);

    const token = localStorage.getItem("token");
    const response = await fetch(`${API_BASE_URL}/rates/import_csv`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error("CSV import failed");
    }

    const data = (await response.json()) as ImportRatesResponse;
    return data;
  }

  // Integrations
  async createWAConnection(data: CreateWAConnectionPayload): Promise<WAConnectionResponse> {
    return this.request<WAConnectionResponse>("/integrations/wa/connections", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async testWAConnection(): Promise<{ status: string; message: string }> {
    return this.request<{ status: string; message: string }>("/integrations/wa/test", {
      method: "POST",
    });
  }

  // Providers
  async getProviders(): Promise<Provider[]> {
    return this.request<Provider[]>("/providers");
  }

  async setProviderCredentials(
    providerId: string,
    credentials: ProviderCredentialInput,
  ): Promise<SetProviderCredentialsResponse> {
    return this.request<SetProviderCredentialsResponse>("/providers/credentials", {
      method: "POST",
      body: JSON.stringify({ provider_id: providerId, credentials }),
    });
  }

  async healthCheckProvider(providerId: string): Promise<ProviderHealth> {
    return this.request<ProviderHealth>(`/providers/${providerId}/health`, {
      method: "POST",
    });
  }

  // Messages
  async getMessageJobs(params?: MessageJobsQueryParams): Promise<MessageJobSummary[]> {
    const query = params?.status ? `?status=${params.status}` : "";
    return this.request<MessageJobSummary[]>(`/messages/jobs${query}`);
  }

  async getMessageJobDetails(jobId: string): Promise<MessageJobDetail> {
    return this.request<MessageJobDetail>(`/messages/jobs/${jobId}`);
  }

  async sendMessage(data: SendMessageRequest): Promise<SendMessageResponse> {
    return this.request<SendMessageResponse>("/messages/send", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Dashboard Metrics
  async getDashboardMetrics(): Promise<DashboardMetrics> {
    return this.request<DashboardMetrics>("/reports/dashboard-metrics");
  }

  async getProviderMetrics(): Promise<ProviderMetric[]> {
    return this.request<ProviderMetric[]>("/reports/provider-metrics");
  }

  // Advanced Simulator
  async simulateAdvanced(data: AdvancedSimulationRequest): Promise<AdvancedSimulationResponse> {
    return this.request<AdvancedSimulationResponse>("/rules/simulate-advanced", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient();
