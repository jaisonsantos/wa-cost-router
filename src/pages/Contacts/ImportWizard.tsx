import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import SimpleLayout from "@/components/SimpleLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { toast } from "@/hooks/use-toast";
import { api, API_BASE_URL } from "@/lib/api";
import { ContactImportJob, ContactImportStatus } from "@/types/api";

const STEPS = [
  { key: 0, title: "Upload", description: "Envie o arquivo CSV" },
  { key: 1, title: "Mapeamento", description: "Associe as colunas" },
  { key: 2, title: "Pré-visualização", description: "Revise antes de importar" },
] as const;

type StepKey = (typeof STEPS)[number]["key"];

type FieldKey = "full_name" | "email" | "phone" | "external_id" | "status";

interface ImportFieldDefinition {
  key: FieldKey;
  label: string;
  required?: boolean;
  helper?: string;
}

const IMPORT_FIELDS: ImportFieldDefinition[] = [
  { key: "full_name", label: "Nome completo", required: true, helper: "Obrigatório" },
  { key: "email", label: "E-mail", helper: "Opcional, usado para opt-ins" },
  { key: "phone", label: "Telefone", helper: "Opcional, usado para opt-ins" },
  { key: "external_id", label: "ID externo", helper: "Opcional" },
  { key: "status", label: "Status", helper: "Opcional (active, inactive, archived)" },
];

type FieldMapping = Record<FieldKey, string | null>;

interface ParsedCsvResult {
  headers: string[];
  rows: Record<string, string>[];
}

const STATUS_LABELS: Record<ContactImportStatus, string> = {
  pending: "Pendente",
  validating: "Validando",
  processing: "Processando",
  completed: "Concluído",
  failed: "Falhou",
};

const STATUS_BADGE_VARIANT: Record<ContactImportStatus, "default" | "secondary" | "outline" | "destructive"> = {
  pending: "secondary",
  validating: "secondary",
  processing: "default",
  completed: "default",
  failed: "destructive",
};

const FINAL_STATUSES: ContactImportStatus[] = ["completed", "failed"];

const sanitizeHeader = (value: string) => value.replace(/^\ufeff/, "").trim();

const detectDelimiter = (headerLine: string) => {
  const commaCount = (headerLine.match(/,/g) ?? []).length;
  const semicolonCount = (headerLine.match(/;/g) ?? []).length;
  if (semicolonCount > commaCount) {
    return ";";
  }
  return ",";
};

const parseCsv = (content: string): ParsedCsvResult => {
  const firstLine = content.split(/\r?\n/)[0] ?? "";
  const delimiter = detectDelimiter(firstLine);

  const rows: string[][] = [];
  let currentField = "";
  let currentRow: string[] = [];
  let inQuotes = false;

  const pushField = () => {
    currentRow.push(currentField);
    currentField = "";
  };

  const pushRow = () => {
    if (currentRow.length > 0) {
      rows.push(currentRow);
    }
    currentRow = [];
  };

  for (let index = 0; index < content.length; index += 1) {
    const char = content[index];

    if (char === "\"" && content[index + 1] === "\"" && inQuotes) {
      currentField += "\"";
      index += 1;
      continue;
    }

    if (char === "\"") {
      inQuotes = !inQuotes;
      continue;
    }

    const isDelimiter = char === delimiter && !inQuotes;
    const isNewLine = (char === "\n" || char === "\r") && !inQuotes;

    if (isDelimiter) {
      pushField();
      continue;
    }

    if (isNewLine) {
      pushField();
      pushRow();
      if (char === "\r" && content[index + 1] === "\n") {
        index += 1;
      }
      continue;
    }

    currentField += char;
  }

  if (currentField.length > 0 || currentRow.length > 0) {
    pushField();
    pushRow();
  }

  if (!rows.length) {
    throw new Error("Arquivo CSV vazio ou inválido");
  }

  const rawHeaders = rows[0] ?? [];
  const headers = rawHeaders.map((header) => sanitizeHeader(header));
  const dataRows = rows.slice(1);

  const records = dataRows
    .map((values) => {
      const record: Record<string, string> = {};
      headers.forEach((header, index) => {
        record[header] = (values[index] ?? "").trim();
      });
      return record;
    })
    .filter((record) => Object.values(record).some((value) => value.trim().length > 0));

  return {
    headers,
    rows: records,
  };
};

