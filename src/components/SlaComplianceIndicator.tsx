import { Progress } from "@/components/ui/progress";

interface SlaComplianceIndicatorProps {
  complianceRate: number | null;
  targetSeconds: number | null;
}

const getComplianceColor = (complianceRate: number | null) => {
  if (complianceRate === null) {
    return "text-muted-foreground";
  }

  if (complianceRate >= 90) {
    return "text-success";
  }

  if (complianceRate >= 80) {
    return "text-warning";
  }

  return "text-destructive";
};

const getProgressVariant = (complianceRate: number | null) => {
  if (complianceRate === null) {
    return "bg-muted";
  }

  if (complianceRate >= 90) {
    return "bg-success";
  }

  if (complianceRate >= 80) {
    return "bg-warning";
  }

  return "bg-destructive";
};

const SlaComplianceIndicator = ({ complianceRate, targetSeconds }: SlaComplianceIndicatorProps) => {
  const safeCompliance = complianceRate ?? 0;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Compliance SLA</span>
        <span className={`font-semibold ${getComplianceColor(complianceRate)}`}>
          {complianceRate === null ? "Sem dados" : `${safeCompliance.toFixed(1)}%`}
        </span>
      </div>
      <Progress
        value={Math.max(0, Math.min(100, safeCompliance))}
        className="h-2 bg-muted"
        indicatorClassName={`transition-all ${getProgressVariant(complianceRate)}`}
      />
      {targetSeconds !== null && (
        <p className="text-xs text-muted-foreground">
          Meta de primeiro atendimento: {Math.round(targetSeconds)}s
        </p>
      )}
    </div>
  );
};

export default SlaComplianceIndicator;
