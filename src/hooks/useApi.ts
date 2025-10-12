import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/hooks/use-toast";
import {
  AdvancedSimulationRequest,
  AdvancedSimulationResponse,
  CreateWAConnectionPayload,
  DashboardMetrics,
  Event,
  EventsQueryParams,
  ChannelMetricsResponse,
  ChannelMetricsQueryParams,
  ImportRatesResponse,
  MessageJobDetail,
  MessageJobSummary,
  MessageJobsQueryParams,
  MessageJobDetailsQueryParams,
  Organization,
  Provider,
  ProviderCredentialInput,
  ProviderHealth,
  ProviderMetric,
  IntegrationConnection,
  ConnectionTestResult,
  QueueMetricsResponse,
  QueueMetricsQueryParams,
  RateEntry,
  Rule,
  RuleCreatePayload,
  RuleUpdatePayload,
  ContactSegment,
  ContactSegmentListResponse,
  ContactSegmentCreatePayload,
  ContactSegmentUpdatePayload,
  SendMessageRequest,
  SendMessageResponse,
  SetProviderCredentialsResponse,
  SimulateRulesRequest,
  SimulateRulesResult,
  SummaryResponse,
  WAConnectionResponse,
} from "@/types/api";

// Summary
export const useSummary = (from?: string, to?: string) => {
  return useQuery<SummaryResponse, Error>({
    queryKey: ["summary", from, to],
    queryFn: () => api.getSummary(from, to),
  });
};

// Events
export const useEvents = (params?: EventsQueryParams) => {
  const queryKey = [
    "events",
    params?.limit ?? null,
    params?.from ?? null,
    params?.to ?? null,
    params?.offset ?? null,
  ];

  return useQuery<Event[], Error>({
    queryKey,
    queryFn: () => api.getEvents(params),
  });
};

// Rules
export const useRules = () => {
  return useQuery<Rule[], Error>({
    queryKey: ["rules"],
    queryFn: () => api.getRules(),
  });
};

export const useCreateRule = () => {
  const queryClient = useQueryClient();
  return useMutation<Rule, Error, RuleCreatePayload>({
    mutationFn: (payload) => api.createRule(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({ title: "Regra criada com sucesso" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao criar regra", description: error.message, variant: "destructive" });
    },
  });
};

export const useUpdateRule = () => {
  const queryClient = useQueryClient();
  return useMutation<{ status: string }, Error, { ruleId: string; updates: RuleUpdatePayload }>({
    mutationFn: ({ ruleId, updates }) => api.updateRule(ruleId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({ title: "Regra atualizada" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao atualizar regra", description: error.message, variant: "destructive" });
    },
  });
};

export const useToggleRule = () => {
  const queryClient = useQueryClient();
  return useMutation<{ is_enabled: boolean }, Error, string>({
    mutationFn: (ruleId: string) => api.toggleRule(ruleId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["rules"] });
      toast({ title: "Estado da regra alterado" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao alterar regra", description: error.message, variant: "destructive" });
    },
  });
};

export const useSimulateRules = () => {
  return useMutation<SimulateRulesResult, Error, SimulateRulesRequest>({
    mutationFn: (payload) => api.simulateRules(payload),
    onSuccess: (data) => {
      toast({
        title: "Simulação concluída",
        description: `Economia potencial: €${(data.saved / 100).toFixed(2)}`,
      });
    },
    onError: (error: Error) => {
      toast({ title: "Erro na simulação", description: error.message, variant: "destructive" });
    },
  });
};

// Rates
export const useRates = () => {
  return useQuery<RateEntry[], Error>({
    queryKey: ["rates"],
    queryFn: () => api.getRates(),
  });
};

export const useImportRatesCSV = () => {
  const queryClient = useQueryClient();
  return useMutation<ImportRatesResponse, Error, File>({
    mutationFn: (file: File) => api.importRatesCSV(file),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["rates"] });
      toast({ title: `${data.imported} tarifas importadas` });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao importar CSV", description: error.message, variant: "destructive" });
    },
  });
};

// Contact Segments
export const useContactSegments = (params?: { limit?: number; offset?: number }) => {
  return useQuery<ContactSegmentListResponse, Error>({
    queryKey: ["contactSegments", params],
    queryFn: () => api.getContactSegments(params ?? {}),
  });
};

export const useCreateContactSegment = () => {
  const queryClient = useQueryClient();
  return useMutation<ContactSegment, Error, ContactSegmentCreatePayload>({
    mutationFn: (payload) => api.createContactSegment(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contactSegments"] });
      toast({ title: "Segmento criado" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao criar segmento", description: error.message, variant: "destructive" });
    },
  });
};

export const useUpdateContactSegment = () => {
  const queryClient = useQueryClient();
  return useMutation<ContactSegment, Error, { segmentId: string; updates: ContactSegmentUpdatePayload }>({
    mutationFn: ({ segmentId, updates }) => api.updateContactSegment(segmentId, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contactSegments"] });
      toast({ title: "Segmento atualizado" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao atualizar segmento", description: error.message, variant: "destructive" });
    },
  });
};

export const useDeleteContactSegment = () => {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (segmentId) => api.deleteContactSegment(segmentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["contactSegments"] });
      toast({ title: "Segmento removido" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao remover segmento", description: error.message, variant: "destructive" });
    },
  });
};

// Organizations
export const useCurrentOrg = () => {
  return useQuery<Organization, Error>({
    queryKey: ["currentOrg"],
    queryFn: () => api.getCurrentOrg(),
  });
};

// Integrations
export const useCreateWAConnection = () => {
  return useMutation<WAConnectionResponse, Error, CreateWAConnectionPayload>({
    mutationFn: (payload) => api.createWAConnection(payload),
    onSuccess: () => {
      toast({
        title: "Conexão WhatsApp configurada",
        description: "Tokens de webhook atualizados com sucesso.",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Erro ao conectar WhatsApp",
        description: error.message,
        variant: "destructive",
      });
    },
  });
};

// Providers
export const useProviders = () => {
  return useQuery<Provider[], Error>({
    queryKey: ["providers"],
    queryFn: () => api.getProviders(),
  });
};

export const useSetProviderCredentials = () => {
  const queryClient = useQueryClient();
  return useMutation<
    SetProviderCredentialsResponse,
    Error,
    { providerId: string; credentials: ProviderCredentialInput }
  >({
    mutationFn: ({ providerId, credentials }) => api.setProviderCredentials(providerId, credentials),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });
};

export const useHealthCheckProvider = () => {
  return useMutation<ProviderHealth, Error, string>({
    mutationFn: (providerId: string) => api.healthCheckProvider(providerId),
  });
};

// Integrations
export const useConnections = () => {
  return useQuery<IntegrationConnection[], Error>({
    queryKey: ["integrationConnections"],
    queryFn: () => api.getIntegrationConnections(),
  });
};

export const useTestConnection = () => {
  const queryClient = useQueryClient();
  return useMutation<
    ConnectionTestResult,
    Error,
    { channel: string; providerId?: string }
  >({
    mutationFn: ({ channel, providerId }) =>
      api.testIntegrationConnection(channel, providerId ? { provider_id: providerId } : undefined),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["integrationConnections"] });
      toast({
        title: data.healthy ? "Conexão saudável" : "Falha no teste da conexão",
        description: data.healthy ? undefined : data.error ?? "Verifique as credenciais e tente novamente.",
        variant: data.healthy ? "default" : "destructive",
      });
    },
    onError: (error: Error) => {
      toast({
        title: "Erro ao testar conexão",
        description: error.message,
        variant: "destructive",
      });
    },
  });
};