const FIELD_SUGGESTIONS: Record<FieldKey, string[]> = {
  full_name: ["fullname", "full_name", "nomecompleto", "nome", "name"],
  email: ["email", "e-mail"],
  phone: ["telefone", "phone", "whatsapp", "msisdn"],
  external_id: ["externalid", "external_id", "idexterno", "id"],
  status: ["status", "lifecycle", "state"],
};

const normalizeComparison = (value: string | null | undefined) =>
  (value ?? "").toLowerCase().replace(/[^a-z0-9]/g, "");

const autoMapColumns = (headers: string[]): FieldMapping => {
  const mapping: FieldMapping = {
    full_name: null,
    email: null,
    phone: null,
    external_id: null,
    status: null,
  };

  const used = new Set<string>();
  headers.forEach((header) => {
    const normalized = normalizeComparison(header);
    (Object.entries(FIELD_SUGGESTIONS) as [FieldKey, string[]][]).forEach(([field, hints]) => {
      if (mapping[field] || used.has(header)) {
        return;
      }
      const hasMatch = hints.some((hint) => hint === normalized);
      if (hasMatch) {
        mapping[field] = header;
        used.add(header);
      }
    });
  });

  if (!mapping.full_name) {
    const fallback = headers.find((header) => normalizeComparison(header).includes("nome")) ?? null;
    mapping.full_name = fallback;
  }

  return mapping;
};

