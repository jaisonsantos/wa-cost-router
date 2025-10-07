import { useState } from "react";
import { useProviders, useSetProviderCredentials, useHealthCheckProvider } from "@/hooks/useApi";
import SimpleLayout from "@/components/SimpleLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Activity, CheckCircle, XCircle, Settings } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { Provider, ProviderHealth } from "@/types/api";

type ProviderSummary = Provider;
type ProviderHealthCheck = ProviderHealth;

export default function Providers() {
  const { data: providers, isLoading } = useProviders();
  const setCredentialsMutation = useSetProviderCredentials();
  const healthCheck = useHealthCheckProvider();

  const [selectedProvider, setSelectedProvider] = useState<ProviderSummary | null>(null);
  const [credentialsForm, setCredentialsForm] = useState<Record<string, string>>({});
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleSetCredentials = async () => {
    if (!selectedProvider) return;

    try {
      await setCredentialsMutation.mutateAsync({
        providerId: selectedProvider.id,
        credentials: credentialsForm,
      });
      setDialogOpen(false);
      setCredentialsForm({});
      toast({ title: "Credenciais configuradas com sucesso" });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Erro inesperado";
      toast({
        title: "Erro ao configurar credenciais",
        description: message,
        variant: "destructive",
      });
    }
  };

  const handleHealthCheck = async (providerId: string) => {
    try {
      const result: ProviderHealthCheck = await healthCheck.mutateAsync(providerId);
      if (result.healthy) {
        toast({ title: "Provider está saudável", description: `Latência: ${result.latency_ms ?? 0}ms` });
      } else {
        toast({
          title: "Provider com problemas",
          description: result.error ?? "Erro desconhecido",
          variant: "destructive",
        });
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Erro inesperado";
      toast({
        title: "Erro ao verificar health",
        description: message,
        variant: "destructive",
      });
    }
  };

  const openCredentialsDialog = (provider: ProviderSummary) => {
    setSelectedProvider(provider);
    setDialogOpen(true);
  };

  const providersList: ProviderSummary[] = providers ?? [];

  if (isLoading) {
    return (
      <SimpleLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Carregando provedores...</div>
        </div>
      </SimpleLayout>
    );
  }

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Provedores</h1>
          <p className="text-muted-foreground mt-2">
            Gerencie conexões com provedores de mensagens WhatsApp
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {providersList.map((provider) => (
            <Card key={provider.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-xl">{provider.name}</CardTitle>
                  <Badge variant={provider.status === "active" ? "default" : "secondary"}>
                    {provider.status}
                  </Badge>
                </div>
                <CardDescription className="capitalize">{provider.type}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-2 text-sm">
                  {provider.is_configured ? (
                    <>
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      <span className="text-green-600">Configurado</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-red-600" />
                      <span className="text-red-600">Não configurado</span>
                    </>
                  )}
                </div>

                {provider.avg_latency_ms !== null && provider.avg_latency_ms !== undefined && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Activity className="h-4 w-4" />
                    <span>Latência média: {provider.avg_latency_ms}ms</span>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => openCredentialsDialog(provider)}
                  >
                    <Settings className="h-4 w-4 mr-2" />
                    Configurar
                  </Button>
                  
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleHealthCheck(provider.id)}
                    disabled={!provider.is_configured || healthCheck.isPending}
                  >
                    <Activity className="h-4 w-4 mr-2" />
                    Testar
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Configurar {selectedProvider?.name}</DialogTitle>
              <DialogDescription>
                Configure as credenciais para conectar ao provedor
              </DialogDescription>
            </DialogHeader>
            
            <div className="space-y-4 py-4">
              {selectedProvider?.name === "360dialog" && (
                <div className="space-y-2">
                  <Label htmlFor="access_token">Access Token</Label>
                  <Input
                    id="access_token"
                    type="password"
                    placeholder="Seu token de acesso 360dialog"
                    value={credentialsForm.access_token || ""}
                    onChange={(e) => setCredentialsForm({ ...credentialsForm, access_token: e.target.value })}
                  />
                </div>
              )}
              
              {selectedProvider?.name === "Gupshup" && (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="api_key">API Key</Label>
                    <Input
                      id="api_key"
                      type="password"
                      placeholder="Sua API key Gupshup"
                      value={credentialsForm.api_key || ""}
                      onChange={(e) => setCredentialsForm({ ...credentialsForm, api_key: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="app_name">App Name</Label>
                    <Input
                      id="app_name"
                      placeholder="Nome do seu app Gupshup"
                      value={credentialsForm.app_name || ""}
                      onChange={(e) => setCredentialsForm({ ...credentialsForm, app_name: e.target.value })}
                    />
                  </div>
                </>
              )}
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>
                Cancelar
              </Button>
              <Button onClick={handleSetCredentials} disabled={setCredentialsMutation.isPending}>
                {setCredentialsMutation.isPending ? "Salvando..." : "Salvar"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </SimpleLayout>
  );
}
