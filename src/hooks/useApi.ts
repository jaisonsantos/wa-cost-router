import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/hooks/use-toast";

// Summary
export const useSummary = (from?: string, to?: string) => {
  return useQuery({
    queryKey: ["summary", from, to],
    queryFn: () => api.getSummary(from, to),
  });
};

// Events
export const useEvents = (params?: Parameters<typeof api.getEvents>[0]) => {
  return useQuery({
    queryKey: ["events", params],
    queryFn: () => api.getEvents(params),
  });
};

// Rules
export const useRules = () => {
  return useQuery({
    queryKey: ["rules"],
    queryFn: () => api.getRules(),
  });
};

export const useCreateRule = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.createRule.bind(api),
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
  return useMutation({
    mutationFn: ({ ruleId, updates }: { ruleId: string; updates: any }) =>
      api.updateRule(ruleId, updates),
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
  return useMutation({
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
  return useMutation({
    mutationFn: () => api.simulateRules(),
    onSuccess: (data: any) => {
      toast({
        title: "Simulação concluída",
        description: `Economia potencial: €${(data.potential_saved_minor / 100).toFixed(2)}`,
      });
    },
    onError: (error: Error) => {
      toast({ title: "Erro na simulação", description: error.message, variant: "destructive" });
    },
  });
};

// Rates
export const useRates = () => {
  return useQuery({
    queryKey: ["rates"],
    queryFn: () => api.getRates(),
  });
};

export const useImportRatesCSV = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.importRatesCSV(file),
    onSuccess: (data: any) => {
      queryClient.invalidateQueries({ queryKey: ["rates"] });
      toast({ title: `${data.imported} tarifas importadas` });
    },
    onError: (error: Error) => {
      toast({ title: "Erro ao importar CSV", description: error.message, variant: "destructive" });
    },
  });
};

// Organizations
export const useCurrentOrg = () => {
  return useQuery({
    queryKey: ["currentOrg"],
    queryFn: () => api.getCurrentOrg(),
  });
};

// Integrations
export const useCreateWAConnection = () => {
  return useMutation({
    mutationFn: api.createWAConnection.bind(api),
    onSuccess: () => {
      toast({ title: "Conexão WhatsApp configurada" });
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
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => api.getProviders(),
  });
};

export const useSetProviderCredentials = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider_id, credentials }: { provider_id: string; credentials: any }) =>
      api.setProviderCredentials(provider_id, credentials),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
    },
  });
};

export const useHealthCheckProvider = () => {
  return useMutation({
    mutationFn: (providerId: string) => api.healthCheckProvider(providerId),
  });
};

// Messages
export const useMessageJobs = (params?: { status?: string }) => {
  return useQuery({
    queryKey: ["messageJobs", params],
    queryFn: () => api.getMessageJobs(params),
  });
};

export const useMessageJobDetails = (jobId: string) => {
  return useQuery({
    queryKey: ["messageJob", jobId],
    queryFn: () => api.getMessageJobDetails(jobId),
    enabled: !!jobId,
  });
};

export const useSendMessage = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: api.sendMessage.bind(api),
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
  return useQuery({
    queryKey: ["dashboardMetrics"],
    queryFn: () => api.getDashboardMetrics(),
  });
};

export const useProviderMetrics = () => {
  return useQuery({
    queryKey: ["providerMetrics"],
    queryFn: () => api.getProviderMetrics(),
  });
};

// Advanced Simulator
export const useSimulateAdvanced = () => {
  return useMutation({
    mutationFn: (data: { countries: string[]; volumes: Record<string, number>; category: string }) => 
      api.simulateAdvanced(data),
    onSuccess: (data: any) => {
      toast({
        title: "Simulação concluída",
        description: `Economia potencial: €${((data.total_savings || 0) / 100).toFixed(2)}`,
      });
    },
    onError: (error: Error) => {
      toast({ title: "Erro na simulação", description: error.message, variant: "destructive" });
    },
  });
};
