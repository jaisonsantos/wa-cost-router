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
  ImportRatesResponse,
  MessageJobDetail,
  MessageJobSummary,
  MessageJobsQueryParams,
  Organization,
  Provider,
  ProviderCredentialInput,
  ProviderHealth,
  ProviderMetric,
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
  return useQuery<Event[], Error>({
    queryKey: ["events", params],
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
  return useMutation<SimulateRulesResult, Error, void>({
    mutationFn: () => api.simulateRules(),
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

// Messages
export const useMessageJobs = (params?: MessageJobsQueryParams) => {
  return useQuery<MessageJobSummary[], Error>({
    queryKey: ["messageJobs", params],
    queryFn: () => api.getMessageJobs(params),
  });
};

export const useMessageJobDetails = (jobId: string) => {
  return useQuery<MessageJobDetail, Error>({
    queryKey: ["messageJob", jobId],
    queryFn: () => api.getMessageJobDetails(jobId),
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
