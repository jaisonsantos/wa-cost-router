import { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import SimpleLayout from "@/components/SimpleLayout";
import ConnectionStatusBadge from "@/components/ConnectionStatusBadge";
import ConnectionActions from "@/components/ConnectionActions";
import {
  useRates,
  useImportRatesCSV,
  useCurrentOrg,
  useCreateWAConnection,
  useConnections,
  useTestConnection,
  useBillingSummary,
  useCreateBillingCheckout,
  useCreateBillingPortal,
} from "@/hooks/useApi";
import { toast } from "@/hooks/use-toast";
import type { IntegrationConnection } from "@/types/api";
import {
  MessageSquare,
  Globe,
  Mail,
  Smartphone,
  Send,
  AlertCircle,
  Upload,
  Download,
  CreditCard,
  Users,
  Shield,
  Info,
} from "lucide-react";
import { CreateWAConnectionPayload, Organization, RateEntry } from "@/types/api";

interface WaConnectionForm {
  business_id: string;
  phone_id: string;
  access_token: string;
  webhook_verify_token: string;
  webhook_secret: string;
}

const Settings = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: ratesData, isLoading: ratesLoading } = useRates();
  const { data: orgData, isLoading: orgLoading } = useCurrentOrg();
  const importRates = useImportRatesCSV();
  const createWAConnection = useCreateWAConnection();
  const navigate = useNavigate();
  const {
    data: connectionsData,
    isLoading: connectionsLoading,
    error: connectionsError,
  } = useConnections();
  const testConnection = useTestConnection();
  const { data: billingSummary, isLoading: billingLoading } = useBillingSummary();
  const createBillingCheckout = useCreateBillingCheckout();
  const createBillingPortal = useCreateBillingPortal();

  const [waForm, setWaForm] = useState<WaConnectionForm>({
    business_id: "",
    phone_id: "",
    access_token: "",
    webhook_verify_token: "",
    webhook_secret: "",
  });

  const isWAFormValid = Object.values(waForm).every((value) => value.trim().length > 0);

  const rates: RateEntry[] = ratesData ?? [];
  const organization: Organization = orgData ?? {
    id: "-",
    name: "Carregando...",
    user_email: "-",
    role: "member",
  };

  const handleCSVUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await importRates.mutateAsync(file);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleWAConnect = async () => {
    if (!isWAFormValid) {
      return;
    }
    const payload: CreateWAConnectionPayload = {
      business_id: waForm.business_id,
      phone_id: waForm.phone_id,
      access_token: waForm.access_token,
      webhook_verify_token: waForm.webhook_verify_token,
      webhook_secret: waForm.webhook_secret,
    };
    await createWAConnection.mutateAsync(payload);
  };

  const connectionMap = new Map<string, IntegrationConnection>();
  connectionsData?.forEach((connection) => {
    connectionMap.set(connection.channel, connection);
  });

  const getConnection = (channel: string): IntegrationConnection | undefined =>
    connectionMap.get(channel);

  const getMetadataString = (
    connection: IntegrationConnection | undefined,
    key: string,
  ): string | undefined => {
    const value = connection?.metadata?.[key];
    return typeof value === "string" ? value : undefined;
  };

  const formatLastHealthCheck = (connection: IntegrationConnection | undefined): string => {
    const timestamp = connection?.last_health_check?.checked_at;
    if (!timestamp) {
      return "Nunca testado";
    }
    try {
      return formatDistanceToNow(new Date(timestamp), { addSuffix: true, locale: ptBR });
    } catch (error) {
      return new Date(timestamp).toLocaleString();
    }
  };

  const handleTestConnection = (channel: string, providerId?: string) => {
    testConnection.mutate({ channel, providerId });
  };

  const testingChannel = testConnection.variables?.channel;
  const connectionsErrorMessage = connectionsError?.message ?? null;

  const billing = billingSummary ?? null;

  const formatCurrency = (amountMinor?: number | null, currency?: string | null) => {
    if (amountMinor === null || amountMinor === undefined || !currency) {
      return "—";
    }
    try {
      return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: currency.toUpperCase(),
        minimumFractionDigits: 2,
      }).format(amountMinor / 100);
    } catch (error) {
      return `${(amountMinor / 100).toFixed(2)} ${currency.toUpperCase()}`;
    }
  };

  const formatNextBilling = (isoDate?: string | null) => {
    if (!isoDate) return "—";
    try {
      return new Date(isoDate).toLocaleDateString("pt-BR", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      });
    } catch (error) {
      return isoDate;
    }
  };

  const planStatus = billing?.plan_status ?? "inactive";
  const planName = billing?.plan_name ?? "Sem plano ativo";
  const statusLabelMap: Record<string, string> = {
    active: "Ativo",
    trialing: "Período de testes",
    past_due: "Pagamento em atraso",
    unpaid: "Não pago",
    canceled: "Cancelado",
    incomplete: "Incompleto",
    incomplete_expired: "Checkout expirado",
  };
  const planStatusLabel =
    statusLabelMap[planStatus] ??
    planStatus
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  const planBadgeClass = () => {
    switch (planStatus) {
      case "active":
      case "trialing":
        return "bg-emerald-100 text-emerald-700 border border-emerald-200";
      case "past_due":
      case "unpaid":
        return "bg-amber-100 text-amber-800 border border-amber-200";
      case "canceled":
        return "bg-slate-200 text-slate-700 border border-slate-300";
      default:
        return "bg-muted text-muted-foreground border border-muted";
    }
  };

  const messageUsage = billing?.message_usage ?? 0;
  const messageQuota = billing?.message_quota ?? 0;
  const usagePercent = messageQuota > 0 ? Math.min(100, Math.round((messageUsage / messageQuota) * 100)) : 0;

  const handleManagePlan = () => {
    const priceId = billing?.price_id;
    if (!priceId) {
      toast({
        title: "Plano não configurado",
        description: "Nenhum preço padrão disponível para esta organização.",
        variant: "destructive",
      });
      return;
    }

    const origin = window.location.origin;
    createBillingCheckout.mutate(
      {
        price_id: priceId,
        success_url: `${origin}/settings?tab=billing&checkout=success`,
        cancel_url: `${origin}/settings?tab=billing&checkout=cancel`,
      },
      {
        onSuccess: (data) => {
          window.location.href = data.checkout_url;
        },
      },
    );
  };

  const whatsappConnection = getConnection("whatsapp");
  const emailConnection = getConnection("email");
  const smsConnection = getConnection("sms");
  const telegramConnection = getConnection("telegram");

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold">Configurações</h2>
          <p className="text-muted-foreground">
            Gerencie conexões, tarifas e configurações da organização
          </p>
        </div>

      <Tabs defaultValue="connections" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="connections" className="flex items-center">
            <MessageSquare className="mr-2 h-4 w-4" />
            Conexões
          </TabsTrigger>
          <TabsTrigger value="rates" className="flex items-center">
            <Globe className="mr-2 h-4 w-4" />
            Tarifas
          </TabsTrigger>
          <TabsTrigger value="organization" className="flex items-center">
            <Users className="mr-2 h-4 w-4" />
            Organização
          </TabsTrigger>
          <TabsTrigger value="billing" className="flex items-center">
            <CreditCard className="mr-2 h-4 w-4" />
            Cobrança
          </TabsTrigger>
        </TabsList>

        {/* Conexões */}
        <TabsContent value="connections" className="space-y-6">
          {connectionsErrorMessage && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4" />
              <span>{connectionsErrorMessage}</span>
            </div>
          )}
          {/* WhatsApp Business */}
          <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <MessageSquare className="mr-2 h-5 w-5 text-primary" />
                WhatsApp Business Cloud API
              </div>
              <ConnectionStatusBadge
                status={whatsappConnection?.status ?? "disconnected"}
                isLoading={connectionsLoading}
              />
            </CardTitle>
          </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="wa-business-id">Business Account ID</Label>
                  <Input
                    id="wa-business-id"
                    value={waForm.business_id}
                    required
                    aria-invalid={!waForm.business_id.trim()}
                    onChange={(e) =>
                      setWaForm({ ...waForm, business_id: e.target.value })
                    }
                    placeholder="Inserir Business ID"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Disponível no painel Meta Business &gt; Configurações da conta comercial.
                  </p>
                </div>
                <div>
                  <Label htmlFor="wa-phone-id">Phone Number ID</Label>
                  <Input
                    id="wa-phone-id"
                    value={waForm.phone_id}
                    required
                    aria-invalid={!waForm.phone_id.trim()}
                    onChange={(e) => setWaForm({ ...waForm, phone_id: e.target.value })}
                    placeholder="Inserir Phone ID"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Copie o ID na seção de números do WhatsApp Manager.
                  </p>
                </div>
                <div>
                  <Label htmlFor="wa-access-token">Access Token</Label>
                  <Input
                    type="password"
                    id="wa-access-token"
                    value={waForm.access_token}
                    required
                    aria-invalid={!waForm.access_token.trim()}
                    onChange={(e) =>
                      setWaForm({ ...waForm, access_token: e.target.value })
                    }
                    placeholder="Inserir token"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Gere um token de longo prazo no Meta for Developers.
                  </p>
                </div>
                <div>
                  <Label htmlFor="wa-webhook-verify-token">Webhook Verify Token</Label>
                  <Input
                    id="wa-webhook-verify-token"
                    value={waForm.webhook_verify_token}
                    required
                    aria-invalid={!waForm.webhook_verify_token.trim()}
                    onChange={(e) =>
                      setWaForm({ ...waForm, webhook_verify_token: e.target.value })
                    }
                    placeholder="Token de verificação"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Use o mesmo token configurado ao registrar o webhook no Meta Developers.
                  </p>
                </div>
                <div>
                  <Label htmlFor="wa-webhook-secret">Webhook Secret</Label>
                  <Input
                    id="wa-webhook-secret"
                    type="password"
                    value={waForm.webhook_secret}
                    required
                    aria-invalid={!waForm.webhook_secret.trim()}
                    onChange={(e) =>
                      setWaForm({ ...waForm, webhook_secret: e.target.value })
                    }
                    placeholder="Secret do webhook"
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Disponível na aba de Webhooks do aplicativo WhatsApp no Meta Developers.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-3 text-sm">
                <Shield className="mt-0.5 h-4 w-4 text-primary" />
                <div>
                  <p className="font-medium flex items-center gap-2">
                    Proteja suas credenciais
                    <Badge variant="outline" className="gap-1">
                      <Info className="h-3 w-3" />
                      Guia
                    </Badge>
                  </p>
                  <p className="text-muted-foreground">
                    Gere o verify token e o secret diretamente no Meta Developers e nunca compartilhe esses valores fora da sua equipe de confiança.
                  </p>
                </div>
              </div>

              <div className="flex flex-col gap-3 rounded-lg border border-border bg-muted/40 p-3 text-sm md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-sm font-medium">
                    {whatsappConnection?.connected ? "Conexão ativa" : "Conexão não configurada"}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Último teste: {connectionsLoading ? "Carregando..." : formatLastHealthCheck(whatsappConnection)}
                  </p>
                  {whatsappConnection?.last_health_check?.error && (
                    <p className="mt-1 text-xs text-destructive">
                      Erro: {whatsappConnection.last_health_check.error}
                    </p>
                  )}
                </div>
                <ConnectionActions
                  onTest={() => handleTestConnection("whatsapp")}
                  isTesting={testConnection.isPending && testingChannel === "whatsapp"}
                  disableTest={connectionsLoading || testConnection.isPending}
                />
              </div>

              <div className="flex space-x-2">
                <Button
                  onClick={handleWAConnect}
                  disabled={createWAConnection.isPending || !isWAFormValid}
                  className="bg-gradient-to-r from-primary to-primary/80"
                >
                  {createWAConnection.isPending ? "Conectando..." : "Conectar WhatsApp"}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Email */}
          <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <Mail className="mr-2 h-5 w-5 text-primary" />
                Email (SMTP)
              </div>
              <ConnectionStatusBadge
                status={emailConnection?.status ?? "disconnected"}
                isLoading={connectionsLoading}
              />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label>Provedor</Label>
                {connectionsLoading ? (
                  <Skeleton className="h-9 w-full" />
                ) : (
                  <Input value={getMetadataString(emailConnection, "provider_name") ?? "Não configurado"} readOnly />
                )}
              </div>
              <div>
                <Label>Endpoint / Base URL</Label>
                {connectionsLoading ? (
                  <Skeleton className="h-9 w-full" />
                ) : (
                  <Input value={getMetadataString(emailConnection, "base_url") ?? "-"} readOnly />
                )}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Último teste: {connectionsLoading ? "Carregando..." : formatLastHealthCheck(emailConnection)}
              </p>
              {emailConnection?.last_health_check?.error && (
                <p className="text-xs text-destructive">
                  Erro: {emailConnection.last_health_check.error}
                </p>
              )}
              {!emailConnection?.has_credentials && !connectionsLoading && (
                <p className="text-xs text-muted-foreground">
                  Credenciais não configuradas. Atualize os dados em Provedores &gt; SendGrid.
                </p>
              )}
              <ConnectionActions
                onTest={emailConnection ? () => handleTestConnection("email", getMetadataString(emailConnection, "provider_id")) : undefined}
                onConfigure={() => navigate("/providers")}
                isTesting={testConnection.isPending && testingChannel === "email"}
                disableTest={
                  connectionsLoading || !emailConnection?.has_credentials || testConnection.isPending
                }
                disableConfigure={connectionsLoading}
                testLabel="Testar Email"
                configureLabel="Reconfigurar"
              />
            </div>
          </CardContent>
        </Card>

          {/* SMS */}
          <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <Smartphone className="mr-2 h-5 w-5 text-primary" />
                SMS (Twilio)
              </div>
              <ConnectionStatusBadge
                status={smsConnection?.status ?? "disconnected"}
                isLoading={connectionsLoading}
              />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Configure sua conta Twilio para habilitar fallback por SMS
            </p>

            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <Label>Provedor</Label>
                {connectionsLoading ? (
                  <Skeleton className="h-9 w-full" />
                ) : (
                  <Input value={getMetadataString(smsConnection, "provider_name") ?? "Twilio"} readOnly />
                )}
              </div>
              <div>
                <Label>Status</Label>
                {connectionsLoading ? (
                  <Skeleton className="h-9 w-full" />
                ) : (
                  <Input value={getMetadataString(smsConnection, "status") ?? smsConnection?.status ?? "desconectado"} readOnly />
                )}
              </div>
            </div>
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Último teste: {connectionsLoading ? "Carregando..." : formatLastHealthCheck(smsConnection)}
              </p>
              {smsConnection?.last_health_check?.error && (
                <p className="text-xs text-destructive">Erro: {smsConnection.last_health_check.error}</p>
              )}
              {!smsConnection?.has_credentials && !connectionsLoading && (
                <p className="text-xs text-muted-foreground">
                  Credenciais não configuradas. Atualize os dados em Provedores &gt; Twilio.
                </p>
              )}
              <ConnectionActions
                onTest={smsConnection ? () => handleTestConnection("sms", getMetadataString(smsConnection, "provider_id")) : undefined}
                onConfigure={() => navigate("/providers")}
                isTesting={testConnection.isPending && testingChannel === "sms"}
                disableTest={connectionsLoading || !smsConnection?.has_credentials || testConnection.isPending}
                disableConfigure={connectionsLoading}
                testLabel="Testar SMS"
                configureLabel="Reconfigurar"
              />
            </div>
          </CardContent>
        </Card>

        {/* Telegram */}
        <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
              <div className="flex items-center">
                <Send className="mr-2 h-5 w-5 text-primary" />
                Telegram Bot
              </div>
              <ConnectionStatusBadge
                status={telegramConnection?.status ?? "disconnected"}
                isLoading={connectionsLoading}
              />
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Integração planejada. Entre em contato com o time de operações para priorizar este canal.
            </p>
            <div className="space-y-2 text-xs text-muted-foreground">
              <p>Último teste: {connectionsLoading ? "Carregando..." : formatLastHealthCheck(telegramConnection)}</p>
              <p>Reconfiguração disponível via módulo de provedores.</p>
            </div>
          </CardContent>
        </Card>
        </TabsContent>

        {/* Tarifas */}
        <TabsContent value="rates" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center">
                  <Globe className="mr-2 h-5 w-5 text-primary" />
                  Rate Cards (Tarifas por País/Categoria)
                </div>
                <div className="flex space-x-2">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleCSVUpload}
                    className="hidden"
                  />
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={importRates.isPending}
                  >
                    <Upload className="mr-2 h-4 w-4" />
                    {importRates.isPending ? "Importando..." : "Importar CSV"}
                  </Button>
                  <Button variant="outline" size="sm">
                    <Download className="mr-2 h-4 w-4" />
                    Exportar
                  </Button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {ratesLoading ? (
                <div className="space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-5 gap-4 p-3 bg-muted/30 rounded-lg font-medium text-sm">
                    <div>País</div>
                    <div>Categoria</div>
                    <div>Provedor</div>
                    <div>Custo Unitário</div>
                    <div>Atualizado</div>
                  </div>

                  {rates.length === 0 ? (
                    <p className="text-center text-muted-foreground py-8">
                      Nenhuma tarifa cadastrada. Importe um CSV para começar.
                    </p>
                  ) : (
                    rates.map((rate) => (
                      <div
                        key={rate.id}
                        className="grid grid-cols-5 gap-4 p-3 rounded-lg bg-card border hover:bg-muted/20 transition-colors"
                      >
                        <div className="font-medium">{rate.country_iso || "Global"}</div>
                        <div>
                          <Badge className={rate.category.toLowerCase() === "marketing"
                            ? "bg-warning/10 text-warning border-warning/20"
                            : "bg-primary/10 text-primary border-primary/20"
                          }>
                            {rate.category}
                          </Badge>
                        </div>
                        <div className="text-sm font-medium text-muted-foreground">
                          {rate.provider_name}
                        </div>
                        <div className="font-medium">€{(rate.unit_cost_minor / 100).toFixed(4)}</div>
                        <div className="text-sm text-muted-foreground">
                          {rate.effective_from ? new Date(rate.effective_from).toLocaleDateString() : "-"}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              <Separator className="my-6" />
              
              <div className="space-y-4">
                <h4 className="font-semibold">Configurações de Fallback</h4>
                <div className="grid md:grid-cols-3 gap-4">
                  <div>
                    <Label>Custo Email</Label>
                    <Input value="€0.001" />
                    <p className="text-xs text-muted-foreground mt-1">Por mensagem</p>
                  </div>
                  <div>
                    <Label>Custo SMS</Label>
                    <Input value="€0.045" />
                    <p className="text-xs text-muted-foreground mt-1">Variável por país</p>
                  </div>
                  <div>
                    <Label>Custo Telegram</Label>
                    <Input value="€0.000" />
                    <p className="text-xs text-muted-foreground mt-1">Gratuito (com limites)</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Organização */}
        <TabsContent value="organization" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="mr-2 h-5 w-5 text-primary" />
                Informações da Organização
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {orgLoading ? (
                <div className="space-y-4">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <Label>Nome da Organização</Label>
                    <Input value={organization.name} readOnly />
                  </div>
                  <div>
                    <Label>Email do Usuário</Label>
                    <Input value={organization.user_email || "-"} readOnly />
                  </div>
                  <div>
                    <Label>Role</Label>
                    <Input value={organization.role || "member"} readOnly />
                  </div>
                  <div>
                    <Label>ID da Organização</Label>
                    <Input value={organization.id || "-"} readOnly className="font-mono text-xs" />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Shield className="mr-2 h-5 w-5 text-primary" />
                Configurações de Segurança
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Autenticação de dois fatores</p>
                  <p className="text-sm text-muted-foreground">Adicione uma camada extra de segurança</p>
                </div>
                <Switch />
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Logs de auditoria</p>
                  <p className="text-sm text-muted-foreground">Registrar todas as ações sensíveis</p>
                </div>
                <Switch defaultChecked />
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Notificações de segurança</p>
                  <p className="text-sm text-muted-foreground">Email quando detectar atividade suspeita</p>
                </div>
                <Switch defaultChecked />
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cobrança */}
        <TabsContent value="billing" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="space-y-1">
                  <div className="flex items-center">
                    <CreditCard className="mr-2 h-5 w-5 text-primary" />
                    <span className="text-lg font-semibold">{planName}</span>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {billing
                      ? `Status: ${planStatusLabel}`
                      : "Ative um plano para habilitar billing e limites de uso."}
                  </p>
                </div>
                <Badge className={planBadgeClass()}>{planStatusLabel}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {billingLoading ? (
                <div className="grid gap-4 md:grid-cols-3">
                  <Skeleton className="h-24 rounded-lg" />
                  <Skeleton className="h-24 rounded-lg" />
                  <Skeleton className="h-24 rounded-lg" />
                </div>
              ) : (
                <>
                  <div className="grid gap-6 md:grid-cols-3">
                    <div className="space-y-2">
                      <p className="text-sm text-muted-foreground">Valor recorrente</p>
                      <p className="text-2xl font-semibold">
                        {formatCurrency(billing?.price_amount_minor, billing?.price_currency)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {billing?.cancel_at_period_end
                          ? "Cancelamento programado ao fim do ciclo atual."
                          : "Renovação automática ativa."}
                      </p>
                    </div>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between text-sm font-medium">
                        <span>Uso de mensagens</span>
                        <span>
                          {messageQuota > 0
                            ? `${messageUsage.toLocaleString()} / ${messageQuota.toLocaleString()}`
                            : `${messageUsage.toLocaleString()} mensagens`}
                        </span>
                      </div>
                      <Progress value={usagePercent} className="h-2" />
                      <p className="text-xs text-muted-foreground">
                        {messageQuota > 0
                          ? `${usagePercent}% da franquia utilizada`
                          : "Defina uma franquia no preço configurado."}
                      </p>
                    </div>
                    <div className="space-y-2">
                      <p className="text-sm text-muted-foreground">Próxima cobrança</p>
                      <p className="text-lg font-semibold">
                        {formatNextBilling(billing?.next_billing_at)}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        Método de pagamento:
                        {billing?.payment_method_brand && billing?.payment_method_last4 ? (
                          <span className="ml-1 font-medium">
                            {billing.payment_method_brand.toUpperCase()} •••• {billing.payment_method_last4}
                          </span>
                        ) : (
                          <span className="ml-1">configure no portal de cobrança.</span>
                        )}
                      </p>
                    </div>
                  </div>

                  <Separator />

                  <div className="flex flex-wrap gap-2">
                    {billing?.latest_invoice_url ? (
                      <Button variant="outline" asChild>
                        <a href={billing.latest_invoice_url} target="_blank" rel="noopener noreferrer">
                          Última fatura
                        </a>
                      </Button>
                    ) : (
                      <Button variant="outline" disabled>
                        Última fatura
                      </Button>
                    )}
                    <Button
                      variant="outline"
                        onClick={handleManagePlan}
                        disabled={billingLoading || createBillingCheckout.isPending}
                    >
                      {createBillingCheckout.isPending ? "Redirecionando..." : "Alterar Plano"}
                    </Button>
                      <Button
                        onClick={async () => {
                          try {
                            const resp = await createBillingPortal.mutateAsync();
                            window.location.href = resp.url;
                          } catch (err) {
                            toast({
                              title: "Não foi possível abrir o portal",
                              description: (
                                <span>
                                  Contate o suporte: <a href="mailto:support@example.com">support@example.com</a>
                                </span>
                              ) as unknown as string,
                              variant: "destructive",
                            });
                          }
                        }}
                        disabled={billingLoading || createBillingPortal.isPending}
                      >
                        {createBillingPortal.isPending ? "Abrindo..." : "Gerenciar assinatura"}
                      </Button>
                    <Button variant="outline" disabled>
                      Cancelar Assinatura
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      </div>
    </SimpleLayout>
  );
};

export default Settings;