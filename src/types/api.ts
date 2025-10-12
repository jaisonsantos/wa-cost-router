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

export interface ChannelBacklogMetrics {
  open: number;
  pending: number;
  closed: number;
}

export interface QueueBacklogMetrics {
  open: number;
  responded: number;
  closed: number;
  total: number;
}

export interface FirstResponseMetrics {
  average_seconds: number | null;
  sample_size: number;
}

export interface SlaMetrics {
  target_seconds: number | null;
  within_target: number;
  total_tracked: number;
  compliance_rate: number | null;
}

export interface ChannelMetric {
  channel: string;
  conversations_opened: number;
  conversations_closed: number;
  backlog: ChannelBacklogMetrics;
  first_response: FirstResponseMetrics;
  sla: SlaMetrics;
}

export interface QueueMetric {
  channel: string;
  backlog: QueueBacklogMetrics;
  first_response: FirstResponseMetrics;
  sla: SlaMetrics;
}

export type ChannelMetricsResponse = ChannelMetric[];
export type QueueMetricsResponse = QueueMetric[];

export interface ChannelMetricsQueryParams {
  from?: string;
  to?: string;
}

export interface QueueMetricsQueryParams {
  from?: string;
  to?: string;
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

export type MessageDirection = "inbound" | "outbound";

export interface MessageJobConversationEntry {
  id: string;
  direction: MessageDirection;
  channel: string;
  channel_address: string;
  content: string;
  timestamp: string;
  status?: string | null;
  sender?: string | null;
}

export interface MessageJobConversationHistory {
  channel: string;
  contact_address: string;
  contact_name?: string | null;
  messages: MessageJobConversationEntry[];
}

export interface MessageJobSummary {
  id: string;
  status: string;
  direction: MessageDirection;
  channel: string;
  channel_address: string;
  contact_id?: string | null;
  contact_name?: string | null;
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
  conversation_history?: MessageJobConversationHistory[];
}

export interface Event {
  id: string;
  direction: string;
  channel?: string | null;
  channel_address?: string | null;
  template_name?: string | null;
  category?: string | null;
  country_iso?: string | null;
  timestamp_provider: string;
  delivery_status?: string | null;
  unit_cost_minor?: number | null;
  currency?: string | null;
}

export interface ProviderFormField {
  key: string;
  label: string;
  type: "text" | "password" | "tel" | "email" | "select";
  placeholder?: string;
  description?: string;
  required?: boolean;
  mask?: string;
  help_text?: string;
  options?: { label: string; value: string }[];
  validation?: { regex?: string; message?: string };
  default_value?: string;
}

export interface ProviderFormSchema {
  title?: string;
  description?: string;
  fields: ProviderFormField[];
  consent_guidance?: string[];
  testing_instructions?: string[];
}

export interface Provider {
  id: string;
  name: string;
  type: string;
  status: string;
  is_configured: boolean;
  has_credentials: boolean;
  avg_latency_ms?: number | null;
  metadata: Record<string, unknown>;
  required_fields: string[];
  provider_form_schema: ProviderFormSchema;
}

export type ProviderCredentialInput = Record<string, string | number | boolean>;

export interface IntegrationHealthSnapshot {
  healthy: boolean;
  status_code?: string | number | null;
  latency_ms?: number | null;
  error?: string | null;
  checked_at?: string | null;
  details?: Record<string, unknown>;
}

export interface IntegrationConnection {
  id: string;
  channel: string;
  display_name: string;
  status: string;
  connected: boolean;
  has_credentials: boolean;
  metadata: Record<string, unknown>;
  last_health_check: IntegrationHealthSnapshot | null;
}

export interface ConnectionTestResult {
  channel: string;
  status: string;
  healthy: boolean;
  status_code?: string | number | null;
  latency_ms?: number | null;
  error?: string | null;
  checked_at: string;
  metadata: Record<string, unknown>;
}

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

export interface SegmentAttributeRule {
  key: string;
  operator: "equals" | "not_equals" | "contains" | "in";
  values: string[];
}

export interface SegmentBehaviorRule {
  requireConsent: boolean;
  includeOptedOut: boolean;
  holdoutPercentage?: number | null;
}

export interface SegmentCriteria {
  attributes?: SegmentAttributeRule[];
  tags?: string[];
  behavior?: SegmentBehaviorRule;
  [key: string]: unknown;
}

export interface SegmentLimits {
  max_daily_messages?: number | null;
  max_weekly_messages?: number | null;
  max_monthly_messages?: number | null;
}

export interface SegmentOptOutPolicy {
  enforce: boolean;
  global_opt_out: boolean;
  channels: string[];
  grace_period_hours?: number | null;
}

export interface SegmentPolicy {
  limits: SegmentLimits;
  opt_out: SegmentOptOutPolicy;
}

export interface ContactSegment extends ContactSegmentSummary {
  slug: string;
  name: string;
  org_id: string;
  criteria?: SegmentCriteria | null;
  source: string;
  source_metadata?: Record<string, unknown> | null;
  proof_hash?: string | null;
  created_at: string;
  updated_at: string;
  policy?: SegmentPolicy | null;
}

export interface ContactSegmentListResponse {
  items: ContactSegment[];
  limit: number;
  offset: number;
  count: number;
}

export interface ContactSegmentCreatePayload {
  slug: string;
  name: string;
  description?: string | null;
  criteria?: SegmentCriteria | null;
  source?: string;
  source_metadata?: Record<string, unknown> | null;
  proof_hash?: string | null;
}

export type ContactSegmentUpdatePayload = Partial<ContactSegmentCreatePayload>;

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

export type ContactImportStatus = "pending" | "validating" | "processing" | "completed" | "failed";

export interface ContactImportJob {
  id: string;
  org_id: string;
  requested_by: string;
  input_uri: string | null;
  status: ContactImportStatus;
  total_rows: number;
  processed_rows: number;
  error_rows: number;
  error_report_uri: string | null;
  source: string;
  source_metadata: Record<string, unknown> | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
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

export interface SimulateRulesRequest {
  countries: string[];
  volumes: Record<string, number>;
  category: string;
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
  channel?: string;
  direction?: MessageDirection;
  channel_address?: string;
  contact_id?: string;
  queue?: string;
}

export interface MessageJobDetailsQueryParams {
  channel?: string;
  channel_address?: string;
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
  channel: string;
  template_id: string;
  template_category: string;
  variables: Record<string, unknown>;
  contact_id?: string;
  channel_address?: string;
  to_number?: string;
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
