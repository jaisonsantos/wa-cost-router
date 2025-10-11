import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChannelMetric, QueueMetric } from "@/types/api";
import SlaComplianceIndicator from "@/components/SlaComplianceIndicator";
import { Clock3, MessageCircle, Users } from "lucide-react";

interface ChannelMetricCardProps {
  metric: ChannelMetric;
  queueMetric?: QueueMetric;
}

const toTitleCase = (value: string) => value.replace(/(^|[_-])(\w)/g, (_, delimiter, char) => `${delimiter ? " " : ""}${char.toUpperCase()}`);

const formatSeconds = (seconds: number | null) => {
  if (seconds === null) {
    return "Sem dados";
  }

  if (seconds < 60) {
    return `${seconds.toFixed(0)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remaining = Math.round(seconds % 60);
  return `${minutes}m ${remaining.toString().padStart(2, "0")}s`;
};

const ChannelMetricCard = ({ metric, queueMetric }: ChannelMetricCardProps) => {
  const openBacklog = queueMetric?.backlog.open ?? metric.backlog.open;
  const pendingBacklog = queueMetric?.backlog.pending ?? metric.backlog.pending;
  const closedBacklog = queueMetric?.backlog.closed ?? metric.backlog.closed;
  const totalQueue = queueMetric?.backlog.total ?? openBacklog + pendingBacklog + closedBacklog;

  return (
    <Card className="border-border bg-card/60 backdrop-blur">
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center justify-between text-base font-semibold">
          <span>{toTitleCase(metric.channel)}</span>
          <Badge variant="secondary" className="text-xs uppercase tracking-wide">
            {metric.conversations_opened.toLocaleString()} abertas
          </Badge>
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {metric.conversations_closed.toLocaleString()} conversas encerradas no período
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-3 text-sm">
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <MessageCircle className="h-4 w-4" />
              <span>Backlog</span>
            </div>
            <p className="mt-2 text-lg font-semibold">{openBacklog.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Abertas</p>
          </div>
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Users className="h-4 w-4" />
              <span>Na fila</span>
            </div>
            <p className="mt-2 text-lg font-semibold">{pendingBacklog.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Pendentes</p>
          </div>
          <div className="rounded-lg border bg-muted/40 p-3">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Clock3 className="h-4 w-4" />
              <span>FRT médio</span>
            </div>
            <p className="mt-2 text-lg font-semibold">
              {formatSeconds(metric.first_response.average_seconds)}
            </p>
            <p className="text-xs text-muted-foreground">Amostra: {metric.first_response.sample_size}</p>
          </div>
        </div>

        <SlaComplianceIndicator
          complianceRate={metric.sla.compliance_rate}
          targetSeconds={metric.sla.target_seconds}
        />

        <div className="rounded-lg border border-dashed bg-muted/30 p-3 text-xs text-muted-foreground">
          <div className="flex items-center justify-between">
            <span>Conversas dentro do SLA</span>
            <span className="font-semibold text-success">{metric.sla.within_target.toLocaleString()}</span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span>Total monitorado</span>
            <span className="font-semibold">{metric.sla.total_tracked.toLocaleString()}</span>
          </div>
          <div className="mt-1 flex items-center justify-between">
            <span>Itens totais na fila</span>
            <span className="font-semibold">{totalQueue.toLocaleString()}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default ChannelMetricCard;
