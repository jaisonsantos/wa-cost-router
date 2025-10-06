import { useEffect, useMemo, useState } from "react";
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
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Separator } from "@/components/ui/separator";

const COUNTRY_OPTIONS = [
  "BR",
  "US",
  "MX",
  "CO",
  "AR",
  "ES",
  "PT",
  "FR",
  "DE",
  "IN",
];

const CATEGORY_OPTIONS = ["marketing", "utility", "authentication"];

const ruleFormSchema = z.object({
  name: z.string().min(1, "Informe um nome"),
  priority: z
    .coerce
    .number({
      required_error: "Informe a prioridade",
      invalid_type_error: "Informe a prioridade",
    })
    .int()
    .min(1, "Prioridade mínima é 1")
    .max(1000, "Prioridade máxima é 1000"),
  is_enabled: z.boolean(),
  countries: z.array(z.string()).default([]),
  categories: z.array(z.string()).default([]),
  templates: z.array(z.string()).default([]),
  primary_provider: z.string().min(1, "Selecione um provedor primário"),
  fallback_chain: z.array(z.string()).default([]),
});

type RuleFormValues = z.infer<typeof ruleFormSchema>;

type RuleCondition = {
  type?: string;
  values?: string[];
};

type RuleActions = {
  primary_provider?: string;
  fallback_chain?: string[];
  [key: string]: unknown;
};

export interface RuleFormRule {
  id: string;
  name: string;
  is_enabled: boolean;
  priority: number;
  conditions: RuleCondition[];
  actions: RuleActions;
}

export interface ProviderOption {
  id: string;
  name: string;
  status?: string;
}

export interface RulePayload {
  name: string;
  priority: number;
  is_enabled: boolean;
  conditions: RuleCondition[];
  actions: {
    primary_provider: string;
    fallback_chain: string[];
  };
}

interface RuleFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: RulePayload) => Promise<void>;
  providers: ProviderOption[];
  initialRule?: RuleFormRule | null;
  isSubmitting?: boolean;
}

const extractValues = (conditions: RuleCondition[] = [], type: string) =>
  conditions
    .filter((condition) => condition?.type === type)
    .flatMap((condition) => (Array.isArray(condition?.values) ? condition!.values! : []));

const getDefaultValues = (rule?: RuleFormRule | null): RuleFormValues => ({
  name: rule?.name ?? "",
  priority: rule?.priority ?? 100,
  is_enabled: rule?.is_enabled ?? true,
  countries: extractValues(rule?.conditions, "country"),
  categories: extractValues(rule?.conditions, "category"),
  templates: extractValues(rule?.conditions, "template"),
  primary_provider: rule?.actions?.primary_provider ?? "",
  fallback_chain: Array.isArray(rule?.actions?.fallback_chain)
    ? [...(rule!.actions!.fallback_chain as string[])]
    : [],
});

