import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { SegmentBehaviorRule } from "@/types/api";

export interface SegmentBehaviorFieldProps {
  value: SegmentBehaviorRule;
  onChange: (value: SegmentBehaviorRule) => void;
  disabled?: boolean;
  className?: string;
}

const DEFAULT_BEHAVIOR: SegmentBehaviorRule = {
  requireConsent: true,
  includeOptedOut: false,
  holdoutPercentage: null,
};

const normalizeBehavior = (behavior?: SegmentBehaviorRule | null): SegmentBehaviorRule => ({
  requireConsent: behavior?.requireConsent ?? DEFAULT_BEHAVIOR.requireConsent,
  includeOptedOut: behavior?.includeOptedOut ?? DEFAULT_BEHAVIOR.includeOptedOut,
  holdoutPercentage: behavior?.holdoutPercentage ?? DEFAULT_BEHAVIOR.holdoutPercentage,
});

export const SegmentBehaviorField = ({
  value,
  onChange,
  disabled = false,
  className,
}: SegmentBehaviorFieldProps) => {
  const behavior = normalizeBehavior(value);

  const updateBehavior = (updates: Partial<SegmentBehaviorRule>) => {
    onChange({ ...behavior, ...updates });
  };

  return (
    <Card className={cn("border-dashed", className)}>
      <CardHeader>
        <CardTitle className="text-base font-semibold">Comportamento do segmento</CardTitle>
        <p className="text-sm text-muted-foreground">
          Ajuste como o segmento deve interagir com políticas de consentimento e testes de campanha.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Label htmlFor="segment-require-consent" className="font-medium">
              Respeitar consentimento ativo
            </Label>
            <p className="text-sm text-muted-foreground">
              Quando habilitado, somente contatos com opt-in válido serão direcionados para campanhas.
            </p>
          </div>
          <Switch
            id="segment-require-consent"
            checked={behavior.requireConsent}
            onCheckedChange={(checked) => updateBehavior({ requireConsent: checked })}
            disabled={disabled}
          />
        </div>

        <div className="flex items-start justify-between gap-4">
          <div>
            <Label htmlFor="segment-include-opted-out" className="font-medium">
              Incluir contatos opt-out em relatórios
            </Label>
            <p className="text-sm text-muted-foreground">
              Mantém contatos com opt-out visíveis para análises, mas bloqueados para envio de mensagens.
            </p>
          </div>
          <Switch
            id="segment-include-opted-out"
            checked={behavior.includeOptedOut}
            onCheckedChange={(checked) => updateBehavior({ includeOptedOut: checked })}
            disabled={disabled}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="segment-holdout" className="font-medium">
            Percentual de holdout opcional
          </Label>
          <p className="text-sm text-muted-foreground">
            Reserve automaticamente uma fração dos contatos para testes A/B ou controle. Use valores de 0 a 50%.
          </p>
          <Input
            id="segment-holdout"
            type="number"
            min={0}
            max={50}
            step={1}
            value={behavior.holdoutPercentage ?? ""}
            onChange={(event) => {
              const numeric = event.target.value === "" ? null : Number(event.target.value);
              if (numeric === null || Number.isFinite(numeric)) {
                updateBehavior({ holdoutPercentage: numeric });
              }
            }}
            placeholder="0"
            disabled={disabled}
          />
        </div>
      </CardContent>
    </Card>
  );
};

export default SegmentBehaviorField;