const escapeCsvValue = (value: string) => {
  if (value === null || value === undefined) return "";
  const needsQuote = /[",\n\r;]/.test(value);
  const escaped = value.replace(/"/g, '""');
  return needsQuote ? `"${escaped}"` : escaped;
};

const buildWebsocketUrl = (jobId: string, token?: string | null) => {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  const baseWithSlash = wsBase.endsWith("/") ? wsBase : `${wsBase}/`;
  const url = new URL(`ws/contact-imports/${jobId}`, baseWithSlash);
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
};

const ImportWizard = () => {
  const [step, setStep] = useState<StepKey>(0);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [mapping, setMapping] = useState<FieldMapping>({
    full_name: null,
    email: null,
    phone: null,
    external_id: null,
    status: null,
  });
  const [parseError, setParseError] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [websocketFailed, setWebsocketFailed] = useState(false);
  const websocketRef = useRef<WebSocket | null>(null);
  const lastStatusRef = useRef<ContactImportStatus | null>(null);

  const queryClient = useQueryClient();

  const selectedFields = useMemo(
    () => IMPORT_FIELDS.filter((field) => field.required || mapping[field.key]),
    [mapping],
  );

  const normalizedRows = useMemo(() => {
    if (!rows.length) {
      return [] as Record<FieldKey, string>[];
    }

    return rows.map((row) => {
      const normalized: Record<FieldKey, string> = {
        full_name: "",
        email: "",
        phone: "",
        external_id: "",
        status: "",
      };
      selectedFields.forEach((field) => {
        const column = mapping[field.key];
        normalized[field.key] = column ? row[column] ?? "" : "";
      });
      return normalized;
    });
  }, [rows, mapping, selectedFields]);

  const previewRows = useMemo(() => normalizedRows.slice(0, 5), [normalizedRows]);

  const { data: job, error: jobError } = useQuery<ContactImportJob, Error>({
    queryKey: ["contact-import-job", activeJobId],
    queryFn: () => api.getContactImportJob(activeJobId as string),
    enabled: Boolean(activeJobId),
    refetchInterval: (data) => {
      if (!data) return 4000;
      return FINAL_STATUSES.includes(data.status) ? false : 4000;
    },
  });

  const createImportMutation = useMutation<ContactImportJob, Error, File>({
    mutationFn: (file) => api.createContactImport(file),
    onSuccess: (createdJob) => {
      queryClient.setQueryData(["contact-import-job", createdJob.id], createdJob);
      setActiveJobId(createdJob.id);
      setStep(2);
      toast({
        title: "Importação iniciada",
        description: "Estamos processando os contatos. Você pode acompanhar o status abaixo.",
      });
    },
    onError: (error) => {
      toast({
        title: "Erro ao iniciar importação",
        description: error.message,
        variant: "destructive",
      });
    },
  });

  useEffect(() => {
    if (!activeJobId) {
      return undefined;
    }

    const token = localStorage.getItem("token");
    let socket: WebSocket | null = null;

    try {
      const url = buildWebsocketUrl(activeJobId, token);
      socket = new WebSocket(url);
      websocketRef.current = socket;
    } catch (error) {
      setWebsocketFailed(true);
      return undefined;
    }

    socket.onopen = () => {
      setWebsocketFailed(false);
    };

    socket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as ContactImportJob;
        queryClient.setQueryData(["contact-import-job", payload.id], payload);
      } catch (err) {
        // Ignore malformed payloads
      }
    };

    socket.onerror = () => {
      setWebsocketFailed(true);
    };

    socket.onclose = () => {
      websocketRef.current = null;
    };

    return () => {
      socket?.close();
    };
  }, [activeJobId, queryClient]);

  useEffect(() => {
    if (!job || !websocketRef.current) {
      return;
    }

    if (FINAL_STATUSES.includes(job.status)) {
      websocketRef.current.close();
      websocketRef.current = null;
    }
  }, [job]);

  useEffect(() => {
    if (!job) {
      return;
    }

    if (job.status !== lastStatusRef.current && FINAL_STATUSES.includes(job.status)) {
      if (job.status === "completed") {
        const message = job.error_rows
          ? `${job.processed_rows} contatos importados com ${job.error_rows} erros.`
          : `${job.processed_rows} contatos importados com sucesso.`;
        toast({ title: "Importação concluída", description: message });
      }

      if (job.status === "failed") {
        toast({
          title: "Importação falhou",
          description: "Revise o relatório de erros para mais detalhes.",
          variant: "destructive",
        });
      }
    }

    lastStatusRef.current = job.status;
  }, [job]);

  const resetWizard = () => {
    setStep(0);
    setUploadedFile(null);
    setHeaders([]);
    setRows([]);
    setMapping({
      full_name: null,
      email: null,
      phone: null,
      external_id: null,
      status: null,
    });
    setParseError(null);
    setActiveJobId(null);
    setWebsocketFailed(false);
    queryClient.removeQueries({ queryKey: ["contact-import-job"] });
    websocketRef.current?.close();
    websocketRef.current = null;
  };

  const handleFileChange: React.ChangeEventHandler<HTMLInputElement> = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setIsParsing(true);
    setParseError(null);
    try {
      const content = await file.text();
      const parsed = parseCsv(content);
      if (!parsed.rows.length) {
        throw new Error("Nenhum dado encontrado no arquivo");
      }
      setUploadedFile(file);
      setHeaders(parsed.headers);
      setRows(parsed.rows);
      setMapping(autoMapColumns(parsed.headers));
      setStep(1);
      setActiveJobId(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha ao ler o arquivo";
      setParseError(message);
      setUploadedFile(null);
      setHeaders([]);
      setRows([]);
    } finally {
      setIsParsing(false);
      event.target.value = "";
    }
  };

  const handleMappingChange = (field: FieldKey, column: string | null) => {
    setMapping((current) => {
      const updated: FieldMapping = { ...current };
      Object.entries(updated).forEach(([key, value]) => {
        if (key !== field && value === column) {
          updated[key as FieldKey] = null;
        }
      });
      updated[field] = column;
      return updated;
    });
  };

  const handleGenerateImport = async () => {
    if (!uploadedFile) {
      toast({ title: "Selecione um arquivo", variant: "destructive" });
      return;
    }

    if (!mapping.full_name) {
      toast({
        title: "Mapeamento obrigatório",
        description: "Associe a coluna de nome completo antes de continuar.",
        variant: "destructive",
      });
      return;
    }

    const fieldsToExport = IMPORT_FIELDS.filter((field) => field.required || mapping[field.key]).map(
      (field) => field.key,
    );

    const csvHeader = fieldsToExport.join(",");
    const csvRows = normalizedRows.map((row) =>
      fieldsToExport.map((field) => escapeCsvValue(row[field] ?? "")).join(","),
    );

    const csvContent = [csvHeader, ...csvRows].join("\n");
    const normalizedFileName = uploadedFile.name.endsWith(".csv")
      ? uploadedFile.name.replace(/\.csv$/i, "_normalized.csv")
      : `${uploadedFile.name}_normalized.csv`;

    const normalizedFile = new File([csvContent], normalizedFileName, { type: "text/csv" });
    createImportMutation.mutate(normalizedFile);
  };

  const progressValue = useMemo(() => {
    if (!job) return 0;
    if (job.total_rows > 0) {
      return Math.min(100, Math.round((job.processed_rows / job.total_rows) * 100));
    }
    if (job.status === "completed") return 100;
    if (job.status === "failed") return 0;
    if (job.status === "processing") return 60;
    if (job.status === "validating") return 30;
    return 10;
  }, [job]);

  const mappingIsValid = Boolean(mapping.full_name);
  const canPreview = mappingIsValid && rows.length > 0;

  const showNoContactWarning = !mapping.email && !mapping.phone;

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <h1 className="text-3xl font-bold">Importar contatos</h1>
              <p className="text-muted-foreground">
                Execute a importação multi-tenant com validação de consentimento e relatório de erros.
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" asChild>
                <Link to="/contacts">Voltar para contatos</Link>
              </Button>
              {FINAL_STATUSES.includes(job?.status ?? "pending") && (
                <Button variant="secondary" onClick={resetWizard}>
                  Nova importação
                </Button>
              )}
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {STEPS.map((item, index) => {
              const isActive = step === item.key;
              const isCompleted = step > item.key;
              return (
                <Card key={item.key} className={isActive ? "border-primary" : undefined}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between text-sm text-muted-foreground">
                      <span>Etapa {index + 1}</span>
                      {isCompleted ? <Badge variant="default">Concluída</Badge> : null}
                    </div>
                    <CardTitle className="text-lg">{item.title}</CardTitle>
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  </CardHeader>
                </Card>
              );
            })}
          </div>
        </div>

        {step === 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Upload do arquivo</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Utilize um arquivo CSV com colunas de nome, contato principal e status. A primeira linha deve conter os cabeçalhos.
              </p>
              <div className="space-y-2">
                <Label htmlFor="contacts-file">Arquivo CSV</Label>
                <Input
                  id="contacts-file"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={handleFileChange}
                  disabled={isParsing}
                />
              </div>
              {uploadedFile && (
                <div className="rounded-md border border-dashed p-4 text-sm">
                  <p className="font-medium">{uploadedFile.name}</p>
                  <p className="text-muted-foreground">{rows.length} linhas detectadas</p>
                </div>
              )}
              {parseError && (
                <Alert variant="destructive">
                  <AlertTitle>Não foi possível ler o arquivo</AlertTitle>
                  <AlertDescription>{parseError}</AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        )}

        {step === 1 && (
          <Card>
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Mapeamento de colunas</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Associe as colunas do seu arquivo aos campos suportados pela plataforma.
                </p>
              </div>
              <Button variant="outline" onClick={() => setStep(0)}>
                Trocar arquivo
              </Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-md border p-4 text-sm">
                <p>
                  <span className="font-medium">Arquivo:</span> {uploadedFile?.name}
                </p>
                <p className="text-muted-foreground">{headers.length} colunas detectadas</p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                {IMPORT_FIELDS.map((field) => {
                  const selectedColumn = mapping[field.key];
                  const sampleValue = selectedColumn ? rows[0]?.[selectedColumn] ?? "-" : "-";
                  const selectValue = selectedColumn ?? (field.required ? undefined : "__none__");
                  return (
                    <div key={field.key} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>{field.label}</Label>
                        {field.required && <Badge variant="outline">Obrigatório</Badge>}
                      </div>
                      <Select
                        value={selectValue}
                        onValueChange={(value) =>
                          handleMappingChange(field.key, value === "__none__" ? null : value)
                        }
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="Selecione uma coluna" />
                        </SelectTrigger>
                        <SelectContent>
                          {!field.required && (
                            <SelectItem value="__none__">Não utilizar</SelectItem>
                          )}
                          {headers.map((header) => (
                            <SelectItem key={header} value={header}>
                              {header}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {field.helper && (
                        <p className="text-xs text-muted-foreground">{field.helper}</p>
                      )}
                      <p className="text-xs text-muted-foreground">Exemplo: {sampleValue || "-"}</p>
                    </div>
                  );
                })}
              </div>

              {showNoContactWarning && (
                <Alert>
                  <AlertTitle>Recomendação</AlertTitle>
                  <AlertDescription>
                    Informe ao menos uma coluna de e-mail ou telefone para manter o rastreamento de opt-in atualizado.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(0)}>
                Voltar
              </Button>
              <Button onClick={() => setStep(2)} disabled={!canPreview}>
                Avançar para pré-visualização
              </Button>
            </CardFooter>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Pré-visualização</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Revise um recorte dos dados antes de confirmar a importação.
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setStep(1)}>
                  Ajustar mapeamento
                </Button>
                <Button variant="outline" onClick={() => setStep(0)}>
                  Trocar arquivo
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-md border p-4 text-sm">
                <p>
                  <span className="font-medium">Arquivo:</span> {uploadedFile?.name}
                </p>
                <p className="text-muted-foreground">Total de linhas: {normalizedRows.length}</p>
              </div>

              {previewRows.length ? (
                <div className="space-y-4">
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          {selectedFields.map((field) => (
                            <TableHead key={field.key}>{field.label}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {previewRows.map((row, rowIndex) => (
                          <TableRow key={`preview-${rowIndex}`}>
                            {selectedFields.map((field) => (
                              <TableCell key={`${field.key}-${rowIndex}`} className="text-sm">
                                {row[field.key] || <span className="text-muted-foreground">-</span>}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Mostrando {previewRows.length} de {normalizedRows.length} registros.
                  </p>
                </div>
              ) : (
                <Alert>
                  <AlertTitle>Nenhum dado encontrado</AlertTitle>
                  <AlertDescription>
                    Ajuste o mapeamento ou carregue um novo arquivo para visualizar os dados.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter className="flex flex-col items-stretch gap-2 sm:flex-row sm:items-center sm:justify-between">
              <Button variant="outline" onClick={() => setStep(1)}>
                Voltar ao mapeamento
              </Button>
              <Button
                onClick={handleGenerateImport}
                disabled={createImportMutation.isPending || !normalizedRows.length || !mappingIsValid}
              >
                {createImportMutation.isPending ? "Iniciando importação..." : "Confirmar importação"}
              </Button>
            </CardFooter>
          </Card>
        )}

        {jobError && (
          <Alert variant="destructive">
            <AlertTitle>Falha ao obter status</AlertTitle>
            <AlertDescription>{jobError.message}</AlertDescription>
          </Alert>
        )}

        {activeJobId && (
          <Card>
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>Status da importação</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Monitoramento contínuo do job #{activeJobId}.
                </p>
              </div>
              {job && <Badge variant={STATUS_BADGE_VARIANT[job.status]}>{STATUS_LABELS[job.status]}</Badge>}
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <Progress value={progressValue} className="h-2" />
                <div className="mt-2 flex flex-wrap items-center justify-between text-sm text-muted-foreground">
                  <span>
                    {job?.processed_rows ?? 0} de {job?.total_rows ?? 0} linhas processadas
                  </span>
                  <span>{job?.error_rows ?? 0} erros</span>
                </div>
              </div>

              <Separator />

              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded-md border p-4 text-sm">
                  <p className="font-medium">Início</p>
                  <p className="text-muted-foreground">
                    {job?.started_at ? new Date(job.started_at).toLocaleString() : "Aguardando processamento"}
                  </p>
                </div>
                <div className="rounded-md border p-4 text-sm">
                  <p className="font-medium">Conclusão</p>
                  <p className="text-muted-foreground">
                    {job?.completed_at ? new Date(job.completed_at).toLocaleString() : "Em andamento"}
                  </p>
                </div>
              </div>

              {job?.error_rows ? (
                <Alert variant="destructive">
                  <AlertTitle>Erros encontrados</AlertTitle>
                  <AlertDescription>
                    {job.error_rows} linhas apresentaram problemas de validação. Faça o download do relatório para revisar.
                  </AlertDescription>
                </Alert>
              ) : null}

              {websocketFailed && (
                <Alert>
                  <AlertTitle>Atualizações em modo polling</AlertTitle>
                  <AlertDescription>
                    Não foi possível estabelecer conexão WebSocket. O status será atualizado a cada poucos segundos.
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
            <CardFooter className="flex flex-wrap gap-2">
              <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ["contact-import-job", activeJobId] })}>
                Atualizar status
              </Button>
              {job?.error_report_uri && (
                <Button asChild variant="secondary">
                  <a
                    href={job.error_report_uri}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Baixar relatório de erros
                  </a>
                </Button>
              )}
            </CardFooter>
          </Card>
        )}
      </div>
    </SimpleLayout>
  );
};

export default ImportWizard;
