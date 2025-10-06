import { useState } from "react";
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

export default function Messages() {
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  
  const { data: jobs, isLoading } = useMessageJobs({ status: statusFilter === "all" ? undefined : statusFilter });
  const { data: jobDetails } = useMessageJobDetails(selectedJobId || "");

  const jobsList = Array.isArray(jobs) ? jobs : [];
  const jobDetailsData = jobDetails as any;

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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Mensagens</h1>
            <p className="text-muted-foreground mt-2">
              Histórico de mensagens enviadas e suas tentativas de entrega
            </p>
          </div>

          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
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
                  <TableHead>Template</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Custo</TableHead>
                  <TableHead>Criado</TableHead>
                  <TableHead className="text-right">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobsList.map((job: any) => (
                  <TableRow key={job.id}>
                    <TableCell className="font-mono text-sm">
                      {job.to_number}
                    </TableCell>
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
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">Número</p>
                    <p className="font-mono">{jobDetailsData.to_number}</p>
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
                    {jobDetailsData.attempts?.map((attempt: any, index: number) => (
                      <Card key={attempt.id}>
                        <CardContent className="pt-6">
                          <div className="flex items-start justify-between">
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">Tentativa #{index + 1}</span>
                                <Badge variant={attempt.status === "success" ? "default" : "destructive"}>
                                  {attempt.status}
                                </Badge>
                              </div>
                              <div className="text-sm text-muted-foreground">
                                Provider: {attempt.provider_name}
                              </div>
                              {attempt.latency_ms && (
                                <div className="text-sm text-muted-foreground">
                                  Latência: {attempt.latency_ms}ms
                                </div>
                              )}
                              {attempt.error_code && (
                                <div className="text-sm text-red-600">
                                  Erro: {attempt.error_code}
                                </div>
                              )}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {formatDistanceToNow(new Date(attempt.timestamp), { addSuffix: true, locale: ptBR })}
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </SimpleLayout>
  );
}
