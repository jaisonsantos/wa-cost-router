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

    return response.json();
  }

  // Auth
  async login(email: string, password: string) {
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
      requiresAuth: false,
    });
  }

  async register(email: string, password: string, org_name: string) {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, org_name }),
      requiresAuth: false,
    });
  }

  // Organizations
  async getCurrentOrg() {
    return this.request("/orgs/current");
  }

  // Reports
  async getSummary(from?: string, to?: string) {
    const params = new URLSearchParams();
    if (from) params.append("from", from);
    if (to) params.append("to", to);
    const query = params.toString() ? `?${params}` : "";
    return this.request(`/reports/summary${query}`);
  }

  // Events
  async getEvents(params: {
    limit?: number;
    offset?: number;
    country?: string;
    template?: string;
    from?: string;
    to?: string;
  } = {}) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.append(key, value.toString());
    });
    const query = searchParams.toString() ? `?${searchParams}` : "";
    return this.request(`/events${query}`);
  }

  // Rules
  async getRules() {
    return this.request("/rules");
  }

  async createRule(rule: {
    name: string;
    description?: string;
    conditions: Record<string, any>;
    actions: Record<string, any>;
    priority: number;
  }) {
    return this.request("/rules", {
      method: "POST",
      body: JSON.stringify(rule),
    });
  }

  async updateRule(ruleId: string, updates: Partial<{
    name: string;
    description: string;
    conditions: Record<string, any>;
    actions: Record<string, any>;
    priority: number;
  }>) {
    return this.request(`/rules/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  }

  async toggleRule(ruleId: string) {
    return this.request(`/rules/${ruleId}/toggle`, {
      method: "POST",
    });
  }

  async simulateRules() {
    return this.request("/rules/simulate", {
      method: "POST",
    });
  }

  // Rates
  async getRates() {
    return this.request("/rates");
  }

  async importRatesCSV(file: File) {
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

    return response.json();
  }

  // Integrations
  async createWAConnection(data: {
    business_id: string;
    phone_id: string;
    access_token: string;
    webhook_verify_token?: string;
  }) {
    return this.request("/integrations/wa/connections", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async testWAConnection() {
    return this.request("/integrations/wa/test", {
      method: "POST",
    });
  }

  // Providers
  async getProviders() {
    return this.request("/providers");
  }

  async setProviderCredentials(providerId: string, credentials: any) {
    return this.request("/providers/credentials", {
      method: "POST",
      body: JSON.stringify({ provider_id: providerId, credentials }),
    });
  }

  async healthCheckProvider(providerId: string) {
    return this.request(`/providers/${providerId}/health`, {
      method: "POST",
    });
  }

  // Messages
  async getMessageJobs(params?: { status?: string }) {
    const query = params?.status ? `?status=${params.status}` : "";
    return this.request(`/messages/jobs${query}`);
  }

  async getMessageJobDetails(jobId: string) {
    return this.request(`/messages/jobs/${jobId}`);
  }

  async sendMessage(data: {
    idempotency_key: string;
    to_number: string;
    template_id: string;
    template_category: string;
    variables: any;
    country_iso: string;
  }) {
    return this.request("/messages/send", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Dashboard Metrics
  async getDashboardMetrics() {
    return this.request("/reports/dashboard-metrics");
  }

  async getProviderMetrics() {
    return this.request("/reports/provider-metrics");
  }

  // Advanced Simulator
  async simulateAdvanced(data: {
    countries: string[];
    volumes: Record<string, number>;
    category: string;
  }) {
    return this.request("/rules/simulate-advanced", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }
}

export const api = new ApiClient();