// Messages
export const useMessageJobs = (params: MessageJobsQueryParams = {}) => {
  const { status, channel, direction, channel_address, contact_id, queue } = params;
  return useQuery<MessageJobSummary[], Error>({
    queryKey: [
      "messageJobs",
      status ?? null,
      channel ?? null,
      direction ?? null,
      channel_address ?? null,
      contact_id ?? null,
      queue ?? null,
    ],
    queryFn: () => api.getMessageJobs(params),
  });
};

export const useMessageJobDetails = (jobId: string, params: MessageJobDetailsQueryParams = {}) => {
  const { channel, channel_address } = params;
  return useQuery<MessageJobDetail, Error>({
    queryKey: ["messageJob", jobId, channel ?? null, channel_address ?? null],
    queryFn: () => api.getMessageJobDetails(jobId, params),
    enabled: !!jobId,
  });
};

export const useSendMessage = () => {
  const queryClient = useQueryClient();
  return useMutation<SendMessageResponse, Error, SendMessageRequest>({
    mutationFn: (payload) => api.sendMessage(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messageJobs"] });
      toast({ title: "Mensagem enviada com sucesso" });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao enviar mensagem", description: error.message, variant: "destructive" });
    },
  });
};

// Dashboard Metrics
export const useDashboardMetrics = () => {
  return useQuery<DashboardMetrics, Error>({
    queryKey: ["dashboardMetrics"],
    queryFn: () => api.getDashboardMetrics(),
  });
};

export const useProviderMetrics = () => {
  return useQuery<ProviderMetric[], Error>({
    queryKey: ["providerMetrics"],
    queryFn: () => api.getProviderMetrics(),
  });
};

export const useChannelMetrics = (params: ChannelMetricsQueryParams = {}) => {
  const { from, to } = params;
  return useQuery<ChannelMetricsResponse, Error>({
    queryKey: ["channelMetrics", from ?? null, to ?? null],
    queryFn: () => api.getChannelMetrics(params),
  });
};

export const useQueueMetrics = (params: QueueMetricsQueryParams = {}) => {
  const { from, to } = params;
  return useQuery<QueueMetricsResponse, Error>({
    queryKey: ["queueMetrics", from ?? null, to ?? null],
    queryFn: () => api.getQueueMetrics(params),
  });
};

// Advanced Simulator
export const useSimulateAdvanced = () => {
  return useMutation<AdvancedSimulationResponse, Error, AdvancedSimulationRequest>({
    mutationFn: (data) => api.simulateAdvanced(data),
    onSuccess: (data) => {
      toast({
        title: "Simulação concluída",
        description: `Economia potencial: €${((data.total_saved || 0) / 100).toFixed(2)}`,
      });
    },
    onError: (error: Error) => {
      toast({ title: "Erro na simulação", description: error.message, variant: "destructive" });
    },
  });
};
