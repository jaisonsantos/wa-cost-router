import { useMemo } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  CalendarClock,
  Mail,
  Phone,
  ShieldCheck,
  User2,
  NotebookPen,
} from "lucide-react";
import SimpleLayout from "@/components/SimpleLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useContact, useContactConsentHistory } from "@/services/contacts";
import { Contact, ContactNote, ContactSegmentSummary, OptInStatus } from "@/types/api";

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
};

const statusVariant: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  active: "default",
  inactive: "secondary",
  archived: "outline",
  granted: "default",
  pending: "secondary",
  revoked: "destructive",
};

const getInitialContact = (state: unknown): Contact | undefined => {
  if (state && typeof state === "object" && "contact" in (state as Record<string, unknown>)) {
    const maybeContact = (state as { contact?: Contact }).contact;
    return maybeContact;
  }
  return undefined;
};

const normalizeSegments = (contact?: Contact): ContactSegmentSummary[] => {
  if (contact?.segments?.length) {
    return contact.segments;
  }

  const attributes = contact?.attributes as { segments?: unknown } | null | undefined;
  const rawSegments = attributes?.segments;
  if (!Array.isArray(rawSegments)) {
    return [];
  }

  return rawSegments
    .filter((segment): segment is Record<string, unknown> => Boolean(segment) && typeof segment === "object")
    .map((segment, index) => {
      const parsed = segment as {
        id?: unknown;
        name?: unknown;
        slug?: unknown;
        description?: unknown;
      };

      return {
        id: typeof parsed.id === "string" ? parsed.id : `attr-${index}`,
        name: typeof parsed.name === "string" ? parsed.name : "Segmento sem nome",
        slug: typeof parsed.slug === "string" ? parsed.slug : undefined,
        description: typeof parsed.description === "string" ? parsed.description : undefined,
      } satisfies ContactSegmentSummary;
    });
};

const normalizeNotes = (contact?: Contact): ContactNote[] => {
  if (contact?.notes?.length) {
    return contact.notes;
  }

  const attributes = contact?.attributes as { notes?: unknown } | null | undefined;
  const rawNotes = attributes?.notes;
  if (!Array.isArray(rawNotes)) {
    return [];
  }

  return rawNotes
    .filter((note): note is Record<string, unknown> => Boolean(note) && typeof note === "object")
    .map((note, index) => {
      const parsed = note as {
        id?: unknown;
        content?: unknown;
        author?: unknown;
        created_at?: unknown;
        updated_at?: unknown;
        visibility?: unknown;
        tags?: unknown;
      };

      const tags = Array.isArray(parsed.tags)
        ? parsed.tags.filter((tag): tag is string => typeof tag === "string")
        : undefined;

      return {
        id: typeof parsed.id === "string" ? parsed.id : `note-${index}`,
        content: typeof parsed.content === "string" ? parsed.content : JSON.stringify(note),
        author: typeof parsed.author === "string" ? parsed.author : "Sem autoria",
        created_at: typeof parsed.created_at === "string" ? parsed.created_at : new Date().toISOString(),
        updated_at: typeof parsed.updated_at === "string" ? parsed.updated_at : undefined,
        visibility: parsed.visibility === "shared" ? "shared" : "internal",
        tags,
      } satisfies ContactNote;
    });
};

const getDisplayName = (contact?: Contact) => {
  if (!contact) return "-";
  if (contact.full_name) return contact.full_name;
  if (contact.first_name || contact.last_name) {
    return [contact.first_name, contact.last_name].filter(Boolean).join(" ");
  }
  return contact.email || contact.phone || "Contato";
};

const getOptInLabel = (channel: string, status: OptInStatus, address: string) => {
  const normalizedChannel = channel.toUpperCase();
  return `${normalizedChannel} • ${status}${address ? ` (${address})` : ""}`;
};

