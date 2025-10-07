import { useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useSimulateAdvanced } from "@/hooks/useApi";
import { PlayCircle, TrendingDown, Plus, X } from "lucide-react";
import {
  AdvancedSimulationCountryBreakdown,
  AdvancedSimulationProviderBreakdown,
  AdvancedSimulationResponse,
} from "@/types/api";

interface CountryVolume {
  country: string;
  volume: number;
}

export default function AdvancedSimulator() {
  const [countries, setCountries] = useState<CountryVolume[]>([{ country: "BR", volume: 1000 }]);
  const [category, setCategory] = useState("marketing");
  const [results, setResults] = useState<AdvancedSimulationResponse | null>(null);
  
  const simulate = useSimulateAdvanced();

  const addCountry = () => {
    setCountries([...countries, { country: "", volume: 0 }]);
  };

  const removeCountry = (index: number) => {
    setCountries(countries.filter((_, i) => i !== index));
  };

  const updateCountry = (index: number, field: "country" | "volume", value: string | number) => {
    const updated = [...countries];
    updated[index] = { ...updated[index], [field]: value };
    setCountries(updated);
  };

  const handleSimulate = async () => {
    const volumesMap = countries.reduce((acc, { country, volume }) => {
      if (country && volume > 0) {
        acc[country] = volume;
      }
      return acc;
    }, {} as Record<string, number>);

    const countriesList = Object.keys(volumesMap);

    if (countriesList.length === 0) {
      return;
    }

    try {
      const result = await simulate.mutateAsync({
        countries: countriesList,
        volumes: volumesMap,
        category,
      });
      
      setResults(result);
    } catch (error) {
      console.error("Simulation error:", error);
    }
  };

  const providerNameMap = useMemo(() => {
    const map = new Map<string, string>();
    results?.breakdown.forEach((countryBreakdown) => {
      countryBreakdown.providers.forEach((provider) => {
        map.set(provider.provider_id, provider.provider_name);
      });
    });
    return map;
  }, [results]);

  const commonCountries = [
    { code: "BR", name: "Brasil" },
    { code: "US", name: "Estados Unidos" },
    { code: "MX", name: "México" },
    { code: "AR", name: "Argentina" },
    { code: "ES", name: "Espanha" },
    { code: "PT", name: "Portugal" },
    { code: "DE", name: "Alemanha" },
    { code: "FR", name: "França" },
    { code: "IT", name: "Itália" },
    { code: "GB", name: "Reino Unido" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <PlayCircle className="mr-2 h-5 w-5 text-primary" />
          Simulador Avançado
        </CardTitle>
        <CardDescription>
          Compare custos entre provedores para diferentes países e volumes
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Input de países e volumes */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Label>Países e Volumes</Label>
            <Button variant="outline" size="sm" onClick={addCountry}>
              <Plus className="h-4 w-4 mr-2" />
              Adicionar País
            </Button>
          </div>

          {countries.map((item, index) => (
            <div key={index} className="flex gap-2 items-end">
              <div className="flex-1">
                <Label>País</Label>
                <Select
                  value={item.country}
                  onValueChange={(value) => updateCountry(index, "country", value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione um país" />
                  </SelectTrigger>
                  <SelectContent>
                    {commonCountries.map((country) => (
                      <SelectItem key={country.code} value={country.code}>
                        {country.name} ({country.code})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              
              <div className="flex-1">
                <Label>Volume Mensal</Label>
                <Input
                  type="number"
                  min="0"
                  value={item.volume || ""}
                  onChange={(e) => updateCountry(index, "volume", parseInt(e.target.value) || 0)}
                  placeholder="Ex: 10000"
                />
              </div>

              {countries.length > 1 && (
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeCountry(index)}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </div>
          ))}
        </div>

        <div>
          <Label>Categoria de Template</Label>
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="marketing">Marketing</SelectItem>
              <SelectItem value="utility">Utility</SelectItem>
              <SelectItem value="authentication">Authentication</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <Button
          onClick={handleSimulate}
          disabled={simulate.isPending || countries.every(c => !c.country || !c.volume)}
          className="w-full bg-gradient-to-r from-primary to-primary/80"
        >
          <PlayCircle className="mr-2 h-4 w-4" />
          {simulate.isPending ? "Simulando..." : "Executar Simulação"}
        </Button>

        {/* Resultados */}
        {results && (
          <>
            <Separator />

            <div>
              <h3 className="font-semibold mb-4">Resultados da Simulação</h3>

              {/* Resumo */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-muted-foreground">Custo Baseline</p>
                    <p className="text-2xl font-bold">€{(results.total_baseline / 100).toFixed(2)}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-muted-foreground">Custo Otimizado</p>
                    <p className="text-2xl font-bold text-success">€{(results.total_optimized / 100).toFixed(2)}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-6">
                    <p className="text-sm text-muted-foreground">Economia</p>
                    <div className="flex items-center gap-2">
                      <TrendingDown className="h-5 w-5 text-success" />
                      <p className="text-2xl font-bold text-success">€{(results.total_saved / 100).toFixed(2)}</p>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Breakdown por país */}
              <div className="space-y-4">
                <h4 className="font-medium">Breakdown por País</h4>
                {results.breakdown.map((countryBreakdown: AdvancedSimulationCountryBreakdown) => (
                  <div key={countryBreakdown.country} className="p-4 bg-muted/30 rounded-lg space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm text-muted-foreground">{countryBreakdown.country}</p>
                        <p className="text-lg font-semibold">Volume: {countryBreakdown.volume.toLocaleString()}</p>
                      </div>
                      <div className="flex gap-6 text-sm">
                        <div>
                          <p className="text-muted-foreground">Baseline</p>
                          <p className="font-semibold">€{(countryBreakdown.baseline_cost / 100).toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Otimizado</p>
                          <p className="font-semibold text-success">€{(countryBreakdown.optimized_cost / 100).toFixed(2)}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Economia</p>
                          <p className="font-semibold text-success">€{(countryBreakdown.saved / 100).toFixed(2)}</p>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <p className="text-sm font-medium">Provedores</p>
                      <div className="grid gap-3 md:grid-cols-2">
                        {countryBreakdown.providers.map((provider: AdvancedSimulationProviderBreakdown) => (
                          <div key={provider.provider_id} className="p-3 bg-background rounded-lg border">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="font-semibold">{provider.provider_name}</span>
                                {!provider.available && (
                                  <Badge variant="outline" className="text-xs text-destructive border-destructive/40">
                                    Indisponível
                                  </Badge>
                                )}
                              </div>
                              <span className="text-sm font-medium">€{(provider.cost_minor / 100).toFixed(2)}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    {countryBreakdown.recommended_provider && (
                      <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm">
                        <span className="font-medium">Provedor recomendado:</span>{" "}
                        {providerNameMap.get(countryBreakdown.recommended_provider) ??
                          countryBreakdown.recommended_provider}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Recomendação de rota */}
              {results.recommended_route && (
                <div className="mt-4 p-4 bg-primary/5 rounded-lg border border-primary/20">
                  <h4 className="font-semibold text-primary mb-2">Rota Recomendada</h4>
                  <div className="space-y-2 text-sm text-muted-foreground">
                    {Object.entries(results.recommended_route).map(([country, providerId]) => (
                      <div key={country} className="flex items-center justify-between rounded bg-background px-3 py-2">
                        <span className="font-medium text-foreground">{country}</span>
                        <span>
                          {providerNameMap.get(providerId) ?? providerId}
                        </span>
                      </div>
                    ))}
                  </div>
                  <Button size="sm" className="bg-gradient-to-r from-primary to-primary/80">
                    Criar Regra com Esta Configuração
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
