import { Fragment } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Plus, Trash2 } from "lucide-react";
import { SegmentAttributeRule } from "@/types/api";

export interface SegmentAttributeRulesFieldProps {
  value: SegmentAttributeRule[];
  onChange: (value: SegmentAttributeRule[]) => void;
  disabled?: boolean;
  className?: string;
}

const DEFAULT_RULE: SegmentAttributeRule = {
  key: "",
  operator: "equals",
  values: [],
};

const operatorLabels: Record<SegmentAttributeRule["operator"], string> = {
  equals: "Igual a",
  not_equals: "Diferente de",
  contains: "Contém",
  in: "Qualquer de",
};

const normalizeRule = (rule: SegmentAttributeRule): SegmentAttributeRule => ({
  key: rule.key ?? "",
  operator: rule.operator ?? "equals",
  values: Array.isArray(rule.values) ? rule.values : [],
});

export const SegmentAttributeRulesField = ({
  value,
  onChange,
  disabled = false,
  className,
}: SegmentAttributeRulesFieldProps) => {
  const rules = Array.isArray(value) ? value.map(normalizeRule) : [];

  const updateRule = (index: number, updates: Partial<SegmentAttributeRule>) => {
    const next = rules.map((rule, idx) => (idx === index ? { ...rule, ...updates } : rule));
    onChange(next);
  };

  const removeRule = (index: number) => {
    const next = rules.filter((_, idx) => idx !== index);
    onChange(next);
  };

  const addRule = () => {
    onChange([...rules, { ...DEFAULT_RULE }]);
  };

  const renderValueInput = (rule: SegmentAttributeRule, index: number) => {
    const valueAsString = rule.values.join(", ");

    return (
      <div className="space-y-2">
        <Label htmlFor={`segment-attribute-values-${index}`}>Valores permitidos</Label>
        <Input
          id={`segment-attribute-values-${index}`}
          placeholder="Use vírgula para separar múltiplos valores"
          value={valueAsString}
          onChange={(event) => {
            const nextValues = event.target.value
              .split(",")
              .map((entry) => entry.trim())
              .filter(Boolean);
            updateRule(index, { values: nextValues });
          }}
          disabled={disabled}
        />
      </div>
    );
  };

  return (
    <Card className={cn("border-dashed", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle className="text-base font-semibold">Regras por atributo</CardTitle>
          <p className="text-sm text-muted-foreground">
            Defina filtros baseados em atributos dos contatos. Os valores aceitam múltiplas opções separados por vírgula.
          </p>
        </div>
        <Button type="button" size="sm" onClick={addRule} disabled={disabled} variant="outline">
          <Plus className="mr-1 h-4 w-4" />
          Adicionar atributo
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {rules.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
            Nenhum filtro configurado. Adicione uma regra para segmentar por atributos.
          </div>
        ) : (
          <div className="space-y-6">
            {rules.map((rule, index) => (
              <Fragment key={`segment-attribute-${index}`}>
                <div className="grid gap-4 md:grid-cols-[1.5fr_1fr]">
                  <div className="space-y-2">
                    <Label htmlFor={`segment-attribute-field-${index}`}>Atributo</Label>
                    <Input
                      id={`segment-attribute-field-${index}`}
                      placeholder="Ex.: country, lifecycle_stage"
                      value={rule.key}
                      onChange={(event) => updateRule(index, { key: event.target.value })}
                      disabled={disabled}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Operador</Label>
                    <Select
                      value={rule.operator}
                      onValueChange={(selected) => updateRule(index, { operator: selected as SegmentAttributeRule["operator"] })}
                      disabled={disabled}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Selecione o operador" />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(operatorLabels).map(([operator, label]) => (
                          <SelectItem key={operator} value={operator}>
                            {label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                {renderValueInput(rule, index)}
                <div className="flex justify-end">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeRule(index)}
                    disabled={disabled}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="mr-1 h-4 w-4" />
                    Remover
                  </Button>
                </div>
                {index < rules.length - 1 && <Separator />}
              </Fragment>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default SegmentAttributeRulesField;