export default function ContactDetailPage() {
  const navigate = useNavigate();
  const params = useParams<{ contactId: string }>();
  const location = useLocation();
  const contactId = params.contactId;
  const initialContact = getInitialContact(location.state);

  const {
    data: contact,
    isLoading: isContactLoading,
    error: contactError,
  } = useContact(contactId, initialContact);

  const {
    data: consentHistory,
    isLoading: isHistoryLoading,
    error: historyError,
  } = useContactConsentHistory(contactId);

  const segments = useMemo(() => normalizeSegments(contact), [contact]);
  const notes = useMemo(() => normalizeNotes(contact), [contact]);
  const optIns = contact?.channel_opt_ins ?? [];

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" onClick={() => navigate(-1)} className="gap-2">
            <ArrowLeft className="h-4 w-4" />
            Voltar
          </Button>
          <div className="flex flex-col">
            <h1 className="text-3xl font-bold">{getDisplayName(contact)}</h1>
            {contact && (
              <p className="text-sm text-muted-foreground">
                Criado em {formatDateTime(contact.created_at)} • Origem: {contact.source || "-"}
              </p>
            )}
          </div>
        </div>

        {contactError ? (
          <Card>
            <CardContent className="py-12 text-center text-destructive">
              Não foi possível carregar o contato: {contactError.message}
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <User2 className="h-5 w-5" />
                  Dados do contato
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isContactLoading && !contact ? (
                  <div className="space-y-3">
                    <Skeleton className="h-5 w-1/2" />
                    <Skeleton className="h-4 w-1/3" />
                    <Skeleton className="h-4 w-1/4" />
                  </div>
                ) : contact ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-3">
                      <div className="flex items-center gap-2 text-sm">
                        <Mail className="h-4 w-4 text-muted-foreground" />
                        <span>{contact.email ?? "-"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <Phone className="h-4 w-4 text-muted-foreground" />
                        <span>{contact.phone ?? "-"}</span>
                      </div>
                      <div className="flex items-center gap-2 text-sm">
                        <ShieldCheck className="h-4 w-4 text-muted-foreground" />
                        <Badge variant={statusVariant[contact.status] ?? "secondary"}>{contact.status}</Badge>
                      </div>
                      {contact.external_id && (
                        <div className="text-sm text-muted-foreground">ID externo: {contact.external_id}</div>
                      )}
                    </div>

                    <div className="space-y-3">
                      <div className="text-sm">
                        <span className="font-medium">Criado em:</span> {formatDateTime(contact.created_at)}
                      </div>
                      <div className="text-sm">
                        <span className="font-medium">Atualizado em:</span> {formatDateTime(contact.updated_at)}
                      </div>
                      {contact.proof_hash && (
                        <div className="text-sm break-all">
                          <span className="font-medium">Hash de prova:</span> {contact.proof_hash}
                        </div>
                      )}
                      {contact.source_metadata && (
                        <div className="text-sm">
                          <span className="font-medium">Metadados da origem:</span>
                          <pre className="mt-1 whitespace-pre-wrap break-all rounded-md bg-muted/60 p-2 text-xs">
                            {JSON.stringify(contact.source_metadata, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">Contato não encontrado.</div>
                )}

                <div className="mt-6 space-y-2">
                  <h3 className="text-sm font-semibold text-muted-foreground">Opt-ins ativos</h3>
                  <div className="flex flex-wrap gap-2">
                    {optIns.length ? (
                      optIns.map((optIn) => (
                        <Badge
                          key={`${optIn.channel}-${optIn.channel_address}-${optIn.version}`}
                          variant={statusVariant[optIn.status] ?? "secondary"}
                        >
                          {getOptInLabel(optIn.channel, optIn.status, optIn.channel_address)}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-xs text-muted-foreground">Nenhum opt-in registrado.</span>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CalendarClock className="h-5 w-5" />
                  Segmentos
                </CardTitle>
              </CardHeader>
              <CardContent>
                {isContactLoading && !contact ? (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-2/3" />
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-4 w-1/3" />
                  </div>
                ) : segments.length ? (
                  <div className="flex flex-col gap-3">
                    {segments.map((segment) => (
                      <div key={segment.id} className="rounded-md border p-3">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">{segment.name}</span>
                          {segment.slug && <Badge variant="outline">{segment.slug}</Badge>}
                        </div>
                        {segment.description && (
                          <p className="mt-1 text-sm text-muted-foreground">{segment.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Nenhum segmento associado.</p>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <NotebookPen className="h-5 w-5" />
                Notas
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isContactLoading && !contact ? (
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, index) => (
                    <Skeleton key={index} className="h-4 w-full" />
                  ))}
                </div>
              ) : notes.length ? (
                <ScrollArea className="h-64 pr-2">
                  <div className="space-y-4">
                    {notes.map((note) => (
                      <div key={note.id} className="rounded-md border p-3">
                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                          <span>{note.author}</span>
                          <span>{formatDateTime(note.created_at)}</span>
                        </div>
                        <p className="mt-2 text-sm whitespace-pre-wrap">{note.content}</p>
                        {note.tags?.length && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {note.tags.map((tag) => (
                              <Badge key={tag} variant="outline" className="text-xs">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhuma nota registrada para este contato.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Histórico de consentimento
              </CardTitle>
            </CardHeader>
            <CardContent>
              {historyError ? (
                <div className="py-6 text-sm text-destructive">
                  Erro ao carregar histórico: {historyError.message}
                </div>
              ) : isHistoryLoading ? (
                <div className="space-y-2">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <Skeleton key={index} className="h-4 w-full" />
                  ))}
                </div>
              ) : consentHistory?.items?.length ? (
                <ScrollArea className="h-64">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Data</TableHead>
                        <TableHead>Canal</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Agente</TableHead>
                        <TableHead className="text-right">Evidência</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {consentHistory.items.map((entry) => (
                        <TableRow key={entry.id}>
                          <TableCell>{formatDateTime(entry.recorded_at)}</TableCell>
                          <TableCell>
                            <div className="flex flex-col text-sm">
                              <span className="font-medium">{entry.channel.toUpperCase()}</span>
                              <span className="text-xs text-muted-foreground">{entry.channel_address}</span>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant={statusVariant[entry.status] ?? "secondary"}>{entry.status}</Badge>
                          </TableCell>
                          <TableCell>{entry.agent}</TableCell>
                          <TableCell className="text-right text-xs">
                            {entry.evidence_uri ? (
                              <a
                                href={entry.evidence_uri}
                                target="_blank"
                                rel="noreferrer"
                                className="text-primary underline-offset-2 hover:underline"
                              >
                                Ver evidência
                              </a>
                            ) : (
                              <span className="text-muted-foreground">-</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </ScrollArea>
              ) : (
                <p className="text-sm text-muted-foreground">Nenhum evento de consentimento registrado.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </SimpleLayout>
  );
}