export const RuleFormDialog = ({
  open,
  onOpenChange,
  onSubmit,
  providers,
  initialRule,
  isSubmitting = false,
}: RuleFormDialogProps) => {
  const form = useForm<RuleFormValues>({
    resolver: zodResolver(ruleFormSchema),
    defaultValues: getDefaultValues(initialRule),
  });

  const [templateInput, setTemplateInput] = useState("");

  useEffect(() => {
    if (open) {
      form.reset(getDefaultValues(initialRule));
      setTemplateInput("");
    }
  }, [form, initialRule, open]);

  const primaryProvider = form.watch("primary_provider");
  const fallbackChain = form.watch("fallback_chain");
  const selectedCountries = form.watch("countries");
  const selectedCategories = form.watch("categories");
  const templates = form.watch("templates");

  useEffect(() => {
    if (!primaryProvider) return;
    const filtered = fallbackChain.filter((id) => id !== primaryProvider);
    if (filtered.length !== fallbackChain.length) {
      form.setValue("fallback_chain", filtered);
    }
  }, [fallbackChain, form, primaryProvider]);

  const fallbackOptions = useMemo(
    () => providers.filter((provider) => provider.id !== primaryProvider),
    [providers, primaryProvider],
  );

  const toggleValue = (field: "countries" | "categories" | "fallback_chain", value: string) => {
    const current = form.getValues(field);
    if (current.includes(value)) {
      form.setValue(
        field,
        current.filter((item) => item !== value),
      );
    } else {
      form.setValue(field, [...current, value]);
    }
  };

  const handleAddTemplate = () => {
    const value = templateInput.trim();
    if (!value) return;
    if (!templates.includes(value)) {
      form.setValue("templates", [...templates, value]);
    }
    setTemplateInput("");
  };

  const handleRemoveTemplate = (template: string) => {
    form.setValue(
      "templates",
      templates.filter((item) => item !== template),
    );
  };

  const handleSubmit = async (values: RuleFormValues) => {
    const payload: RulePayload = {
      name: values.name.trim(),
      is_enabled: values.is_enabled,
      priority: values.priority,
      conditions: [],
      actions: {
        primary_provider: values.primary_provider,
        fallback_chain: values.fallback_chain,
      },
    };

    if (values.countries.length > 0) {
      payload.conditions.push({ type: "country", values: values.countries });
    }

    if (values.categories.length > 0) {
      payload.conditions.push({ type: "category", values: values.categories });
    }

    if (values.templates.length > 0) {
      payload.conditions.push({ type: "template", values: values.templates });
    }

    try {
      await onSubmit(payload);
      onOpenChange(false);
      form.reset(getDefaultValues(null));
      setTemplateInput("");
    } catch (error) {
      // O erro já é tratado pelo caller (toast). Mantemos o formulário aberto.
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{initialRule ? "Editar regra" : "Nova regra"}</DialogTitle>
          <DialogDescription>
            Configure condições e ações para o roteamento inteligente de mensagens.
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
                    <FormLabel>Nome da regra</FormLabel>
                    <FormControl>
                      <Input placeholder="Ex: BR marketing" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="priority"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Prioridade</FormLabel>
                    <FormControl>
                      <Input type="number" min={1} max={1000} {...field} />
                    </FormControl>
                    <FormDescription>
                      Menor número = maior prioridade na avaliação.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="is_enabled"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-lg border p-4">
                  <div className="space-y-0.5">
                    <FormLabel>Regra ativa</FormLabel>
                    <FormDescription>
                      Desative para pausar temporariamente o roteamento desta regra.
                    </FormDescription>
                  </div>
                  <FormControl>
                    <Switch checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                </FormItem>
              )}
            />

            <Separator />

            <div className="grid gap-6 md:grid-cols-2">
              <FormField
                control={form.control}
                name="countries"
                render={() => (
                  <FormItem>
                    <FormLabel>Países</FormLabel>
                    <FormDescription>
                      Selecione os países onde esta regra deve ser aplicada.
                    </FormDescription>
                    <div className="mt-2 grid gap-2 sm:grid-cols-2">
                      {COUNTRY_OPTIONS.map((country) => (
                        <label
                          key={country}
                          className="flex items-center space-x-2 rounded border p-2 text-sm"
                        >
                          <Checkbox
                            checked={selectedCountries.includes(country)}
                            onCheckedChange={() => toggleValue("countries", country)}
                          />
                          <span>{country}</span>
                        </label>
                      ))}
                    </div>
                    {selectedCountries.length === 0 && (
                      <p className="text-xs text-muted-foreground mt-2">
                        Nenhum país selecionado: a regra será considerada global.
                      </p>
                    )}
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="categories"
                render={() => (
                  <FormItem>
                    <FormLabel>Categorias</FormLabel>
                    <FormDescription>
                      Escolha as categorias de template que ativam esta regra.
                    </FormDescription>
                    <div className="mt-2 grid gap-2">
                      {CATEGORY_OPTIONS.map((category) => (
                        <label
                          key={category}
                          className="flex items-center space-x-2 rounded border p-2 text-sm capitalize"
                        >
                          <Checkbox
                            checked={selectedCategories.includes(category)}
                            onCheckedChange={() => toggleValue("categories", category)}
                          />
                          <span>{category}</span>
                        </label>
                      ))}
                    </div>
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="templates"
              render={() => (
                <FormItem>
                  <FormLabel>Templates específicos (opcional)</FormLabel>
                  <FormDescription>
                    Informe IDs de template para restringir a regra.
                  </FormDescription>
                  <div className="mt-2 flex gap-2">
                    <Input
                      value={templateInput}
                      placeholder="Ex: welcome_message"
                      onChange={(event) => setTemplateInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          event.preventDefault();
                          handleAddTemplate();
                        }
                      }}
                    />
                    <Button type="button" variant="outline" onClick={handleAddTemplate}>
                      Adicionar
                    </Button>
                  </div>
                  {templates.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {templates.map((template) => (
                        <Badge key={template} variant="secondary" className="flex items-center gap-1">
                          {template}
                          <button
                            type="button"
                            className="text-xs text-muted-foreground hover:text-foreground"
                            onClick={() => handleRemoveTemplate(template)}
                          >
                            ×
                          </button>
                        </Badge>
                      ))}
                    </div>
                  )}
                </FormItem>
              )}
            />

            <Separator />

            <FormField
              control={form.control}
              name="primary_provider"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Provedor principal</FormLabel>
                  <FormDescription>
                    Escolha qual provedor será usado quando a regra for satisfeita.
                  </FormDescription>
                  <div className="mt-2 grid gap-2">
                    {providers.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Nenhum provedor disponível. Configure provedores antes de criar a regra.
                      </p>
                    ) : (
                      providers.map((provider) => (
                        <label
                          key={provider.id}
                          className={`flex items-center justify-between rounded border p-3 text-sm ${
                            field.value === provider.id ? "border-primary" : "border-border"
                          }`}
                        >
                          <div>
                            <p className="font-medium">{provider.name}</p>
                            {provider.status && (
                              <p className="text-xs text-muted-foreground">Status: {provider.status}</p>
                            )}
                          </div>
                          <Checkbox
                            checked={field.value === provider.id}
                            onCheckedChange={() => field.onChange(provider.id)}
                          />
                        </label>
                      ))
                    )}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="fallback_chain"
              render={() => (
                <FormItem>
                  <FormLabel>Fallback (ordem de tentativa)</FormLabel>
                  <FormDescription>
                    Selecione provedores alternativos caso o principal falhe.
                  </FormDescription>
                  {fallbackOptions.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Nenhum provedor elegível para fallback.
                    </p>
                  ) : (
                    <ScrollArea className="mt-2 h-40 rounded border p-2">
                      <div className="space-y-2">
                        {fallbackOptions.map((provider) => (
                          <label
                            key={provider.id}
                            className="flex items-center justify-between rounded border p-2 text-sm"
                          >
                            <div>
                              <p className="font-medium">{provider.name}</p>
                              {provider.status && (
                                <p className="text-xs text-muted-foreground">Status: {provider.status}</p>
                              )}
                            </div>
                            <Checkbox
                              checked={fallbackChain.includes(provider.id)}
                              onCheckedChange={() => toggleValue("fallback_chain", provider.id)}
                            />
                          </label>
                        ))}
                      </div>
                    </ScrollArea>
                  )}
                </FormItem>
              )}
            />

            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting || providers.length === 0}>
                {isSubmitting ? "Salvando..." : initialRule ? "Salvar alterações" : "Criar regra"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
};

export default RuleFormDialog;
