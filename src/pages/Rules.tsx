import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import SimpleLayout from "@/components/SimpleLayout";
import AdvancedSimulator from "@/components/AdvancedSimulator";
import { useRules, useToggleRule, useSimulateRules } from "@/hooks/useApi";
import { 
  Plus, 
  Edit, 
  Trash2, 
  PlayCircle, 
  Target, 
  TrendingDown,
  MessageSquare,
  Zap
} from "lucide-react";

const Rules = () => {
  const { data: rulesData, isLoading } = useRules();
  const toggleRule = useToggleRule();
  const simulate = useSimulateRules();

  const rules = (rulesData as any)?.rules || [];

  const handleToggle = async (ruleId: string) => {
    await toggleRule.mutateAsync(ruleId);
  };

  const handleSimulate = async () => {
    await simulate.mutateAsync();
  };

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

  const getFallbackColor = (fallback: string) => {
    switch (fallback.toLowerCase()) {
      case "email":
        return "bg-primary/10 text-primary border-primary/20";
      case "sms":
        return "bg-warning/10 text-warning border-warning/20";
      case "telegram":
        return "bg-success/10 text-success border-success/20";
      default:
        return "bg-muted/10 text-muted-foreground border-border";
    }
  };

  if (isLoading) {
    return (
      <SimpleLayout>
        <div className="space-y-6">
          <Skeleton className="h-32 w-full" />
          <div className="grid gap-6">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))}
          </div>
        </div>
      </SimpleLayout>
    );
  }

  const activeRules = rules.filter((r: any) => r.enabled).length;
  const totalSavings = 0; // Will be calculated from simulation

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
                <p className="text-2xl font-bold text-success">€{totalSavings.toFixed(2)}</p>
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
                <p className="text-2xl font-bold">0</p>
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
            >
              <Plus className="mr-2 h-5 w-5" />
              Nova Regra
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Lista de regras */}
      <div className="space-y-4">
        {rules.length === 0 ? (
          <Card>
            <CardContent className="p-12 text-center">
              <Target className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Nenhuma regra criada</h3>
              <p className="text-muted-foreground mb-4">
                Crie sua primeira regra de roteamento para começar a economizar
              </p>
              <Button className="bg-gradient-to-r from-primary to-primary/80">
                <Plus className="mr-2 h-4 w-4" />
                Criar Primeira Regra
              </Button>
            </CardContent>
          </Card>
        ) : (
          rules.map((rule: any) => (
            <Card key={rule.rule_id} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center space-x-3">
                      <CardTitle className="text-xl">{rule.name}</CardTitle>
                      <Badge variant="outline" className="text-xs">
                        Prioridade {rule.priority}
                      </Badge>
                      <Switch
                        checked={rule.enabled}
                        onCheckedChange={() => handleToggle(rule.rule_id)}
                      />
                    </div>
                    {rule.description && (
                      <p className="text-sm text-muted-foreground">{rule.description}</p>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button variant="ghost" size="sm">
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm">
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
              </CardHeader>

              <CardContent className="space-y-4">
                {/* Condições */}
                <div>
                  <h4 className="text-sm font-semibold mb-2 flex items-center">
                    <Target className="h-4 w-4 mr-2 text-primary" />
                    Condições
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {rule.conditions?.countries && (
                      <Badge variant="outline">
                        Países: {rule.conditions.countries.join(", ")}
                      </Badge>
                    )}
                    {rule.conditions?.template_categories && (
                      rule.conditions.template_categories.map((cat: string) => (
                        <Badge key={cat} className={getCategoryColor(cat)}>
                          {cat}
                        </Badge>
                      ))
                    )}
                    {rule.conditions?.templates && (
                      <Badge variant="outline">
                        Templates: {rule.conditions.templates.join(", ")}
                      </Badge>
                    )}
                    {rule.conditions?.cost_threshold_minor && (
                      <Badge variant="outline">
                        Custo &gt; €{(rule.conditions.cost_threshold_minor / 100).toFixed(3)}
                      </Badge>
                    )}
                  </div>
                </div>

                <Separator />

                {/* Ações */}
                <div>
                  <h4 className="text-sm font-semibold mb-2 flex items-center">
                    <Zap className="h-4 w-4 mr-2 text-warning" />
                    Ações
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {rule.actions?.fallback_channel && (
                      <Badge className={getFallbackColor(rule.actions.fallback_channel)}>
                        Fallback: {rule.actions.fallback_channel}
                      </Badge>
                    )}
                    {rule.actions?.template_mapping && (
                      <Badge variant="outline">
                        Template Mapping: {Object.keys(rule.actions.template_mapping).length} mapeamentos
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Estatísticas */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-foreground">0</p>
                    <p className="text-xs text-muted-foreground">Aplicações</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-success">€0.00</p>
                    <p className="text-xs text-muted-foreground">Economizado</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-foreground">-</p>
                    <p className="text-xs text-muted-foreground">Última aplicação</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
      </div>

      {/* Simulador Avançado */}
      <AdvancedSimulator />

      {/* Simulação Rápida */}
      {rules.length > 0 && (
        <Card className="bg-gradient-to-r from-primary/5 to-success/5 border-primary/20">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold flex items-center">
                  <PlayCircle className="h-5 w-5 mr-2 text-primary" />
                  Simulação Rápida
                </h3>
                <p className="text-muted-foreground text-sm">
                  Teste rapidamente o impacto das regras atuais
                </p>
              </div>
              <Button
                onClick={handleSimulate}
                disabled={simulate.isPending}
                variant="outline"
              >
                <PlayCircle className="mr-2 h-4 w-4" />
                {simulate.isPending ? "Simulando..." : "Executar"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Sugestões */}
      <Card className="bg-gradient-to-br from-warning/5 to-background border-warning/20">
        <CardContent className="p-6">
          <div className="flex items-start space-x-4">
            <div className="p-3 bg-warning/10 rounded-lg">
              <TrendingDown className="h-6 w-6 text-warning" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold mb-2">Sugestão de Otimização</h3>
              <p className="text-muted-foreground mb-4">
                Identificamos potencial de economia adicional de até €500/mês com novas regras baseadas no seu histórico
              </p>
              <Button variant="outline">
                Ver Sugestões Detalhadas
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
      </div>
    </SimpleLayout>
  );
};

export default Rules;

