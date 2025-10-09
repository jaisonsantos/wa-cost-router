import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { SegmentAttributeRulesField } from "./SegmentAttributeRulesField";
import { SegmentTagsField } from "./SegmentTagsField";
import { SegmentBehaviorField } from "./SegmentBehaviorField";
import {
  ContactSegment,
  SegmentAttributeRule,
  SegmentBehaviorRule,
} from "@/types/api";

const attributeRuleSchema = z.object({
  key: z.string().min(1, "Informe o atributo"),
  operator: z.enum(["equals", "not_equals", "contains", "in"]),
  values: z.array(z.string().min(1, "Informe ao menos um valor")),
});

const behaviorSchema = z.object({
  requireConsent: z.boolean(),
  includeOptedOut: z.boolean(),
  holdoutPercentage: z
    .number()
    .min(0, "Use valores de 0 a 50")
    .max(50, "Use valores de 0 a 50")
    .nullable()
    .optional(),
});

const segmentFormSchema = z.object({
  name: z.string().min(1, "Informe um nome"),
  slug: z
    .string()
    .min(1, "Informe o identificador")
    .regex(/^[a-z0-9][a-z0-9_-]*$/, "Use apenas letras minúsculas, números, hífen ou sublinhado"),
  description: z.string().optional(),
  attributes: z.array(attributeRuleSchema).default([]),
  tags: z.array(z.string()).default([]),
  behavior: behaviorSchema,
});

export type SegmentFormValues = z.infer<typeof segmentFormSchema>;

const normalizeAttributeRules = (rules?: SegmentAttributeRule[] | null): SegmentAttributeRule[] => {
  if (!Array.isArray(rules)) return [];
  return rules
    .filter((rule): rule is SegmentAttributeRule => Boolean(rule))
    .map((rule) => ({
      key: rule.key ?? "",
      operator: rule.operator ?? "equals",
      values: Array.isArray(rule.values) ? rule.values : [],
    }))
    .filter((rule) => rule.key.trim().length > 0);
};

const normalizeBehavior = (behavior?: SegmentBehaviorRule | null): SegmentBehaviorRule => ({
  requireConsent: behavior?.requireConsent ?? true,
  includeOptedOut: behavior?.includeOptedOut ?? false,
  holdoutPercentage:
    typeof behavior?.holdoutPercentage === "number" ? behavior?.holdoutPercentage : null,
});

const getDefaultValues = (segment?: ContactSegment | null): SegmentFormValues => ({
  name: segment?.name ?? "",
  slug: segment?.slug ?? "",
  description: segment?.description ?? "",
  attributes: normalizeAttributeRules(segment?.criteria?.attributes as SegmentAttributeRule[] | undefined),
  tags: Array.isArray(segment?.criteria?.tags)
    ? [...(segment?.criteria?.tags as string[])]
    : [],
  behavior: normalizeBehavior(segment?.criteria?.behavior as SegmentBehaviorRule | undefined),
});

export interface SegmentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (values: SegmentFormValues) => Promise<void> | void;
  isSubmitting?: boolean;
  segment?: ContactSegment | null;
}

export const SegmentFormDialog = ({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting = false,
  segment,
}: SegmentFormDialogProps) => {
  const form = useForm<SegmentFormValues>({
    resolver: zodResolver(segmentFormSchema),
    defaultValues: getDefaultValues(segment),
  });

  useEffect(() => {
    if (open) {
      form.reset(getDefaultValues(segment));
    }
  }, [form, segment, open]);

  const handleSubmit = async (values: SegmentFormValues) => {
    await onSubmit({
      ...values,
      attributes: values.attributes.map((rule) => ({
        ...rule,
        values: rule.values.map((entry) => entry.trim()).filter(Boolean),
      })),
      tags: values.tags.map((tag) => tag.trim()).filter(Boolean),
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{segment ? "Editar segmento" : "Novo segmento"}</DialogTitle>
          <DialogDescription>
            Configure atributos, tags e comportamento para direcionar campanhas e relatórios com segurança.
          </DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2">
              <FormField
                control={form.control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nome</FormLabel>
                    <FormControl>
                      <Input placeholder="Clientes prioritários" disabled={isSubmitting} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="slug"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Identificador (slug)</FormLabel>
                    <FormControl>
                      <Input placeholder="vip_customers" disabled={isSubmitting} {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Descrição</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Contextualize o objetivo do segmento e quando deve ser usado."
                      rows={3}
                      disabled={isSubmitting}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="attributes"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <SegmentAttributeRulesField
                      value={field.value}
                      onChange={field.onChange}
                      disabled={isSubmitting}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="tags"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <SegmentTagsField
                      value={field.value}
                      onChange={field.onChange}
                      disabled={isSubmitting}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="behavior"
              render={({ field }) => (
                <FormItem>
                  <FormControl>
                    <SegmentBehaviorField
                      value={field.value}
                      onChange={field.onChange}
                      disabled={isSubmitting}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {segment ? "Salvar alterações" : "Criar segmento"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export default SegmentFormDialog;
