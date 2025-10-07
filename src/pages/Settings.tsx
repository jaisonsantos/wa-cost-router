import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import SimpleLayout from "@/components/SimpleLayout";
import { useRates, useImportRatesCSV, useCurrentOrg, useCreateWAConnection } from "@/hooks/useApi";
import {
  MessageSquare,
  Globe,
  Mail,
  Smartphone,
  Send,
  CheckCircle,
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

type ConnectionStatus = "healthy" | "warning" | "disconnected";

interface WhatsAppConnection {
  connected: boolean;
  businessId: string;
  phoneId: string;
  lastSync: string;
  status: ConnectionStatus;
}

interface EmailConnection {
  connected: boolean;
  provider: string;
  endpoint: string;
  status: ConnectionStatus;
}

interface SmsConnection {
  connected: boolean;
  provider: string;
  status: ConnectionStatus;
}

interface TelegramConnection {
  connected: boolean;
  botToken: string;
  status: ConnectionStatus;
}

interface ConnectionsState {
  whatsapp: WhatsAppConnection;
  email: EmailConnection;
  sms: SmsConnection;
  telegram: TelegramConnection;
}

const Settings = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { data: ratesData, isLoading: ratesLoading } = useRates();
  const { data: orgData, isLoading: orgLoading } = useCurrentOrg();
  const importRates = useImportRatesCSV();
  const createWAConnection = useCreateWAConnection();

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

  const [connections] = useState<ConnectionsState>({
    whatsapp: {
      connected: true,
      businessId: "1234567890123456",
      phoneId: "987654321098765",
      lastSync: "2 horas atrás",
      status: "healthy",
    },
    email: {
      connected: true,
      provider: "SMTP",
      endpoint: "smtp.empresa.com",
      status: "healthy",
    },
    sms: {
      connected: false,
      provider: "Twilio",
      status: "disconnected",
    },
    telegram: {
      connected: true,
      botToken: "123456789:ABC...XYZ",
      status: "healthy",
    },
  });


  const getStatusColor = (status: string) => {
    switch (status) {
      case "healthy":
        return "bg-success/10 text-success border-success/20";
      case "warning":
        return "bg-warning/10 text-warning border-warning/20";
      case "disconnected":
        return "bg-destructive/10 text-destructive border-destructive/20";
      default:
        return "bg-muted/10 text-muted-foreground border-border";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "healthy":
        return <CheckCircle className="h-4 w-4 text-success" />;
      case "warning":
        return <AlertCircle className="h-4 w-4 text-warning" />;
      case "disconnected":
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      default:
        return <AlertCircle className="h-4 w-4 text-muted-foreground" />;
    }
  };

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
          {/* WhatsApp Business */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center">
                  <MessageSquare className="mr-2 h-5 w-5 text-primary" />
                  WhatsApp Business Cloud API
                </div>
                <Badge className={getStatusColor(connections.whatsapp.status)}>
                  {getStatusIcon(connections.whatsapp.status)}
                  Conectado
                </Badge>
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

              <div className="flex items-center justify-between p-3 bg-success/10 rounded-lg">
                <div>
                  <p className="text-sm font-medium text-success">Conexão ativa</p>
                  <p className="text-xs text-muted-foreground">Última sincronização: {connections.whatsapp.lastSync}</p>
                </div>
                <Button variant="outline" size="sm">
                  Testar Conexão
                </Button>
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
                <Badge className={getStatusColor(connections.email.status)}>
                  {getStatusIcon(connections.email.status)}
                  Conectado
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label>Provedor</Label>
                  <Input value={connections.email.provider} readOnly />
                </div>
                <div>
                  <Label>Endpoint SMTP</Label>
                  <Input value={connections.email.endpoint} readOnly />
                </div>
              </div>
              
              <div className="flex space-x-2">
                <Button variant="outline">
                  <Send className="mr-2 h-4 w-4" />
                  Testar Email
                </Button>
                <Button variant="outline">
                  Reconfigurar
                </Button>
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
                <Badge className={getStatusColor(connections.sms.status)}>
                  {getStatusIcon(connections.sms.status)}
                  Desconectado
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Configure sua conta Twilio para habilitar fallback por SMS
              </p>
              
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label>Account SID</Label>
                  <Input placeholder="AC..." />
                </div>
                <div>
                  <Label>Auth Token</Label>
                  <Input type="password" placeholder="Inserir token..." />
                </div>
              </div>
              
              <Button className="bg-gradient-to-r from-primary to-primary/80">
                Conectar Twilio
              </Button>
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
                <Badge className={getStatusColor(connections.telegram.status)}>
                  {getStatusIcon(connections.telegram.status)}
                  Conectado
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Label>Bot Token</Label>
                <Input value={connections.telegram.botToken} type="password" readOnly />
              </div>
              
              <div className="flex space-x-2">
                <Button variant="outline">
                  Testar Bot
                </Button>
                <Button variant="outline">
                  Reconfigurar
                </Button>
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
                <div className="flex items-center">
                  <CreditCard className="mr-2 h-5 w-5 text-primary" />
                  Plano Atual
                </div>
                <Badge className="bg-primary/10 text-primary border-primary/20">
                  Professional
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid md:grid-cols-3 gap-4">
                <div className="p-4 border rounded-lg">
                  <h4 className="font-semibold text-primary">€79/mês</h4>
                  <p className="text-sm text-muted-foreground">Plano Professional</p>
                  <p className="text-xs text-muted-foreground mt-2">Até 5 usuários</p>
                </div>
                
                <div className="p-4 border rounded-lg">
                  <h4 className="font-semibold">€2.847</h4>
                  <p className="text-sm text-muted-foreground">Economizado este mês</p>
                  <p className="text-xs text-success mt-2">ROI: 3.604%</p>
                </div>
                
                <div className="p-4 border rounded-lg">
                  <h4 className="font-semibold">23 de Nov</h4>
                  <p className="text-sm text-muted-foreground">Próxima cobrança</p>
                  <p className="text-xs text-muted-foreground mt-2">Auto-renovação ativa</p>
                </div>
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Método de pagamento</p>
                  <p className="text-sm text-muted-foreground">**** **** **** 1234 (Visa)</p>
                </div>
                <Button variant="outline">
                  Atualizar
                </Button>
              </div>
              
              <div className="flex space-x-2">
                <Button variant="outline">
                  Histórico de Faturas
                </Button>
                <Button variant="outline">
                  Alterar Plano
                </Button>
                <Button variant="destructive">
                  Cancelar Assinatura
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      </div>
    </SimpleLayout>
  );
};

export default Settings;