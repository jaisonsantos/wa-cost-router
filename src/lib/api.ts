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
  Template,
  TemplateCreatePayload,
  TemplateSyncResponse,
  TemplateUpdatePayload,
  IntegrationConnection,
  ConnectionTestResult,
  RateEntry,
  ContactListResponse,
  ContactConsentHistoryResponse,
  Contact,
  ContactSegment,
  ContactSegmentCreatePayload,
  ContactSegmentListResponse,
  ContactSegmentUpdatePayload,
  OptInStatus,
  ContactStatus,
  Rule,
  RuleCreatePayload,
  RuleUpdatePayload,
  SendMessageRequest,
  SendMessageResponse,
  SetProviderCredentialsResponse,
  SimulateRulesRequest,
  SimulateRulesResult,
  SummaryResponse,
  TokenResponse,
  WAConnectionResponse,
  ContactImportJob,
  ChannelMetricsResponse,
  ChannelMetricsQueryParams,
  QueueMetricsResponse,
  QueueMetricsQueryParams,
  MessageJobDetailsQueryParams,
  BillingSummary,
  BillingCheckoutRequest,
  BillingCheckoutResponse,
} from "@/types/api";

export const API_BASE_URL = "http://localhost:8000";

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
      let detailMessage: string | undefined;
      const detail = error.detail;
      if (typeof detail === "string") {
        detailMessage = detail;
      } else if (Array.isArray(detail)) {
        detailMessage = detail.join("; ");
      } else if (detail && typeof detail === "object" && Array.isArray(detail.errors)) {
        detailMessage = detail.errors.join("; ");
      }
      throw new Error(detailMessage || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const contentLength = response.headers.get("content-length");
    if (contentLength === "0") {
      return undefined as T;
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("application/json")) {
      return undefined as T;
    }

    const data = (await response.json()) as T;
    return data;
  }

  private async downloadFile(
    endpoint: string,
    {
      params,
      requiresAuth = true,
      fallbackFilename,
    }: { params?: URLSearchParams; requiresAuth?: boolean; fallbackFilename: string },
  ): Promise<void> {
    const url = new URL(`${API_BASE_URL}${endpoint}`);
    if (params) {
      params.forEach((value, key) => {
        url.searchParams.append(key, value);
      });
    }

    const headers = { ...(this.getHeaders(requiresAuth) as Record<string, string>) };
    delete headers["Content-Type"];

    const response = await fetch(url.toString(), {
      method: "GET",
      headers,
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      let detailMessage: string | undefined;
      if (contentType.includes("application/json")) {
        const errorPayload = await response.json().catch(() => undefined);
        const detail = errorPayload?.detail;
        if (typeof detail === "string") {
          detailMessage = detail;
        } else if (Array.isArray(detail)) {
          detailMessage = detail.join("; ");
        }
      }
      throw new Error(detailMessage || `HTTP ${response.status}`);
    }

    const blob = await response.blob();
    let filename = fallbackFilename;
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    if (match) {
      const encoded = match[1] ?? match[2];
      if (encoded) {
        try {
          filename = decodeURIComponent(encoded);
        } catch (err) {
          filename = encoded;
        }
      }
    }

    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
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

  async getBillingSummary(): Promise<BillingSummary> {
    return this.request<BillingSummary>("/billing/summary");
  }

  async createBillingCheckout(payload: BillingCheckoutRequest): Promise<BillingCheckoutResponse> {
    return this.request<BillingCheckoutResponse>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async createBillingPortal(): Promise<{ url: string }> {
    return this.request<{ url: string }>("/billing/portal", {
      method: "GET",
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

  async simulateRules(data: SimulateRulesRequest): Promise<SimulateRulesResult> {
    return this.request<SimulateRulesResult>("/rules/simulate", {
      method: "POST",
      body: JSON.stringify(data),
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

  // Templates
  async getTemplates(params: { language?: string; status?: string } = {}): Promise<Template[]> {
    const searchParams = new URLSearchParams();
    if (params.language) searchParams.append("language", params.language);
    if (params.status) searchParams.append("status", params.status);
    const query = searchParams.toString();
    return this.request<Template[]>(`/templates${query ? `?${query}` : ""}`);
  }

  async createTemplate(payload: TemplateCreatePayload): Promise<Template> {
    return this.request<Template>("/templates/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateTemplate(templateId: string, updates: TemplateUpdatePayload): Promise<Template> {
    return this.request<Template>(`/templates/${templateId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  }

  async deleteTemplate(templateId: string): Promise<void> {
    await this.request<void>(`/templates/${templateId}`, {
      method: "DELETE",
    });
  }

  async syncTemplates(): Promise<TemplateSyncResponse> {
    return this.request<TemplateSyncResponse>("/templates/sync", {
      method: "POST",
    });
  }

  // Integrations
  async getIntegrationConnections(): Promise<IntegrationConnection[]> {
    return this.request<IntegrationConnection[]>("/integrations/connections");
  }

  async testIntegrationConnection(
    channel: string,
    payload?: { provider_id?: string },
  ): Promise<ConnectionTestResult> {
    const body = payload ? JSON.stringify(payload) : undefined;
    return this.request<ConnectionTestResult>(`/integrations/${channel}/test`, {
      method: "POST",
      body,
    });
  }

  // Contacts
  async getContacts(params: {
    limit?: number;
    offset?: number;
    status?: ContactStatus;
    channel?: string;
    opt_in_status?: OptInStatus[];
    segment_id?: string[];
    segment_slug?: string[];
    channel_address?: string;
  } = {}): Promise<ContactListResponse> {
    const searchParams = new URLSearchParams();

    if (params.limit !== undefined) {
      searchParams.append("limit", params.limit.toString());
    }

    if (params.offset !== undefined) {
      searchParams.append("offset", params.offset.toString());
    }

    if (params.status) {
      searchParams.append("status", params.status);
    }

    if (params.channel) {
      searchParams.append("channel", params.channel);
    }

    if (params.opt_in_status?.length) {
      params.opt_in_status.forEach((status) => searchParams.append("opt_in_status", status));
    }

    if (params.segment_id?.length) {
      params.segment_id.forEach((segmentId) => searchParams.append("segment_id", segmentId));
    }

    if (params.segment_slug?.length) {
      params.segment_slug.forEach((segmentSlug) => searchParams.append("segment_slug", segmentSlug));
    }

    if (params.channel_address) {
      searchParams.append("channel_address", params.channel_address);
    }

    const query = searchParams.toString();
    return this.request<ContactListResponse>(`/contacts${query ? `?${query}` : ""}`);
  }

  async getContact(contactId: string): Promise<Contact> {
    return this.request<Contact>(`/contacts/${contactId}`);
  }

  async getContactConsentHistory(contactId: string): Promise<ContactConsentHistoryResponse> {
    return this.request<ContactConsentHistoryResponse>(`/contacts/${contactId}/consents/history`);
  }

  async createContactImport(file: File): Promise<ContactImportJob> {
    const formData = new FormData();
    formData.append("upload", file);

    const token = localStorage.getItem("token");
    const response = await fetch(`${API_BASE_URL}/contacts/imports`, {
      method: "POST",
      headers: token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : undefined,
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Contact import failed" }));
      throw new Error(error.detail ?? "Contact import failed");
    }

    const data = (await response.json()) as ContactImportJob;
    return data;
  }

  async getContactImportJob(jobId: string): Promise<ContactImportJob> {
    return this.request<ContactImportJob>(`/contacts/imports/${jobId}`);
  }

  // Contact Segments
  async getContactSegments(params: { limit?: number; offset?: number } = {}): Promise<ContactSegmentListResponse> {
    const searchParams = new URLSearchParams();

    if (params.limit !== undefined) {
      searchParams.append("limit", params.limit.toString());
    }

    if (params.offset !== undefined) {
      searchParams.append("offset", params.offset.toString());
    }

    const query = searchParams.toString();
    const querySuffix = query ? `?${query}` : "";
    return this.request<ContactSegmentListResponse>(`/contact-segments${querySuffix}`);
  }

  async createContactSegment(payload: ContactSegmentCreatePayload): Promise<ContactSegment> {
    return this.request<ContactSegment>("/contact-segments/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async updateContactSegment(segmentId: string, payload: ContactSegmentUpdatePayload): Promise<ContactSegment> {
    return this.request<ContactSegment>(`/contact-segments/${segmentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  }

  async deleteContactSegment(segmentId: string): Promise<void> {
    await this.request<void>(`/contact-segments/${segmentId}`, {
      method: "DELETE",
    });
  }

  // Messages
  async getMessageJobs(params: MessageJobsQueryParams = {}): Promise<MessageJobSummary[]> {
    const searchParams = new URLSearchParams();
    if (params.status) {
      searchParams.append("status", params.status);
    }
    if (params.channel) {
      searchParams.append("channel", params.channel);
    }
    if (params.direction) {
      searchParams.append("direction", params.direction);
    }
    if (params.channel_address) {
      searchParams.append("channel_address", params.channel_address);
    }
    if (params.contact_id) {
      searchParams.append("contact_id", params.contact_id);
    }
    if (params.queue) {
      searchParams.append("queue", params.queue);
    }
    const query = searchParams.toString();
    return this.request<MessageJobSummary[]>(`/messages/jobs${query ? `?${query}` : ""}`);
  }

  async getMessageJobDetails(
    jobId: string,
    params: MessageJobDetailsQueryParams = {},
  ): Promise<MessageJobDetail> {
    const searchParams = new URLSearchParams();
    if (params.channel) {
      searchParams.append("channel", params.channel);
    }
    if (params.channel_address) {
      searchParams.append("channel_address", params.channel_address);
    }
    const query = searchParams.toString();
    return this.request<MessageJobDetail>(`/messages/jobs/${jobId}${query ? `?${query}` : ""}`);
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

  async getChannelMetrics(params: ChannelMetricsQueryParams = {}): Promise<ChannelMetricsResponse> {
    const searchParams = new URLSearchParams();
    if (params.from) {
      searchParams.append("from", params.from);
    }
    if (params.to) {
      searchParams.append("to", params.to);
    }
    const query = searchParams.toString();
    return this.request<ChannelMetricsResponse>(`/reports/channel-metrics${query ? `?${query}` : ""}`);
  }

  async getQueueMetrics(params: QueueMetricsQueryParams = {}): Promise<QueueMetricsResponse> {
    const searchParams = new URLSearchParams();
    if (params.from) {
      searchParams.append("from", params.from);
    }
    if (params.to) {
      searchParams.append("to", params.to);
    }
    const query = searchParams.toString();
    return this.request<QueueMetricsResponse>(`/reports/queues${query ? `?${query}` : ""}`);
  }

  async downloadSummary(
    format: "csv" | "json" = "csv",
    params: { from?: string; to?: string } = {},
  ): Promise<void> {
    const searchParams = new URLSearchParams();
    if (params.from) {
      searchParams.append("from", params.from);
    }
    if (params.to) {
      searchParams.append("to", params.to);
    }
    searchParams.append("format", format);
    await this.downloadFile("/reports/summary/export", {
      params: searchParams,
      fallbackFilename: `summary-report.${format}`,
    });
  }

  async downloadProviderMetrics(format: "csv" | "json" = "csv", days: number = 7): Promise<void> {
    const searchParams = new URLSearchParams();
    searchParams.append("days", days.toString());
    searchParams.append("format", format);
    await this.downloadFile("/reports/provider-metrics/export", {
      params: searchParams,
      fallbackFilename: `provider-metrics-report.${format}`,
    });
  }

  async downloadChannelMetrics(
    format: "csv" | "json" = "csv",
    params: { from?: string; to?: string } = {},
  ): Promise<void> {
    const searchParams = new URLSearchParams();
    if (params.from) {
      searchParams.append("from", params.from);
    }
    if (params.to) {
      searchParams.append("to", params.to);
    }
    searchParams.append("format", format);
    await this.downloadFile("/reports/channel-metrics/export", {
      params: searchParams,
      fallbackFilename: `channel-metrics-report.${format}`,
    });
  }

  async downloadQueueMetrics(
    format: "csv" | "json" = "csv",
    params: { from?: string; to?: string } = {},
  ): Promise<void> {
    const searchParams = new URLSearchParams();
    if (params.from) {
      searchParams.append("from", params.from);
    }
    if (params.to) {
      searchParams.append("to", params.to);
    }
    searchParams.append("format", format);
    await this.downloadFile("/reports/queues/export", {
      params: searchParams,
      fallbackFilename: `queue-metrics-report.${format}`,
    });
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
