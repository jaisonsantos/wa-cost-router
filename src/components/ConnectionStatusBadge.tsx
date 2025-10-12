import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { AlertCircle, AlertTriangle, CheckCircle, Loader2, Plug } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type ConnectionStatus = "healthy" | "warning" | "error" | "disconnected" | "unknown";

const STATUS_CONFIG: Record<ConnectionStatus, { label: string; className: string; Icon: LucideIcon }> = {
  healthy: {
    label: "Saudável",
    className: "bg-success/10 text-success border-success/20",
    Icon: CheckCircle,
  },
  warning: {
    label: "Atenção",
    className: "bg-warning/10 text-warning border-warning/20",
    Icon: AlertTriangle,
  },
  error: {
    label: "Falha",
    className: "bg-destructive/10 text-destructive border-destructive/20",
    Icon: AlertCircle,
  },
  disconnected: {
    label: "Desconectado",
    className: "bg-muted/10 text-muted-foreground border-border",
    Icon: Plug,
  },
  unknown: {
    label: "Desconhecido",
    className: "bg-muted/10 text-muted-foreground border-border",
    Icon: AlertCircle,
  },
};

interface ConnectionStatusBadgeProps {
  status?: string | null;
  isLoading?: boolean;
}

const normalizeStatus = (status?: string | null): ConnectionStatus => {
  if (!status) {
    return "unknown";
  }
  const normalized = status.toLowerCase();
  if (normalized === "healthy" || normalized === "warning" || normalized === "error") {
    return normalized;
  }
  if (normalized === "disconnected" || normalized === "inactive") {
    return "disconnected";
  }
  return "unknown";
};

const ConnectionStatusBadge = ({ status, isLoading = false }: ConnectionStatusBadgeProps) => {
  if (isLoading) {
    return (
      <Badge className="gap-2 bg-muted/10 text-muted-foreground border-border">
        <Loader2 className="h-4 w-4 animate-spin" />
        Carregando
      </Badge>
    );
  }

  const normalized = normalizeStatus(status);
  const { label, className, Icon } = STATUS_CONFIG[normalized];

  return (
    <Badge className={cn("gap-2", className)}>
      <Icon className="h-4 w-4" />
      {label}
    </Badge>
  );
};

export default ConnectionStatusBadge;
