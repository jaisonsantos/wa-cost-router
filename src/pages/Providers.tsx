import { useMemo, useState } from "react";
import { useProviders, useSetProviderCredentials, useHealthCheckProvider } from "@/hooks/useApi";
import SimpleLayout from "@/components/SimpleLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Activity, CheckCircle, XCircle, Settings } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { Provider, ProviderHealth } from "@/types/api";
import ProviderForm from "@/components/providers/ProviderForm";

type ProviderSummary = Provider;
type ProviderHealthCheck = ProviderHealth;

export default function Providers() {
  const { data: providers, isLoading } = useProviders();
  const setCredentialsMutation = useSetProviderCredentials();
  const healthCheck = useHealthCheckProvider();

  const [selectedProvider, setSelectedProvider] = useState<ProviderSummary | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const handleSubmitCredentials = async (formValues: Record<string, string>) => {
    if (!selectedProvider) return;

    try {
      await setCredentialsMutation.mutateAsync({
        providerId: selectedProvider.id,
        credentials: formValues,
      });
      setDialogOpen(false);
      toast({ title: "Credenciais configuradas com sucesso" });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Erro inesperado";
      toast({
        title: "Erro ao configurar credenciais",
        description: message,
        variant: "destructive",
      });
      throw new Error(message);
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

  const handleDialogChange = (open: boolean) => {
    setDialogOpen(open);
    if (!open) {
      setSelectedProvider(null);
    }
  };

  const complianceHighlights = useMemo(() => {
    if (!selectedProvider) return [] as string[];
    const metadata = selectedProvider.metadata ?? {};
    const compliance = metadata.compliance as Record<string, unknown> | undefined;
    if (!compliance) return [] as string[];
    const notes: string[] = [];
    Object.values(compliance).forEach((value) => {
      if (Array.isArray(value)) {
        value.forEach((item) => {
          if (typeof item === "string") {
            notes.push(item);
          }
        });
      } else if (typeof value === "string") {
        notes.push(value);
      }
    });
    return notes;
  }, [selectedProvider]);

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
            Gerencie conexões com provedores de mensagens WhatsApp, SMS e Email com validação dinâmica de credenciais.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {providersList.map((provider) => {
            const complianceMeta = provider.metadata?.compliance as Record<string, unknown> | undefined;
            const registrationNotes = Array.isArray(complianceMeta?.registrations)
              ? (complianceMeta!.registrations as unknown[]).filter(
                  (item): item is string => typeof item === "string",
                )
              : [];

            return (
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

                {registrationNotes.length > 0 && (
                  <div className="rounded-md border border-muted p-3 text-xs text-muted-foreground">
                    {registrationNotes.slice(0, 2).map((note) => (
                      <div key={note} className="flex gap-2">
                        <span className="text-primary">•</span>
                        <span>{note}</span>
                      </div>
                    ))}
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
            );
          })}
        </div>

        <Dialog open={dialogOpen} onOpenChange={handleDialogChange}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Configurar {selectedProvider?.name}</DialogTitle>
              <DialogDescription>
                Configure as credenciais e siga as recomendações de consentimento para habilitar o canal.
              </DialogDescription>
            </DialogHeader>

            {selectedProvider && selectedProvider.provider_form_schema.fields.length > 0 ? (
              <ProviderForm
                schema={selectedProvider.provider_form_schema}
                requiredFields={selectedProvider.required_fields}
                metadata={selectedProvider.metadata}
                isSubmitting={setCredentialsMutation.isPending}
                onSubmit={handleSubmitCredentials}
                onCancel={() => handleDialogChange(false)}
              />
            ) : (
              <div className="py-6 text-sm text-muted-foreground">
                Nenhum esquema de formulário foi definido para este provedor. Contate o suporte para concluir a configuração.
              </div>
            )}

            {complianceHighlights.length > 0 && (
              <div className="mt-4 rounded-md border border-muted bg-muted/30 p-3 text-xs text-muted-foreground">
                <p className="font-medium text-foreground">Notas de compliance</p>
                <ul className="mt-2 list-disc space-y-1 pl-4">
                  {complianceHighlights.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </SimpleLayout>
  );
}
