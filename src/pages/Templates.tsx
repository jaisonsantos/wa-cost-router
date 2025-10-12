import { useMemo, useState } from "react";
import SimpleLayout from "@/components/SimpleLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useTemplates, useSyncTemplates } from "@/hooks/useApi";
import { Loader2, RefreshCw } from "lucide-react";

export default function Templates() {
  const [languageFilter, setLanguageFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");

  const templatesQuery = useTemplates({
    language: languageFilter.trim() || undefined,
    status: statusFilter.trim() || undefined,
  });

  const syncTemplates = useSyncTemplates();

  const languages = useMemo(() => {
    const values = new Set<string>();
    (templatesQuery.data ?? []).forEach((template) => values.add(template.language));
    return Array.from(values).sort();
  }, [templatesQuery.data]);

  const statuses = useMemo(() => {
    const values = new Set<string>();
    (templatesQuery.data ?? []).forEach((template) => values.add(template.status));
    return Array.from(values).sort();
  }, [templatesQuery.data]);

  const handleSync = async () => {
    try {
      await syncTemplates.mutateAsync();
    } catch (error) {
      console.error(error);
    }
  };

  const resetFilters = () => {
    setLanguageFilter("");
    setStatusFilter("");
  };

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold">Templates</h1>
            <p className="text-muted-foreground mt-2">
              Consulte os templates sincronizados com os provedores WhatsApp e acompanhe status/aprovações.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={resetFilters} disabled={!languageFilter && !statusFilter}>
              Limpar filtros
            </Button>
            <Button onClick={handleSync} disabled={syncTemplates.isPending}>
              {syncTemplates.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Sincronizar provedores
            </Button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <label className="text-sm font-medium text-muted-foreground">Idioma</label>
            <Input
              value={languageFilter}
              onChange={(event) => setLanguageFilter(event.target.value)}
              placeholder="Ex.: pt_BR"
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Status</label>
            <Input
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              placeholder="approved, rejected, pending"
              className="mt-1"
            />
          </div>
          <Card>
            <CardHeader className="py-3">
              <CardTitle className="text-sm">Resumo</CardTitle>
              <CardDescription>Idiomas e status detectados entre os templates atuais.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase">Idiomas</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {languages.length === 0 ? (
                    <span className="text-sm text-muted-foreground">Nenhum idioma sincronizado</span>
                  ) : (
                    languages.map((language) => (
                      <Badge key={language} variant="secondary">
                        {language}
                      </Badge>
                    ))
                  )}
                </div>
              </div>
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase">Status</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  {statuses.length === 0 ? (
                    <span className="text-sm text-muted-foreground">Nenhum status disponível</span>
                  ) : (
                    statuses.map((status) => (
                      <Badge key={status} variant="outline">
                        {status}
                      </Badge>
                    ))
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {templatesQuery.isLoading ? (
          <div className="flex h-40 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (templatesQuery.data?.length ?? 0) === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-muted-foreground">
              Nenhum template encontrado. Inicie uma sincronização para importar do provedor.
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {templatesQuery.data!.map((template) => (
              <Card key={template.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-lg">{template.name}</CardTitle>
                      <CardDescription>{template.category}</CardDescription>
                    </div>
                    <Badge variant={template.status === "approved" ? "default" : "secondary"}>{template.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">Idioma:</span> {template.language}
                  </div>
                  {Object.keys(template.meta ?? {}).length > 0 && (
                    <div className="rounded-md border border-muted p-3 text-xs text-muted-foreground">
                      <pre className="whitespace-pre-wrap break-words">
                        {JSON.stringify(template.meta, null, 2)}
                      </pre>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </SimpleLayout>
  );
}
