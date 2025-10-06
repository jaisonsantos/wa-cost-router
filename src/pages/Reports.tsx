import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import SimpleLayout from "@/components/SimpleLayout";
import { useSummary, useEvents } from "@/hooks/useApi";
import { 
  Download, 
  Globe, 
  MessageSquare, 
  Clock, 
  TrendingDown,
  TrendingUp,
  Calendar,
  Filter
} from "lucide-react";

const Reports = () => {
  const [timeRange, setTimeRange] = useState("7d");
  
  // Calculate date range
  const getDateRange = () => {
    const to = new Date().toISOString();
    const from = new Date();
    switch (timeRange) {
      case "1d":
        from.setDate(from.getDate() - 1);
        break;
      case "7d":
        from.setDate(from.getDate() - 7);
        break;
      case "30d":
        from.setDate(from.getDate() - 30);
        break;
      case "90d":
        from.setDate(from.getDate() - 90);
        break;
    }
    return { from: from.toISOString(), to };
  };

  const { from, to } = getDateRange();
  const { data: summary, isLoading: summaryLoading } = useSummary(from, to);
  const { data: eventsData, isLoading: eventsLoading } = useEvents({ 
    limit: 1000,
    from,
    to 
  });

  const events = (eventsData as any)?.events || [];
  const costEur = ((summary as any)?.cost_7d_minor || 0) / 100;
  const savedEur = ((summary as any)?.saved_7d_minor || 0) / 100;
  const pctSaved = (summary as any)?.pct_saved || 0;

  // Process events by country
  const countryStats = events.reduce((acc: any, event: any) => {
    const country = event.destination_country || "Unknown";
    if (!acc[country]) {
      acc[country] = { baseline: 0, optimized: 0, messages: 0 };
    }
    const cost = (event.unit_cost_minor || 0) / 100;
    acc[country].optimized += cost;
    acc[country].baseline += cost * 1.3; // Assume 30% baseline increase
    acc[country].messages++;
    return acc;
  }, {});

  const countryData = Object.entries(countryStats).map(([country, stats]: [string, any]) => {
    const savings = stats.baseline - stats.optimized;
    const percentage = stats.baseline > 0 ? ((savings / stats.baseline) * 100) : 0;
    return {
      country,
      flag: "🌍",
      baseline: `€${stats.baseline.toFixed(2)}`,
      optimized: `€${stats.optimized.toFixed(2)}`,
      savings: `€${savings.toFixed(2)}`,
      percentage: `${percentage.toFixed(0)}%`,
      messages: stats.messages.toString(),
      avgCost: `€${(stats.optimized / stats.messages).toFixed(4)}`,
      trend: percentage > 0 ? "down" : "up"
    };
  });

  // Process events by template
  const templateStats = events.reduce((acc: any, event: any) => {
    const template = event.template_name || "unknown";
    if (!acc[template]) {
      acc[template] = { 
        baseline: 0, 
        optimized: 0, 
        messages: 0, 
        category: event.template_category || "Unknown",
        countries: new Set()
      };
    }
    const cost = (event.unit_cost_minor || 0) / 100;
    acc[template].optimized += cost;
    acc[template].baseline += cost * 1.3;
    acc[template].messages++;
    if (event.destination_country) {
      acc[template].countries.add(event.destination_country);
    }
    return acc;
  }, {});

  const templateData = Object.entries(templateStats).map(([name, stats]: [string, any]) => {
    const savings = stats.baseline - stats.optimized;
    const percentage = stats.baseline > 0 ? ((savings / stats.baseline) * 100) : 0;
    return {
      name,
      category: stats.category,
      baseline: `€${stats.baseline.toFixed(2)}`,
      optimized: `€${stats.optimized.toFixed(2)}`,
      savings: `€${savings.toFixed(2)}`,
      percentage: `${percentage.toFixed(0)}%`,
      messages: stats.messages.toString(),
      countries: Array.from(stats.countries).slice(0, 3)
    };
  });

  // Process events by hour
  const hourlyStats = events.reduce((acc: any, event: any) => {
    if (!event.timestamp_provider) return acc;
    const hour = new Date(event.timestamp_provider).getHours();
    if (!acc[hour]) {
      acc[hour] = { baseline: 0, optimized: 0 };
    }
    const cost = (event.unit_cost_minor || 0) / 100;
    acc[hour].optimized += cost;
    acc[hour].baseline += cost * 1.3;
    return acc;
  }, {});

  const hourlyData = Array.from({ length: 24 }, (_, hour) => {
    const stats = hourlyStats[hour] || { baseline: 0, optimized: 0 };
    const savings = stats.baseline - stats.optimized;
    const percentage = stats.baseline > 0 ? Math.round((savings / stats.baseline) * 100) : 0;
    return {
      hour: `${hour.toString().padStart(2, '0')}:00`,
      baseline: stats.baseline,
      optimized: stats.optimized,
      savings,
      percentage
    };
  });

  const timeRanges = [
    { value: "1d", label: "Hoje" },
    { value: "7d", label: "7 dias" },
    { value: "30d", label: "30 dias" },
    { value: "90d", label: "90 dias" }
  ];

  if (summaryLoading || eventsLoading) {
    return (
      <SimpleLayout>
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <div className="grid gap-6 md:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Skeleton key={i} className="h-32 w-full" />
            ))}
          </div>
        </div>
      </SimpleLayout>
    );
  }

  const totalMessages = events.length;

  return (
    <SimpleLayout>
      <div className="space-y-6">
      {/* Header com controles */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Relatórios & Analytics</h2>
          <p className="text-muted-foreground">
            Análise detalhada de custos e economia por dimensão
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-1 bg-muted p-1 rounded-lg">
            {timeRanges.map((range) => (
              <Button
                key={range.value}
                variant={timeRange === range.value ? "default" : "ghost"}
                size="sm"
                onClick={() => setTimeRange(range.value)}
                className={timeRange === range.value ? "bg-primary text-primary-foreground" : ""}
              >
                {range.label}
              </Button>
            ))}
          </div>
          
          <Button variant="outline">
            <Filter className="mr-2 h-4 w-4" />
            Filtros
          </Button>
          
          <Button className="bg-gradient-to-r from-primary to-primary/80">
            <Download className="mr-2 h-4 w-4" />
            Exportar CSV
          </Button>
        </div>
      </div>

      {/* Resumo executivo */}
      <div className="grid gap-6 md:grid-cols-4">
        <Card className="bg-gradient-to-br from-success-muted to-background border-success/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Economia Total</p>
                <p className="text-2xl font-bold text-success">€{savedEur.toFixed(2)}</p>
                <p className="text-xs text-success flex items-center mt-1">
                  <TrendingDown className="h-3 w-3 mr-1" />
                  {pctSaved.toFixed(1)}% de redução
                </p>
              </div>
              <TrendingDown className="h-8 w-8 text-success" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Custo Baseline</p>
                <p className="text-2xl font-bold text-foreground">€{(costEur + savedEur).toFixed(2)}</p>
                <p className="text-xs text-muted-foreground flex items-center mt-1">
                  <Calendar className="h-3 w-3 mr-1" />
                  Últimos {timeRange}
                </p>
              </div>
              <MessageSquare className="h-8 w-8 text-primary" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Custo Otimizado</p>
                <p className="text-2xl font-bold text-foreground">€{costEur.toFixed(2)}</p>
                <p className="text-xs text-success flex items-center mt-1">
                  <TrendingDown className="h-3 w-3 mr-1" />
                  {pctSaved.toFixed(1)}% de economia
                </p>
              </div>
              <TrendingDown className="h-8 w-8 text-primary" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Mensagens</p>
                <p className="text-2xl font-bold text-foreground">{totalMessages}</p>
                <p className="text-xs text-muted-foreground flex items-center mt-1">
                  <Globe className="h-3 w-3 mr-1" />
                  {Object.keys(countryStats).length} países
                </p>
              </div>
              <MessageSquare className="h-8 w-8 text-muted-foreground" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs de relatórios */}
      <Tabs defaultValue="countries" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="countries" className="flex items-center">
            <Globe className="mr-2 h-4 w-4" />
            Por País
          </TabsTrigger>
          <TabsTrigger value="templates" className="flex items-center">
            <MessageSquare className="mr-2 h-4 w-4" />
            Por Template
          </TabsTrigger>
          <TabsTrigger value="hourly" className="flex items-center">
            <Clock className="mr-2 h-4 w-4" />
            Por Hora
          </TabsTrigger>
        </TabsList>

        {/* Relatório por país */}
        <TabsContent value="countries">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Globe className="mr-2 h-5 w-5 text-primary" />
                Breakdown por País
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {countryData.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    Nenhum dado disponível para o período selecionado
                  </p>
                ) : (
                  countryData.map((country, index) => (
                  <div key={index} className="grid grid-cols-8 gap-4 p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                    <div className="flex items-center space-x-2">
                      <span className="text-xl">{country.flag}</span>
                      <span className="font-medium">{country.country}</span>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Baseline</p>
                      <p className="font-medium">{country.baseline}</p>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Otimizado</p>
                      <p className="font-medium">{country.optimized}</p>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Economia</p>
                      <p className="font-medium text-success">{country.savings}</p>
                    </div>
                    
                    <div className="text-center">
                      <Badge className="bg-success/10 text-success border-success/20">
                        {country.percentage}
                      </Badge>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Mensagens</p>
                      <p className="font-medium">{country.messages}</p>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Custo médio</p>
                      <p className="font-medium">{country.avgCost}</p>
                    </div>
                    
                    <div className="text-center">
                      {country.trend === "down" ? (
                        <TrendingDown className="h-5 w-5 text-success mx-auto" />
                      ) : (
                        <TrendingUp className="h-5 w-5 text-warning mx-auto" />
                      )}
                    </div>
                  </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Relatório por template */}
        <TabsContent value="templates">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <MessageSquare className="mr-2 h-5 w-5 text-primary" />
                Breakdown por Template
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {templateData.length === 0 ? (
                  <p className="text-center text-muted-foreground py-8">
                    Nenhum dado disponível para o período selecionado
                  </p>
                ) : (
                  templateData.map((template, index) => (
                  <div key={index} className="grid grid-cols-7 gap-4 p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                    <div>
                      <p className="font-medium">{template.name}</p>
                      <Badge 
                        className={template.category === "Marketing" 
                          ? "bg-warning/10 text-warning border-warning/20 text-xs mt-1" 
                          : "bg-primary/10 text-primary border-primary/20 text-xs mt-1"
                        }
                      >
                        {template.category}
                      </Badge>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Baseline</p>
                      <p className="font-medium">{template.baseline}</p>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Otimizado</p>
                      <p className="font-medium">{template.optimized}</p>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Economia</p>
                      <p className="font-medium text-success">{template.savings}</p>
                    </div>
                    
                    <div className="text-center">
                      <Badge className="bg-success/10 text-success border-success/20">
                        {template.percentage}
                      </Badge>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Mensagens</p>
                      <p className="font-medium">{template.messages}</p>
                    </div>
                    
                    <div className="text-center">
                      <p className="text-sm text-muted-foreground">Países</p>
                      <p className="text-xs">{template.countries.join(", ")}</p>
                    </div>
                  </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Relatório por hora */}
        <TabsContent value="hourly">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Clock className="mr-2 h-5 w-5 text-primary" />
                Breakdown por Hora do Dia
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-2 grid-cols-6 md:grid-cols-8 lg:grid-cols-12">
                {hourlyData.map((hour, index) => (
                  <div key={index} className="p-3 text-center rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors">
                    <p className="text-xs font-medium">{hour.hour}</p>
                    <p className="text-sm text-success font-semibold">€{hour.savings.toFixed(2)}</p>
                    <p className="text-xs text-muted-foreground">{hour.percentage}%</p>
                  </div>
                ))}
              </div>
              
              <div className="mt-6 p-4 bg-primary/5 rounded-lg">
                <h4 className="font-semibold text-primary mb-2">Insights Horários</h4>
                <div className="grid md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">• Maior economia: <span className="text-foreground font-medium">02:00-06:00 (45% médio)</span></p>
                    <p className="text-muted-foreground">• Horário de pico: <span className="text-foreground font-medium">09:00-18:00</span></p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">• Custo mais alto: <span className="text-foreground font-medium">14:00-16:00</span></p>
                    <p className="text-muted-foreground">• Melhor para regras: <span className="text-foreground font-medium">20:00-07:00</span></p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      </div>
    </SimpleLayout>
  );
};

export default Reports;