export interface SummaryResponse {
  cost_7d_minor: number;
  saved_7d_minor: number;
  pct_saved: number;
}

export interface DashboardAlert {
  type: string;
  message: string;
  action?: string;
}

export interface DashboardCountryMetric {
  country: string;
  cost_minor: number;
  count: number;
}

export interface DashboardTemplateMetric {
  template: string;
  cost_minor: number;
  count: number;
}

export interface DashboardMetrics {
  total_messages: number;
  total_cost_minor: number;
  baseline_cost_minor: number;
  saved_minor: number;
  success_rate: number;
  avg_latency_ms: number;
  top_countries: DashboardCountryMetric[];
  top_templates: DashboardTemplateMetric[];
  alerts: DashboardAlert[];
  recommendations: string[];
}

export interface ProviderMetric {
  provider_id: string;
  provider_name: string;
  total_sent: number;
  success_rate: number;
  avg_latency_ms: number;
  total_cost_minor: number;
}

export interface MessageJobAttempt {
  id: string;
  attempt_number: number;
  status: string;
  provider_id: string;
  provider_name: string;
  latency_ms: number | null;
  error_code?: string | null;
  error_message?: string | null;
  timestamp?: string | null;
}

export interface MessageJobSummary {
  id: string;
  status: string;
  to_number: string;
  template_id: string;
  template_category: string;
  country_iso: string | null;
  created_at: string;
  total_cost_minor?: number | null;
}

export interface MessageJobDetail extends MessageJobSummary {
  attempts: MessageJobAttempt[];
  total_cost_minor: number;
}

export interface Event {
  id: string;
  direction: string;
  template_name?: string | null;
  category?: string | null;
  country_iso?: string | null;
  timestamp_provider: string;
  delivery_status?: string | null;
  unit_cost_minor?: number | null;
  currency?: string | null;
}

export interface Provider {
  id: string;
  name: string;
  type: string;
  status: string;
  is_configured: boolean;
  has_credentials: boolean;
  avg_latency_ms?: number | null;
}

export type ProviderCredentialInput = Record<string, unknown>;

export type ContactStatus = "active" | "inactive" | "archived";

export type OptInStatus = "granted" | "revoked" | "pending";

export interface ContactOptIn {
  id: string;
  channel: string;
  channel_address: string;
  status: OptInStatus;
  version: number;
  captured_at: string;
  source: string;
  legal_basis?: string | null;
  evidence_uri?: string | null;
  proof_hash?: string | null;
}

export interface ContactSegmentSummary {
  id: string;
  name: string;
  slug?: string;
  description?: string | null;
}

export interface ContactNote {
  id: string;
  author: string;
  content: string;
  created_at: string;
  updated_at?: string;
  visibility?: "internal" | "shared";
  tags?: string[];
}

export interface Contact {
  id: string;
  org_id: string;
  external_id?: string | null;
  full_name?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  phone?: string | null;
  status: ContactStatus;
  attributes?: Record<string, unknown> | null;
  source: string;
  source_metadata?: Record<string, unknown> | null;
  proof_hash?: string | null;
  created_at: string;
  updated_at: string;
  channel_opt_ins?: ContactOptIn[];
  segments?: ContactSegmentSummary[];
  notes?: ContactNote[];
}

export interface ContactListResponse {
  items: Contact[];
  limit: number;
  offset: number;
  count: number;
}

export interface ContactConsentAuditItem {
  id: string;
  opt_in_id?: string | null;
  opt_in_version?: number | null;
  channel: string;
  channel_address: string;
  status: OptInStatus;
  source: string;
  agent: string;
  request_ip?: string | null;
  recorded_at: string;
  evidence_uri?: string | null;
  proof_hash?: string | null;
  context?: Record<string, unknown> | null;
}

export interface ContactConsentHistoryResponse {
  items: ContactConsentAuditItem[];
  count: number;
}

export interface ProviderHealth {
  provider_id: string;
  provider_name: string;
  healthy: boolean;
  status_code?: number | string | null;
  latency_ms?: number | null;
  error?: string | null;
}

export interface RuleCondition {
  type?: string;
  values?: string[];
  [key: string]: unknown;
}

export interface RuleActions {
  primary_provider?: string;
  fallback_chain?: string[];
  [key: string]: unknown;
}

export interface Rule {
  id: string;
  name: string;
  is_enabled: boolean;
  priority: number;
  conditions: RuleCondition[];
  actions: RuleActions;
}

export interface RuleUpdatePayload {
  name: string;
  is_enabled: boolean;
  priority: number;
  conditions: RuleCondition[];
  actions: RuleActions;
}

export type RuleCreatePayload = RuleUpdatePayload;

export interface SimulateRulesResult {
  baseline: number;
  optimized: number;
  saved: number;
}

export interface AdvancedSimulationProviderBreakdown {
  provider_id: string;
  provider_name: string;
  cost_minor: number;
  available: boolean;
}

export interface AdvancedSimulationCountryBreakdown {
  country: string;
  volume: number;
  baseline_cost: number;
  optimized_cost: number;
  saved: number;
  providers: AdvancedSimulationProviderBreakdown[];
  recommended_provider: string;
}

export interface AdvancedSimulationRequest {
  countries: string[];
  volumes: Record<string, number>;
  category: string;
}

export interface AdvancedSimulationResponse {
  total_baseline: number;
  total_optimized: number;
  total_saved: number;
  breakdown: AdvancedSimulationCountryBreakdown[];
  recommended_route: Record<string, string>;
}

export interface RateEntry {
  id: string;
  provider_id: string;
  provider_name: string;
  effective_from: string;
  country_iso: string;
  category: string;
  template_name?: string | null;
  unit_cost_minor: number;
  currency: string;
}

export interface ImportRatesResponse {
  imported: number;
}

export interface Organization {
  id: string;
  name: string;
  user_email: string;
  role: string;
}

export interface EventsQueryParams {
  limit?: number;
  offset?: number;
  country?: string;
  template?: string;
  from?: string;
  to?: string;
}

export interface MessageJobsQueryParams {
  status?: string;
}

export interface CreateWAConnectionPayload {
  business_id: string;
  phone_id: string;
  access_token: string;
  webhook_verify_token: string;
  webhook_secret: string;
}

export interface WAConnectionResponse {
  id: string;
  status: string;
}

export interface SetProviderCredentialsResponse {
  status: string;
}

export interface ProviderCredentialsRequest {
  providerId: string;
  credentials: ProviderCredentialInput;
}

export interface SendMessageRequest {
  idempotency_key: string;
  to_number: string;
  template_id: string;
  template_category: string;
  variables: Record<string, unknown>;
  country_iso?: string;
}

export interface SendMessageResponse {
  job_id: string;
  status: string;
  provider_used?: string | null;
  estimated_cost?: number | null;
  message: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}
