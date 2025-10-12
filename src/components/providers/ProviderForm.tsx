import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ProviderFormSchema } from "@/types/api";

type ProviderFormValues = Record<string, string>;

interface ProviderFormProps {
  schema: ProviderFormSchema;
  requiredFields: string[];
  metadata?: Record<string, unknown>;
  initialValues?: Record<string, string | number | boolean>;
  isSubmitting?: boolean;
  onSubmit: (values: ProviderFormValues) => Promise<void> | void;
  onCancel: () => void;
}

const EMPTY_SCHEMA: ProviderFormSchema = { fields: [] };

function applyMask(value: string, mask: string): string {
  if (!mask) {
    return value;
  }

  const raw = value.replace(/[^0-9]/g, "");
  const result: string[] = [];
  let rawIndex = 0;

  for (const char of mask) {
    if (char === "#") {
      if (rawIndex >= raw.length) {
        break;
      }
      result.push(raw[rawIndex]);
      rawIndex += 1;
    } else {
      result.push(char);
    }
  }

  return result.join("");
}

function inferDefaultFromMetadata(key: string, metadata?: Record<string, unknown>): string | undefined {
  if (!metadata) {
    return undefined;
  }

  if (typeof metadata?.defaults === "object" && metadata.defaults !== null) {
    const defaults = metadata.defaults as Record<string, unknown>;
    const candidate = defaults[key];
    if (candidate !== undefined && candidate !== null) {
      return String(candidate);
    }
  }

  if (key === "from_number") {
    const numbers = metadata?.channels as Record<string, unknown> | undefined;
    const sms = numbers?.sms as Record<string, unknown> | undefined;
    const inbound = sms?.inbound_numbers as unknown;
    if (Array.isArray(inbound) && inbound[0]) {
      return String(inbound[0]);
    }
  }

  if (key === "from_email") {
    const channels = metadata?.channels as Record<string, unknown> | undefined;
    const emailChannel = channels?.email as Record<string, unknown> | undefined;
    const fromAddress = emailChannel?.from_address;
    if (typeof fromAddress === "string") {
      return fromAddress;
    }
  }

  return undefined;
}

function buildInitialValues(
  schema: ProviderFormSchema,
  metadata: Record<string, unknown> | undefined,
  initialValues?: Record<string, string | number | boolean>,
): ProviderFormValues {
  const values: ProviderFormValues = {};
  schema.fields.forEach((field) => {
    const key = field.key;
    const provided = initialValues?.[key];
    if (provided !== undefined && provided !== null) {
      values[key] = String(provided);
      return;
    }

    if (field.default_value !== undefined) {
      values[key] = field.default_value;
      return;
    }

    const inferred = inferDefaultFromMetadata(key, metadata);
    values[key] = inferred ?? "";
  });
  return values;
}

export function ProviderForm({
  schema = EMPTY_SCHEMA,
  metadata,
  requiredFields,
  initialValues,
  isSubmitting = false,
  onSubmit,
  onCancel,
}: ProviderFormProps) {
  const normalizedSchema = schema ?? EMPTY_SCHEMA;

  const [values, setValues] = useState<ProviderFormValues>(() =>
    buildInitialValues(normalizedSchema, metadata, initialValues),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    setValues(buildInitialValues(normalizedSchema, metadata, initialValues));
    setErrors({});
    setSubmitError(null);
  }, [normalizedSchema, metadata, initialValues]);

  const requiredSet = useMemo(() => new Set(requiredFields ?? []), [requiredFields]);

  const handleChange = useCallback(
    (key: string, mask?: string) =>
      (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const nextValue = event.target.value;
        setValues((prev) => ({
          ...prev,
          [key]: mask ? applyMask(nextValue, mask) : nextValue,
        }));
        if (errors[key]) {
          setErrors((prev) => ({ ...prev, [key]: "" }));
        }
      },
    [errors],
  );

  const validate = useCallback(
    (currentValues: ProviderFormValues) => {
      const validationErrors: Record<string, string> = {};

      normalizedSchema.fields.forEach((field) => {
        const key = field.key;
        const label = field.label ?? key;
        const value = (currentValues[key] ?? "").toString();
        const isRequired = field.required ?? requiredSet.has(key);

        if (isRequired && value.trim() === "") {
          validationErrors[key] = `O campo "${label}" é obrigatório.`;
          return;
        }

        if (field.validation?.regex && value.trim() !== "") {
          try {
            const regex = new RegExp(field.validation.regex);
            if (!regex.test(value)) {
              validationErrors[key] = field.validation.message ?? `Valor inválido para ${label}.`;
            }
          } catch (error) {
            console.warn("Falha ao compilar regex do campo", key, error);
          }
        }
      });

      return validationErrors;
    },
    [normalizedSchema.fields, requiredSet],
  );

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const validationErrors = validate(values);
      if (Object.keys(validationErrors).length > 0) {
        setErrors(validationErrors);
        return;
      }

      setErrors({});
      setSubmitError(null);
      try {
        await onSubmit(values);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Falha ao salvar credenciais.";
        setSubmitError(message);
      }
    },
    [onSubmit, validate, values],
  );

  return (
    <form className="space-y-6" onSubmit={handleSubmit} data-testid="provider-form" noValidate>
      <div className="space-y-2">
        {normalizedSchema.title && <h3 className="text-lg font-semibold">{normalizedSchema.title}</h3>}
        {normalizedSchema.description && (
          <p className="text-sm text-muted-foreground">{normalizedSchema.description}</p>
        )}
      </div>

      <div className="space-y-4">
        {normalizedSchema.fields.map((field) => {
          const value = values[field.key] ?? "";
          const error = errors[field.key];
          const inputType = field.type ?? "text";
          const id = `provider-field-${field.key}`;

          return (
            <div key={field.key} className="space-y-2">
              <Label htmlFor={id}>{field.label}</Label>
              {inputType === "select" ? (
                <select
                  id={id}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={value}
                  onChange={handleChange(field.key)}
                >
                  <option value="" disabled>
                    Selecione
                  </option>
                  {(field.options ?? []).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={id}
                  type={inputType}
                  placeholder={field.placeholder}
                  value={value}
                  inputMode={inputType === "tel" ? "tel" : undefined}
                  onChange={handleChange(field.key, field.mask)}
                  aria-required={(field.required ?? requiredSet.has(field.key)) || undefined}
                />
              )}

              {field.help_text && <p className="text-sm text-muted-foreground">{field.help_text}</p>}
              {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
            </div>
          );
        })}
      </div>

      {(normalizedSchema.consent_guidance?.length ?? 0) > 0 && (
        <div className="rounded-md border border-muted p-4">
          <h4 className="font-medium">Diretrizes de consentimento</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {normalizedSchema.consent_guidance!.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {(normalizedSchema.testing_instructions?.length ?? 0) > 0 && (
        <div className="rounded-md border border-muted p-4">
          <h4 className="font-medium">Passos de teste</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {normalizedSchema.testing_instructions!.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}

      {submitError && <p className="text-sm text-destructive">{submitError}</p>}

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
          Cancelar
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Salvando..." : "Salvar"}
        </Button>
      </div>
    </form>
  );
}

export default ProviderForm;

