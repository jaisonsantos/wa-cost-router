import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import MetricCard from "@/components/MetricCard";
import SimpleLayout from "@/components/SimpleLayout";
import { useSummary, useEvents, useDashboardMetrics, useProviderMetrics } from "@/hooks/useApi";
import { Skeleton } from "@/components/ui/skeleton";
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
} from "lucide-react";
import { DashboardMetrics, Event, ProviderMetric, SummaryResponse } from "@/types/api";

interface CountryAggregation {
  count: number;
  costMinor: number;
}

interface CountryRow {
  country: string;
  flag: string;
  costMinor: number;
  messages: number;
}

interface TemplateAggregation {
  count: number;
  costMinor: number;
  category: string;
}

interface TemplateRow {
  name: string;
  category: string;
  costMinor: number;
  count: number;
}

const Dashboard = () => {
  const navigate = useNavigate();
  const { data: summary, isLoading: summaryLoading } = useSummary();
  const { data: events } = useEvents({ limit: 10 });
  const { data: dashboardMetrics } = useDashboardMetrics();
  const { data: providerMetrics } = useProviderMetrics();

  const summaryData: SummaryResponse | undefined = summary;
  const eventsList: Event[] = events ?? [];
  const metricsData: DashboardMetrics | undefined = dashboardMetrics;
  const providersData: ProviderMetric[] = providerMetrics ?? [];

  if (summaryLoading) {
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

  const costEur = (summaryData?.cost_7d_minor ?? 0) / 100;
  const savedEur = (summaryData?.saved_7d_minor ?? 0) / 100;
  const pctSaved = summaryData?.pct_saved ?? 0;
  const totalMessages = eventsList.length;

  const metrics = [
    {
      title: "Economia Total (7 dias)",
      value: `€${savedEur.toFixed(2)}`,
      change: `${pctSaved.toFixed(1)}% de redução`,
      changeType: "positive" as const,
      icon: TrendingDown,
      variant: "success" as const
    },
    {
      title: "Custo WhatsApp (7 dias)",
      value: `€${costEur.toFixed(2)}`,
      change: "Total gasto no período",
      changeType: "neutral" as const,
      icon: MessageSquare,
      variant: "default" as const
    },
    {
      title: "Mensagens Processadas",
      value: totalMessages.toString(),
      change: "Últimas mensagens",
      changeType: "neutral" as const,
      icon: Target,
      variant: "default" as const
    },
    {
      title: "Taxa de Economia",
      value: `${pctSaved.toFixed(0)}%`,
      change: "vs baseline",
      changeType: pctSaved > 0 ? "positive" as const : "neutral" as const,
      icon: AlertTriangle,
      variant: "warning" as const
    }
  ];

  // Group events by country
  const eventsByCountry = eventsList.reduce<Record<string, CountryAggregation>>((acc, event) => {
    const country = event.country_iso ?? "Unknown";
    const unitCost = event.unit_cost_minor ?? 0;
    if (!acc[country]) {
      acc[country] = { count: 0, costMinor: 0 };
    }
    acc[country].count += 1;
    acc[country].costMinor += unitCost;
    return acc;
  }, {});

  const topCountries: CountryRow[] = Object.entries(eventsByCountry)
    .map(([country, data]) => ({
      country,
      flag: "🌍",
      costMinor: data.costMinor,
      messages: data.count,
    }))
    .sort((a, b) => b.costMinor - a.costMinor)
    .slice(0, 4);

  // Group events by template
  const eventsByTemplate = eventsList.reduce<Record<string, TemplateAggregation>>((acc, event) => {
    const template = event.template_name ?? "unknown";
    const unitCost = event.unit_cost_minor ?? 0;
    if (!acc[template]) {
      acc[template] = {
        count: 0,
        costMinor: 0,
        category: event.category ?? "Unknown",
      };
    }
    acc[template].count += 1;
    acc[template].costMinor += unitCost;
    return acc;
  }, {});

  const topTemplates: TemplateRow[] = Object.entries(eventsByTemplate)
    .map(([name, data]) => ({
      name,
      category: data.category,
      costMinor: data.costMinor,
      count: data.count,
    }))
    .sort((a, b) => b.costMinor - a.costMinor)
    .slice(0, 4);

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
                <p className="text-2xl font-bold text-foreground">€{((costEur + savedEur)).toFixed(2)}</p>
              </div>
              <div className="space-y-1 text-right">
                <p className="text-sm text-muted-foreground">Custo Otimizado (com regras)</p>
                <p className="text-2xl font-bold text-success">€{costEur.toFixed(2)}</p>
              </div>
            </div>
            
            <div className="relative">
              <div className="h-3 bg-muted rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-success to-success/80 rounded-full transition-all duration-1000 ease-out"
                  style={{ width: "65%" }}
                />
              </div>
              <div className="flex items-center justify-between mt-2 text-sm">
                <span className="text-muted-foreground">€0</span>
                <Badge className="bg-success/10 text-success border-success/20">
                  {pctSaved.toFixed(1)}% de economia (€{savedEur.toFixed(2)})
                </Badge>
                <span className="text-muted-foreground">€{(costEur + savedEur).toFixed(2)}</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

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
                    <span className="text-xl">{country.flag}</span>
                    <div>
                      <p className="font-medium">{country.country}</p>
                      <p className="text-sm text-muted-foreground">Custo: €{(country.costMinor / 100).toFixed(2)}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">{country.messages} msgs</p>
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
                      <p className="font-medium text-sm">{template.name}</p>
                      <Badge
                        variant={template.category.toLowerCase() === "marketing" ? "secondary" : "outline"}
                        className="text-xs"
                      >
                        {template.category}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{template.count} mensagens</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-medium">€{(template.costMinor / 100).toFixed(2)}</p>
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
        {providersData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Activity className="mr-2 h-5 w-5 text-primary" />
                Desempenho dos Provedores (Últimos 7 dias)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {providersData.map((provider) => (
                  <div key={provider.provider_id} className="p-4 bg-muted/30 rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="font-semibold">{provider.provider_name}</h3>
                      <Badge variant={provider.success_rate >= 0.95 ? "default" : "destructive"}>
                        {provider.success_rate >= 0.95 ? "Saudável" : "Atenção"}
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
                          {(provider.success_rate * 100).toFixed(0)}%
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
        {metricsData?.alerts && metricsData.alerts.length > 0 && (
          <Card className="bg-gradient-to-r from-warning/5 to-background border-warning/20">
            <CardHeader>
              <CardTitle className="flex items-center">
                <Zap className="mr-2 h-5 w-5 text-warning" />
                Alertas e Recomendações
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {metricsData.alerts.map((alert, index) => (
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
      </div>
    </SimpleLayout>
  );
};

export default Dashboard;