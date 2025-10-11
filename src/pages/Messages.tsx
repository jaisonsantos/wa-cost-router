import { useMemo, useState } from "react";
import { useMessageJobs, useMessageJobDetails } from "@/hooks/useApi";
import SimpleLayout from "@/components/SimpleLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CheckCircle, XCircle, Clock, AlertCircle, Eye } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { ptBR } from "date-fns/locale";
import { MessageJobDetail, MessageJobSummary } from "@/types/api";

export default function Messages() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const channelParam = channelFilter === "all" ? undefined : channelFilter;

  const { data: jobs, isLoading } = useMessageJobs({
    status: statusFilter === "all" ? undefined : statusFilter,
    channel: channelParam,
  });
  const { data: jobDetails } = useMessageJobDetails(selectedJobId ?? "", { channel: channelParam });

  const jobsList: MessageJobSummary[] = jobs ?? [];
  const jobDetailsData: MessageJobDetail | undefined = jobDetails;

  const availableChannels = useMemo(
    () => Array.from(new Set(jobsList.map((job) => job.channel))).sort(),
    [jobsList],
  );

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "delivered":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "failed":
        return <XCircle className="h-4 w-4 text-red-600" />;
      case "processing":
        return <Clock className="h-4 w-4 text-blue-600" />;
      default:
        return <AlertCircle className="h-4 w-4 text-yellow-600" />;
    }
  };

  const getStatusVariant = (status: string): "default" | "destructive" | "secondary" | "outline" => {
    switch (status) {
      case "delivered":
        return "default";
      case "failed":
        return "destructive";
      case "processing":
        return "secondary";
      default:
        return "outline";
    }
  };

  const formatDirection = (direction: string) => {
    return direction === "inbound" ? "Inbound" : "Outbound";
  };

  const getDirectionVariant = (direction: string): "default" | "destructive" | "secondary" | "outline" => {
    return direction === "inbound" ? "secondary" : "default";
  };

  if (isLoading) {
    return (
      <SimpleLayout>
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Carregando mensagens...</div>
        </div>
      </SimpleLayout>
    );
  }

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold">Mensagens</h1>
            <p className="text-muted-foreground mt-2">
              Histórico de mensagens enviadas e suas tentativas de entrega
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[200px]" aria-label="Filtrar por status">
                <SelectValue placeholder="Filtrar por status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="pending">Pendente</SelectItem>
                <SelectItem value="processing">Processando</SelectItem>
                <SelectItem value="delivered">Entregue</SelectItem>
                <SelectItem value="failed">Falhou</SelectItem>
              </SelectContent>
            </Select>

            <Select value={channelFilter} onValueChange={setChannelFilter}>
              <SelectTrigger className="w-[200px]" aria-label="Filtrar por canal">
                <SelectValue placeholder="Filtrar por canal" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os canais</SelectItem>
                {availableChannels.map((channel) => (
                  <SelectItem key={channel} value={channel}>
                    {channel.charAt(0).toUpperCase() + channel.slice(1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Jobs de Mensagens</CardTitle>
            <CardDescription>
              {jobsList.length} mensagens encontradas
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Número</TableHead>
                  <TableHead>Direção</TableHead>
                  <TableHead>Canal</TableHead>
                  <TableHead>Endereço</TableHead>
                  <TableHead>Contato</TableHead>
                  <TableHead>Template</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Custo</TableHead>
                  <TableHead>Criado</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobsList.map((job) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-mono text-sm">
                      {job.to_number}
                    </TableCell>
                    <TableCell>
                      <Badge variant={getDirectionVariant(job.direction)}>
                        {formatDirection(job.direction)}
                      </Badge>
                    </TableCell>
                    <TableCell className="capitalize">{job.channel}</TableCell>
                    <TableCell className="font-mono text-sm">
                      {job.channel_address}
                    </TableCell>
                    <TableCell>{job.contact_name ?? "Contato desconhecido"}</TableCell>
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium">{job.template_id}</span>
                        <span className="text-xs text-muted-foreground capitalize">
                          {job.template_category}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStatusIcon(job.status)}
                        <Badge variant={getStatusVariant(job.status)}>
                          {job.status}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      {job.total_cost_minor ? `€${(job.total_cost_minor / 100).toFixed(4)}` : "-"}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDistanceToNow(new Date(job.created_at), { addSuffix: true, locale: ptBR })}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setSelectedJobId(job.id)}
                        aria-label="Ver detalhes"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Dialog open={!!selectedJobId} onOpenChange={() => setSelectedJobId(null)}>
          <DialogContent className="max-w-3xl">
            <DialogHeader>
              <DialogTitle>Detalhes da Mensagem</DialogTitle>
            </DialogHeader>
            
            {jobDetailsData && (
              <div className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Número</p>
                    <p className="font-mono">{jobDetailsData.to_number}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Contato</p>
                    <p>{jobDetailsData.contact_name ?? "Contato desconhecido"}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Direção</p>
                    <Badge variant={getDirectionVariant(jobDetailsData.direction)}>
                      {formatDirection(jobDetailsData.direction)}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Canal</p>
                    <p className="capitalize">{jobDetailsData.channel}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Endereço do Canal</p>
                    <p className="font-mono">{jobDetailsData.channel_address}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Template</p>
                    <p>{jobDetailsData.template_id}</p>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Status</p>
                    <Badge variant={getStatusVariant(jobDetailsData.status)}>
                      {jobDetailsData.status}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">País</p>
                    <p>{jobDetailsData.country_iso || "N/A"}</p>
                  </div>
                </div>

                <div>
                  <h3 className="font-semibold mb-3">Tentativas de Entrega</h3>
                  <div className="space-y-2">
                    {jobDetailsData.attempts.map((attempt) => (
                      <Card key={attempt.id}>
                        <CardContent className="pt-6">
                          <div className="flex items-start justify-between">
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">Tentativa #{attempt.attempt_number}</span>
                                <Badge variant={attempt.status === "success" ? "default" : "destructive"}>
                                  {attempt.status}
                                </Badge>
                              </div>
                              <div className="text-sm text-muted-foreground">
                                Provider: {attempt.provider_name}
                              </div>
                              {attempt.latency_ms !== null && attempt.latency_ms !== undefined && (
                                <div className="text-sm text-muted-foreground">
                                  Latência: {attempt.latency_ms}ms
                                </div>
                              )}
                              {attempt.error_code && (
                                <div className="text-sm text-red-600">
                                  Erro: {attempt.error_code}
                                </div>
                              )}
                              {attempt.error_message && (
                                <div className="text-xs text-muted-foreground">
                                  {attempt.error_message}
                                </div>
                              )}
                            </div>
                            {"timestamp" in attempt && attempt.timestamp ? (
                              <div className="text-sm text-muted-foreground">
                                {formatDistanceToNow(new Date(attempt.timestamp), { addSuffix: true, locale: ptBR })}
                              </div>
                            ) : null}
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>

                {jobDetailsData.conversation_history && jobDetailsData.conversation_history.length > 0 ? (
                  <div>
                    <h3 className="font-semibold mb-3">Histórico da Conversa</h3>
                    <div className="space-y-4">
                      {jobDetailsData.conversation_history.map((history) => (
                        <Card key={history.channel}>
                          <CardHeader className="pb-3">
                            <CardTitle className="text-lg capitalize">{history.channel}</CardTitle>
                            <CardDescription>
                              {history.contact_name ? `${history.contact_name} • ` : ""}
                              {history.contact_address}
                            </CardDescription>
                          </CardHeader>
                          <CardContent className="space-y-3">
                            {history.messages.length > 0 ? (
                              history.messages.map((message) => (
                                <div key={message.id} className="rounded-lg border bg-muted/40 p-3">
                                  <div className="flex items-center justify-between gap-2">
                                    <div className="flex items-center gap-2">
                                      <Badge variant={getDirectionVariant(message.direction)}>
                                        {formatDirection(message.direction)}
                                      </Badge>
                                      {message.status ? (
                                        <span className="text-xs uppercase text-muted-foreground">
                                          {message.status}
                                        </span>
                                      ) : null}
                                    </div>
                                    <span className="text-xs text-muted-foreground">
                                      {message.timestamp
                                        ? formatDistanceToNow(new Date(message.timestamp), {
                                            addSuffix: true,
                                            locale: ptBR,
                                          })
                                        : "Sem data"}
                                    </span>
                                  </div>
                                  <p className="mt-2 text-sm leading-relaxed whitespace-pre-wrap">
                                    {message.content}
                                  </p>
                                  {message.sender ? (
                                    <p className="mt-2 text-xs text-muted-foreground">
                                      Remetente: {message.sender}
                                    </p>
                                  ) : null}
                                </div>
                              ))
                            ) : (
                              <p className="text-sm text-muted-foreground">
                                Nenhuma mensagem registrada neste canal.
                              </p>
                            )}
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </SimpleLayout>
  );
}
