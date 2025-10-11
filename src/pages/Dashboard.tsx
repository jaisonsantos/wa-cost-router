import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import MetricCard from "@/components/MetricCard";
import SimpleLayout from "@/components/SimpleLayout";
import ChannelMetricCard from "@/components/ChannelMetricCard";
import { Skeleton } from "@/components/ui/skeleton";
import { useDashboardMetrics, useProviderMetrics, useChannelMetrics, useQueueMetrics } from "@/hooks/useApi";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  TrendingDown,
  MessageSquare,
  Globe,
  AlertTriangle,
  ArrowRight,
  Target,
  BarChart3,
  Activity,
  Zap,
  ShieldCheck,
  TimerReset,
  BellRing,
  Signal,
} from "lucide-react";
import { ChannelMetric, DashboardMetrics, ProviderMetric, QueueMetric } from "@/types/api";

const formatCurrency = (valueMinor: number) => `€${(valueMinor / 100).toFixed(2)}`;

const getFlagEmoji = (countryIso?: string) => {
  if (!countryIso) {
    return "🌐";
  }

  const upper = countryIso.toUpperCase();
  if (!/^[A-Z]{2}$/.test(upper)) {
    return "🌐";
  }

  const codePoints = [...upper].map((char) => 127397 + char.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
};

const formatChannelName = (channel: string) =>
  channel
    .split(/[_-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");

interface ChannelSpecificAlert {
  channel: string;
  message: string;
  severity: "warning" | "critical";
}

const generateChannelAlerts = (metric: ChannelMetric, queueMetric?: QueueMetric): ChannelSpecificAlert[] => {
  const alerts: ChannelSpecificAlert[] = [];
  const channelLabel = formatChannelName(metric.channel);
  const complianceRate = metric.sla.compliance_rate;

  if (complianceRate !== null) {
    if (complianceRate < 70) {
      alerts.push({
        channel: metric.channel,
        message: `${channelLabel} está com apenas ${complianceRate.toFixed(1)}% dentro do SLA.`,
        severity: "critical",
      });
    } else if (complianceRate < 85) {
      alerts.push({
        channel: metric.channel,
        message: `${channelLabel} apresenta queda de SLA (${complianceRate.toFixed(1)}%).`,
        severity: "warning",
      });
    }
  }

  const targetSeconds = metric.sla.target_seconds;

  if (
    metric.first_response.average_seconds !== null &&
    targetSeconds !== null &&
    metric.first_response.average_seconds > targetSeconds
  ) {
    const roundedTarget = Math.round(targetSeconds);
    alerts.push({
      channel: metric.channel,
      message: `Tempo médio de primeira resposta (${metric.first_response.average_seconds.toFixed(0)}s) excede a meta de ${roundedTarget}s.`,
      severity: "warning",
    });
  }

  const openItems = queueMetric?.backlog.open ?? metric.backlog.open;
  if (openItems >= 15) {
    alerts.push({
      channel: metric.channel,
      message: `${channelLabel} acumula ${openItems} conversas abertas aguardando atendimento.`,
      severity: "critical",
    });
  } else if (openItems >= 8) {
    alerts.push({
      channel: metric.channel,
      message: `${channelLabel} possui ${openItems} conversas abertas no backlog.`,
      severity: "warning",
    });
  }

  return alerts;
};

const Dashboard = () => {
  const navigate = useNavigate();
  const {
    data: metricsData,
    isLoading: metricsLoading,
    isError: metricsError,
    error,
  } = useDashboardMetrics();
  const {
    data: providersData,
    isLoading: providersLoading,
    isError: providersError,
  } = useProviderMetrics();
  const {
    data: channelMetricsData,
    isLoading: channelLoading,
    isError: channelError,
    error: channelErrorData,
  } = useChannelMetrics();
  const {
    data: queueMetricsData,
    isLoading: queueLoading,
    isError: queueError,
    error: queueErrorData,
  } = useQueueMetrics();

  const dashboard: DashboardMetrics | undefined = metricsData;
  const providers: ProviderMetric[] = providersData ?? [];
  const channelMetrics: ChannelMetric[] = channelMetricsData ?? [];
  const queueByChannel = useMemo(() => {
    const grouped: Record<string, QueueMetric> = {};
    (queueMetricsData ?? []).forEach((item) => {
      grouped[item.channel] = item;
    });
    return grouped;
  }, [queueMetricsData]);
  const channelSpecificAlerts = useMemo(
    () =>
      channelMetricsData
        ? channelMetricsData.flatMap((metric) => generateChannelAlerts(metric, queueByChannel[metric.channel]))
        : [],
    [channelMetricsData, queueByChannel],
  );
  const channelSectionLoading = channelLoading || queueLoading;
  const channelSectionError = channelError || queueError;
  const channelErrorMessage =
    ((channelErrorData as Error | undefined)?.message ??
      (queueErrorData as Error | undefined)?.message) ||
    "Não foi possível carregar métricas por canal.";

  if (metricsLoading) {
    return (
      <SimpleLayout>
        <div className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Card key={i}>
                <CardContent className="p-6">
                  <Skeleton className="h-20 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </SimpleLayout>
    );
  }

  if (metricsError) {
    return (
      <SimpleLayout>
        <Card className="border-destructive/40 bg-destructive/5">
          <CardContent className="p-6 space-y-2 text-destructive">
            <h2 className="text-lg font-semibold">Não foi possível carregar as métricas do dashboard</h2>
            <p className="text-sm text-destructive/80">
              {(error as Error | undefined)?.message ?? "Tente novamente mais tarde."}
            </p>
          </CardContent>
        </Card>
      </SimpleLayout>
    );
  }

  const savedMinor = dashboard?.saved_minor ?? 0;
  const totalCostMinor = dashboard?.total_cost_minor ?? 0;
  const baselineCostMinor = dashboard?.baseline_cost_minor ?? 0;
  const successRate = dashboard?.success_rate ?? 0;
  const avgLatency = dashboard?.avg_latency_ms ?? 0;
  const totalMessages = dashboard?.total_messages ?? 0;

  const pctSaved = baselineCostMinor > 0 ? (savedMinor / baselineCostMinor) * 100 : 0;

  const metrics = [
    {
      title: "Economia Total (período)",
      value: formatCurrency(savedMinor),
      change: baselineCostMinor > 0 ? `${pctSaved.toFixed(1)}% vs. baseline` : "Sem baseline registrado",
      changeType: savedMinor > 0 ? ("positive" as const) : ("neutral" as const),
      icon: TrendingDown,
      variant: savedMinor > 0 ? ("success" as const) : ("default" as const),
    },
    {
      title: "Custo Otimizado",
      value: formatCurrency(totalCostMinor),
      change: baselineCostMinor > 0 ? `Baseline: ${formatCurrency(baselineCostMinor)}` : "Baseline indisponível",
      changeType: "neutral" as const,
      icon: MessageSquare,
      variant: "default" as const,
    },
    {
      title: "Mensagens Processadas",
      value: totalMessages.toLocaleString(),
      change: "Volume total no período",
      changeType: "neutral" as const,
      icon: Target,
      variant: "default" as const,
    },
    {
      title: "Taxa de Sucesso",
      value: `${successRate.toFixed(1)}%`,
      change: successRate < 95 ? "Abaixo do ideal (>95%)" : "Saudável",
      changeType: successRate >= 95 ? ("positive" as const) : ("warning" as const),
      icon: ShieldCheck,
      variant: successRate >= 95 ? ("success" as const) : ("warning" as const),
    },
  ];

  const topCountries = dashboard?.top_countries ?? [];
  const topTemplates = dashboard?.top_templates ?? [];

  const progressWidth = baselineCostMinor > 0 ? Math.min(100, (totalCostMinor / baselineCostMinor) * 100) : 0;

  return (
    <SimpleLayout>
      <div className="space-y-6">
      {/* Métricas principais */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
        {metrics.map((metric, index) => (
          <MetricCard key={index} {...metric} />
        ))}
      </div>

      {/* Gráfico de economia */}
      <Card className="bg-gradient-to-r from-card to-card/50 border-primary/20">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <BarChart3 className="h-5 w-5 text-primary" />
            <span>Baseline vs Otimizado (Últimos 30 dias)</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <p className="text-sm text-muted-foreground">Custo Baseline (100% WhatsApp)</p>
                <p className="text-2xl font-bold text-foreground">{formatCurrency(baselineCostMinor)}</p>
              </div>
              <div className="space-y-1 text-right">
                <p className="text-sm text-muted-foreground">Custo Otimizado (com regras)</p>
                <p className="text-2xl font-bold text-success">{formatCurrency(totalCostMinor)}</p>
              </div>
            </div>

            <div className="relative">
              <div className="h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-success to-success/80 rounded-full transition-all duration-1000 ease-out"
                  style={{ width: `${progressWidth}%` }}
                />
              </div>
              <div className="flex items-center justify-between mt-2 text-sm">
                <span className="text-muted-foreground">€0</span>
                <Badge className="bg-success/10 text-success border-success/20">
                  {pctSaved.toFixed(1)}% de economia ({formatCurrency(savedMinor)})
                </Badge>
                <span className="text-muted-foreground">{formatCurrency(baselineCostMinor)}</span>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase text-primary/80">Economia registrada</p>
                    <p className="text-lg font-semibold text-primary">{formatCurrency(savedMinor)}</p>
                  </div>
                  <TrendingDown className="h-6 w-6 text-primary" />
                </CardContent>
              </Card>
              <Card className="border-muted/50">
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase text-muted-foreground">Latência média</p>
                    <p className="text-lg font-semibold">{avgLatency.toFixed(0)} ms</p>
                  </div>
                  <TimerReset className="h-6 w-6 text-muted-foreground" />
                </CardContent>
              </Card>
            </div>
          </div>
        </CardContent>
      </Card>

      <section className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <Signal className="h-5 w-5 text-primary" />
            <span>Saúde por Canal</span>
          </div>
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Monitorando {channelMetrics.length} {channelMetrics.length === 1 ? "canal" : "canais"}
          </span>
        </div>
        {channelSectionLoading ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[...Array(3)].map((_, index) => (
              <Card key={index}>
                <CardContent className="space-y-4 p-6">
                  <Skeleton className="h-5 w-2/3" />
                  <Skeleton className="h-24 w-full" />
                  <Skeleton className="h-8 w-full" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : channelSectionError ? (
          <Card className="border-destructive/40 bg-destructive/5">
            <CardContent className="p-6 text-sm text-destructive">
              {channelErrorMessage}
            </CardContent>
          </Card>
        ) : channelMetrics.length > 0 ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {channelMetrics.map((metric) => (
              <ChannelMetricCard
                key={metric.channel}
                metric={metric}
                queueMetric={queueByChannel[metric.channel]}
              />
            ))}
          </div>
        ) : (
          <Card>
            <CardContent className="p-6 text-sm text-muted-foreground">
              Nenhum canal com métricas registradas no período selecionado.
            </CardContent>
          </Card>
        )}
      </section>

      {channelSpecificAlerts.length > 0 && (
        <Card className="border-warning/30 bg-warning/5">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-warning">
              <BellRing className="h-5 w-5" />
              Alertas por canal
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {channelSpecificAlerts.map((alert, index) => (
                <div
                  key={`${alert.channel}-${index}`}
                  className="flex items-start gap-3 rounded-lg border border-warning/30 bg-background/80 p-3"
                >
                  <Badge
                    variant="outline"
                    className={
                      alert.severity === "critical"
                        ? "border-destructive/40 bg-destructive/10 text-destructive"
                        : "border-warning/40 bg-warning/10 text-warning"
                    }
                  >
                    {alert.severity === "critical" ? "Crítico" : "Atenção"}
                  </Badge>
                  <div>
                    <p className="text-sm font-semibold">{formatChannelName(alert.channel)}</p>
                    <p className="text-sm text-muted-foreground">{alert.message}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabelas */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Top países */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Globe className="h-5 w-5 text-primary" />
                <span>Top Países por Custo</span>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate("/reports")}>
                Ver todos
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topCountries.length > 0 ? topCountries.map((country, index) => (
                <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                  <div className="flex items-center space-x-3">
                    <span className="text-xl">{getFlagEmoji(country.country)}</span>
                    <div>
                      <p className="font-medium">{country.country}</p>
                      <p className="text-sm text-muted-foreground">Custo: {formatCurrency(country.cost_minor)}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{country.count.toLocaleString()} msgs</p>
                  </div>
                </div>
              )) : (
                <p className="text-sm text-muted-foreground text-center py-4">Nenhum dado disponível</p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Top templates */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <MessageSquare className="h-5 w-5 text-primary" />
                <span>Templates Mais Caros</span>
              </div>
              <Button variant="ghost" size="sm" onClick={() => navigate("/reports")}>
                Ver todos
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {topTemplates.length > 0 ? topTemplates.map((template, index) => (
                <div key={index} className="flex items-center justify-between p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <p className="font-medium text-sm">{template.template}</p>
                      <Badge
                        variant={template.category?.toLowerCase() === "marketing" ? "secondary" : "outline"}
                        className="text-xs"
                      >
                        {template.category ?? "N/A"}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{template.count.toLocaleString()} mensagens</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{formatCurrency(template.cost_minor)}</p>
                  </div>
                </div>
              )) : (
                <p className="text-sm text-muted-foreground text-center py-4">Nenhum dado disponível</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Call to action */}
      <Card className="bg-gradient-to-r from-primary/5 to-success/5 border-primary/20">
        <CardContent className="p-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold">Otimize ainda mais suas regras</h3>
              <p className="text-muted-foreground">
                Configurar novas regras de roteamento pode economizar até €500 adicionais por mês
              </p>
            </div>
            <Button 
              className="bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70"
              onClick={() => navigate("/rules")}
            >
              Criar Regra
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </CardContent>
        </Card>

        {/* Métricas de Provedores */}
        {providersLoading ? (
          <Card>
            <CardContent className="p-6 space-y-3">
              {[...Array(2)].map((_, index) => (
                <Skeleton key={index} className="h-20 w-full" />
              ))}
            </CardContent>
          </Card>
        ) : providersError ? (
          <Card className="border-destructive/40 bg-destructive/5">
            <CardContent className="p-6 text-sm text-destructive">
              Não foi possível carregar métricas de provedores no momento.
            </CardContent>
          </Card>
        ) : providers.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Activity className="mr-2 h-5 w-5 text-primary" />
                Desempenho dos Provedores (Últimos 7 dias)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {providers.map((provider) => (
                  <div key={provider.provider_id} className="p-4 bg-muted/30 rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold">{provider.provider_name}</h3>
                      <Badge variant={provider.success_rate >= 95 ? "default" : "destructive"}>
                        {provider.success_rate >= 95 ? "Saudável" : "Atenção"}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <p className="text-muted-foreground">Mensagens</p>
                        <p className="text-lg font-bold">{provider.total_sent}</p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Taxa Sucesso</p>
                        <p className="text-lg font-bold text-success">
                          {provider.success_rate.toFixed(0)}%
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">Latência Avg</p>
                        <p className="text-lg font-bold">{provider.avg_latency_ms}ms</p>
                      </div>
                    </div>

                    {provider.total_cost_minor && (
                      <div className="mt-3 pt-3 border-t">
                        <p className="text-sm text-muted-foreground">Custo Total</p>
                        <p className="text-lg font-bold">€{(provider.total_cost_minor / 100).toFixed(2)}</p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Alertas e Recomendações */}
        {dashboard?.alerts && dashboard.alerts.length > 0 && (
          <Card className="bg-gradient-to-r from-warning/5 to-background border-warning/20">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Zap className="mr-2 h-5 w-5 text-warning" />
                Alertas e Recomendações
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {dashboard.alerts.map((alert, index) => (
                  <div key={index} className="flex items-start gap-3 p-3 bg-warning/5 rounded-lg">
                    <AlertTriangle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium capitalize">{alert.type}</p>
                      <p className="text-sm text-muted-foreground">{alert.message}</p>
                      {alert.action && (
                        <p className="text-xs text-foreground mt-1">Sugestão: {alert.action}</p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {dashboard?.recommendations?.length ? (
          <Card className="border-primary/30 bg-primary/5">
            <CardHeader>
              <CardTitle className="flex items-center text-primary">
                <ArrowRight className="mr-2 h-5 w-5" />
                Recomendações do motor de rotas
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-primary/90">
                {dashboard.recommendations.map((recommendation, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="mt-1 h-2 w-2 rounded-full bg-primary" />
                    <span>{recommendation}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </SimpleLayout>
  );
};

export default Dashboard;