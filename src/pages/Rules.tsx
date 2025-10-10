import { useEffect, useMemo, useRef, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import SimpleLayout from "@/components/SimpleLayout";
import AdvancedSimulator from "@/components/AdvancedSimulator";
import RuleFormDialog, { RuleFormRule, RulePayload } from "@/components/RuleFormDialog";
import {
  useRules,
  useToggleRule,
  useSimulateRules,
  useCreateRule,
  useUpdateRule,
  useProviders,
  useDashboardMetrics,
} from "@/hooks/useApi";
import {
  Plus,
  Edit,
  PlayCircle,
  Target,
  TrendingDown,
  MessageSquare,
  Zap,
} from "lucide-react";
import { Provider, Rule, RuleActions, RuleCondition, SimulateRulesRequest } from "@/types/api";

type RuleLike = Rule & {
  rule_id?: string;
  conditions_json?: RuleCondition[];
  actions_json?: RuleActions;
};

const isRuleActions = (value: unknown): value is RuleFormRule["actions"] =>
  typeof value === "object" && value !== null;

const normalizeRule = (rule?: RuleLike | null): RuleFormRule | null => {
  if (!rule) {
    return null;
  }

  const id = rule.id ?? rule.rule_id;
  if (!id) {
    return null;
  }

  const conditions: RuleCondition[] = Array.isArray(rule.conditions)
    ? rule.conditions
    : Array.isArray(rule.conditions_json)
      ? rule.conditions_json
      : [];

  const actionsSource = rule.actions ?? rule.actions_json ?? {};
  const actions: RuleFormRule["actions"] = isRuleActions(actionsSource) ? actionsSource : {};

  return {
    id,
    name: rule.name ?? "Regra sem nome",
    is_enabled: rule.is_enabled ?? false,
    priority: rule.priority ?? 100,
    conditions,
    actions,
  };
};

const getConditionValues = (rule: RuleFormRule, type: string) =>
  rule.conditions
    .filter((condition) => condition?.type === type)
    .flatMap((condition) => (Array.isArray(condition?.values) ? condition!.values! : []));

const getCategoryColor = (category: string) => {
  switch (category.toLowerCase()) {
    case "marketing":
      return "bg-warning/10 text-warning border-warning/20";
    case "utility":
      return "bg-primary/10 text-primary border-primary/20";
    case "authentication":
      return "bg-success/10 text-success border-success/20";
    default:
      return "bg-muted/10 text-muted-foreground border-border";
  }
};

const Rules = () => {
  const { data: rulesData, isLoading } = useRules();
  const { data: providersData } = useProviders();
  const { data: dashboardMetrics } = useDashboardMetrics();
  const toggleRule = useToggleRule();
  const simulate = useSimulateRules();
  const createRule = useCreateRule();
  const updateRule = useUpdateRule();

  const [isFormOpen, setIsFormOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<RuleFormRule | null>(null);

  const providers: Provider[] = useMemo(() => providersData ?? [], [providersData]);

  const providerOptions = useMemo(
    () =>
      providers.map((provider) => ({
        id: provider.id,
        name: provider.name,
        status: provider.status,
      })),
    [providers],
  );

  const providerMap = useMemo(() => {
    const map = new Map<string, { name: string; status?: string }>();
    providerOptions.forEach((provider) => {
      map.set(provider.id, { name: provider.name, status: provider.status });
    });
    return map;
  }, [providerOptions]);

  const rules = useMemo(() => {
    const list: RuleLike[] = rulesData ?? [];
    return list
      .map((rule) => normalizeRule(rule))
      .filter((rule): rule is RuleFormRule => Boolean(rule))
      .sort((a, b) => a.priority - b.priority);
  }, [rulesData]);

  const defaultCategory = useMemo(
    () => dashboardMetrics?.top_templates?.[0]?.category?.toLowerCase() ?? "marketing",
    [dashboardMetrics],
  );

  const defaultSimulationPayload = useMemo<SimulateRulesRequest | null>(() => {
    const topCountries = dashboardMetrics?.top_countries ?? [];

    if (topCountries.length === 0) {
      return null;
    }

    const volumes = topCountries.reduce<Record<string, number>>((acc, country) => {
      if (country.country) {
        acc[country.country] = country.count;
      }
      return acc;
    }, {});

    const countries = Object.keys(volumes);

    if (countries.length === 0) {
      return null;
    }

    return {
      countries,
      volumes,
      category: defaultCategory,
    };
  }, [dashboardMetrics, defaultCategory]);

  const lastSimulationKey = useRef<string | null>(null);

  useEffect(() => {
    if (!defaultSimulationPayload) {
      return;
    }

    const payloadKey = JSON.stringify(defaultSimulationPayload);
    if (lastSimulationKey.current !== payloadKey) {
      simulate.mutate(defaultSimulationPayload);
      lastSimulationKey.current = payloadKey;
    }
  }, [defaultSimulationPayload, simulate]);

  const handleToggle = async (ruleId: string) => {
    await toggleRule.mutateAsync(ruleId);
  };

  const handleSimulate = async () => {
    if (!defaultSimulationPayload) {
      return;
    }

    await simulate.mutateAsync(defaultSimulationPayload);
  };

  const handleOpenCreate = () => {
    setEditingRule(null);
    setIsFormOpen(true);
  };

  const handleEdit = (rule: RuleFormRule) => {
    setEditingRule(rule);
    setIsFormOpen(true);
  };

  const handleFormSubmit = async (payload: RulePayload) => {
    if (editingRule) {
      await updateRule.mutateAsync({ ruleId: editingRule.id, updates: payload });
    } else {
      await createRule.mutateAsync(payload);
    }
  };

  const handleFormOpenChange = (open: boolean) => {
    setIsFormOpen(open);
    if (!open) {
      setEditingRule(null);
    }
  };

  if (isLoading) {
    return (
      <SimpleLayout>
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <div className="grid gap-6">
            {[...Array(3)].map((_, index) => (
              <Skeleton key={index} className="h-48 w-full" />
            ))}
          </div>
        </div>
      </SimpleLayout>
    );
  }

  const activeRules = rules.filter((rule) => rule.is_enabled).length;
  const quickSimulation = simulate.data;
  const totalSavings = (quickSimulation?.saved ?? 0) / 100;
  const baselineCost = (quickSimulation?.baseline ?? 0) / 100;
  const optimizedCost = (quickSimulation?.optimized ?? 0) / 100;
  const totalMessages = dashboardMetrics?.total_messages ?? 0;
  const quickSavingsPct = quickSimulation?.baseline
    ? ((quickSimulation.saved / quickSimulation.baseline) * 100).toFixed(1)
    : "0.0";
  const isSubmitting = createRule.isPending || updateRule.isPending;

  return (
    <SimpleLayout>
      <div className="space-y-6">
        {/* Header com métricas */}
        <div className="grid gap-6 md:grid-cols-4">
          <Card className="bg-gradient-to-br from-success/10 to-background border-success/20">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Economia Potencial</p>
                  <p className="text-2xl font-bold text-success">
                    €{totalSavings.toFixed(2)}
                  </p>
                  {quickSimulation?.baseline ? (
                    <p className="text-xs text-muted-foreground">
                      {quickSavingsPct}% vs baseline de €{baselineCost.toFixed(2)}
                    </p>
                  ) : (
                    <p className="text-xs text-muted-foreground">Aguardando simulação rápida</p>
                  )}
                </div>
                <TrendingDown className="h-8 w-8 text-success" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Mensagens Roteadas</p>
                  <p className="text-2xl font-bold">{totalMessages.toLocaleString()}</p>
                </div>
                <MessageSquare className="h-8 w-8 text-primary" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-muted-foreground">Regras Ativas</p>
                  <p className="text-2xl font-bold">{activeRules}/{rules.length}</p>
                </div>
                <Zap className="h-8 w-8 text-warning" />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-6">
              <Button
                className="w-full bg-gradient-to-r from-primary to-primary/80"
                size="lg"
                onClick={handleOpenCreate}
              >
                <Plus className="mr-2 h-5 w-5" />
                Nova Regra
              </Button>
              {providerOptions.length === 0 && (
                <p className="mt-3 text-xs text-muted-foreground">
                  Configure ao menos um provedor ativo para criar regras de roteamento.
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Lista de regras */}
        <div className="space-y-4">
          {rules.length === 0 ? (
            <Card>
              <CardContent className="p-12 text-center">
                <Target className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
                <h3 className="mb-2 text-lg font-semibold">Nenhuma regra criada</h3>
                <p className="mb-4 text-muted-foreground">
                  Crie sua primeira regra de roteamento para começar a economizar.
                </p>
                <Button className="bg-gradient-to-r from-primary to-primary/80" onClick={handleOpenCreate}>
                  <Plus className="mr-2 h-4 w-4" />
                  Criar Primeira Regra
                </Button>
              </CardContent>
            </Card>
          ) : (
            rules.map((rule) => {
              const countryValues = getConditionValues(rule, "country");
              const categoryValues = getConditionValues(rule, "category");
              const templateValues = getConditionValues(rule, "template");
              const primaryProviderId = rule.actions?.primary_provider as string | undefined;
              const primaryProvider = primaryProviderId ? providerMap.get(primaryProviderId) : undefined;
              const fallbackChain = Array.isArray(rule.actions?.fallback_chain)
                ? (rule.actions?.fallback_chain as string[])
                : [];

              return (
                <Card key={rule.id} className="transition-shadow hover:shadow-md">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div className="flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-3">
                          <CardTitle className="text-xl">{rule.name}</CardTitle>
                          <Badge variant="outline" className="text-xs">
                            Prioridade {rule.priority}
                          </Badge>
                          <Switch
                            checked={rule.is_enabled}
                            onCheckedChange={() => handleToggle(rule.id)}
                            disabled={toggleRule.isPending}
                          />
                        </div>
                        {primaryProviderId && (
                          <p className="text-xs text-muted-foreground">
                            Regra vinculada ao provedor {primaryProvider?.name ?? primaryProviderId}.
                          </p>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        <Button variant="ghost" size="sm" onClick={() => handleEdit(rule)}>
                          <Edit className="h-4 w-4" />
                          <span className="sr-only">Editar</span>
                        </Button>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    {/* Condições */}
                    <div>
                      <h4 className="mb-2 flex items-center text-sm font-semibold">
                        <Target className="mr-2 h-4 w-4 text-primary" />
                        Condições
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {countryValues.length > 0 && (
                          <Badge variant="outline">Países: {countryValues.join(", ")}</Badge>
                        )}
                        {categoryValues.length > 0 &&
                          categoryValues.map((category) => (
                            <Badge key={category} className={getCategoryColor(category)}>
                              {category}
                            </Badge>
                          ))}
                        {templateValues.length > 0 && (
                          <Badge variant="outline">Templates: {templateValues.join(", ")}</Badge>
                        )}
                        {countryValues.length === 0 &&
                          categoryValues.length === 0 &&
                          templateValues.length === 0 && (
                            <Badge variant="outline">Sem filtros específicos</Badge>
                          )}
                      </div>
                    </div>

                    <Separator />

                    {/* Ações */}
                    <div>
                      <h4 className="mb-2 flex items-center text-sm font-semibold">
                        <Zap className="mr-2 h-4 w-4 text-warning" />
                        Ações
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {primaryProviderId ? (
                          <Badge className="border-primary/20 bg-primary/10 text-primary">
                            Primário: {primaryProvider?.name ?? primaryProviderId}
                          </Badge>
                        ) : (
                          <Badge variant="outline">Defina um provedor principal</Badge>
                        )}

                        {fallbackChain.length > 0 ? (
                          fallbackChain.map((providerId, index) => {
                            const provider = providerMap.get(providerId);
                            return (
                              <Badge key={providerId} variant="outline">
                                {index + 1}º fallback: {provider?.name ?? providerId}
                              </Badge>
                            );
                          })
                        ) : (
                          <Badge variant="outline">Sem fallback configurado</Badge>
                        )}
                      </div>
                    </div>

                    {/* Estatísticas */}
                    <div className="border-t pt-4 text-sm text-muted-foreground">
                      Telemetria por regra ainda não está disponível. Utilize o simulador abaixo para projetar impacto de custo.
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>

        {/* Simulador Avançado */}
        <AdvancedSimulator
          defaultCountries={defaultSimulationPayload?.countries.map((country) => ({
            country,
            volume: defaultSimulationPayload.volumes[country],
          }))}
          defaultCategory={defaultCategory}
        />

        {/* Simulação Rápida */}
        {rules.length > 0 && (
          <Card className="border-primary/20 bg-gradient-to-r from-primary/5 to-success/5">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="flex items-center text-lg font-semibold">
                    <PlayCircle className="mr-2 h-5 w-5 text-primary" />
                    Simulação Rápida
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Teste rapidamente o impacto das regras atuais usando volumes reais dos principais países.
                  </p>
                  {quickSimulation && (
                    <div className="mt-4 grid gap-4 md:grid-cols-3 text-sm">
                      <div className="rounded-lg border bg-background p-3">
                        <p className="text-muted-foreground">Baseline</p>
                        <p className="text-lg font-semibold">€{baselineCost.toFixed(2)}</p>
                      </div>
                      <div className="rounded-lg border bg-background p-3">
                        <p className="text-muted-foreground">Otimizado</p>
                        <p className="text-lg font-semibold text-success">€{optimizedCost.toFixed(2)}</p>
                      </div>
                      <div className="rounded-lg border bg-background p-3">
                        <p className="text-muted-foreground">Economia</p>
                        <p className="text-lg font-semibold text-success">€{totalSavings.toFixed(2)}</p>
                      </div>
                    </div>
                  )}
                </div>
                <Button
                  onClick={handleSimulate}
                  disabled={simulate.isPending || !defaultSimulationPayload}
                  variant="outline"
                >
                  <PlayCircle className="mr-2 h-4 w-4" />
                  {simulate.isPending ? "Simulando..." : "Executar"}
                </Button>
              </div>
              {simulate.isError && (
                <p className="mt-3 text-sm text-destructive">
                  {(simulate.error as Error | undefined)?.message ?? "Não foi possível executar a simulação."}
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Sugestões */}
        <Card className="border-warning/20 bg-gradient-to-br from-warning/5 to-background">
          <CardContent className="p-6">
            <div className="flex items-start space-x-4">
              <div className="rounded-lg bg-warning/10 p-3">
                <TrendingDown className="h-6 w-6 text-warning" />
              </div>
              <div className="flex-1">
                <h3 className="mb-2 text-lg font-semibold">Sugestão de Otimização</h3>
                <p className="mb-4 text-muted-foreground">
                  Com as regras atuais economizando cerca de {quickSavingsPct}% nos países com maior volume, avalie simulações
                  avançadas para mapear provedores alternativos e ampliar a economia.
                </p>
                <Button variant="outline" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
                  Configurar simulação avançada
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <RuleFormDialog
        open={isFormOpen}
        onOpenChange={handleFormOpenChange}
        providers={providerOptions}
        initialRule={editingRule}
        onSubmit={handleFormSubmit}
        isSubmitting={isSubmitting}
      />
    </SimpleLayout>
  );
};

export default Rules;
