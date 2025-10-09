import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import SimpleLayout from "@/components/SimpleLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useContactList } from "@/services/contacts";
import { Contact, ContactStatus, OptInStatus } from "@/types/api";

const PAGE_SIZE = 25;

const statusOptions: { value: "all" | ContactStatus; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "active", label: "Ativo" },
  { value: "inactive", label: "Inativo" },
  { value: "archived", label: "Arquivado" },
];

const channelOptions: { value: string; label: string }[] = [
  { value: "all", label: "Todos os canais" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "sms", label: "SMS" },
  { value: "email", label: "E-mail" },
];

const optInStatusOptions: { value: "all" | OptInStatus; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "granted", label: "Concedido" },
  { value: "pending", label: "Pendente" },
  { value: "revoked", label: "Revogado" },
];

const statusVariant: Record<ContactStatus, "default" | "secondary" | "outline"> = {
  active: "default",
  inactive: "secondary",
  archived: "outline",
};

const optInVariant: Record<OptInStatus, "default" | "secondary" | "destructive"> = {
  granted: "default",
  pending: "secondary",
  revoked: "destructive",
};

const getDisplayName = (contact: Contact) => {
  if (contact.full_name) return contact.full_name;
  if (contact.first_name || contact.last_name) {
    return [contact.first_name, contact.last_name].filter(Boolean).join(" ");
  }
  return contact.email || contact.phone || "Contato sem nome";
};

const getOptInLabel = (optIn: { channel: string; status: OptInStatus; channel_address: string }) => {
  const channelName = optIn.channel.toUpperCase();
  return `${channelName} • ${optIn.status}`;
};

export default function ContactListPage() {
  const [statusFilter, setStatusFilter] = useState<"all" | ContactStatus>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");
  const [optInFilter, setOptInFilter] = useState<"all" | OptInStatus>("all");
  const [channelAddress, setChannelAddress] = useState("");
  const [page, setPage] = useState(0);

  useEffect(() => {
    setPage(0);
  }, [statusFilter, channelFilter, optInFilter, channelAddress]);

  const filters = useMemo(
    () => ({
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      status: statusFilter === "all" ? undefined : statusFilter,
      channel: channelFilter === "all" ? undefined : channelFilter,
      optInStatus: optInFilter === "all" ? undefined : [optInFilter],
      channelAddress: channelAddress.trim() ? channelAddress.trim() : undefined,
    }),
    [statusFilter, channelFilter, optInFilter, channelAddress, page],
  );

  const { data, isLoading, isFetching, error } = useContactList(filters);

  const contacts = data?.items ?? [];
  const totalCount = data?.count ?? 0;
  const totalPages = totalCount > 0 ? Math.ceil(totalCount / PAGE_SIZE) : page + (contacts.length === PAGE_SIZE ? 2 : 1);
  const isFirstPage = page === 0;
  const isLastPage = totalPages ? page >= totalPages - 1 : contacts.length < PAGE_SIZE;

  const handlePrevious = () => {
    setPage((current) => Math.max(current - 1, 0));
  };

  const handleNext = () => {
    if (!isLastPage || contacts.length === PAGE_SIZE) {
      setPage((current) => current + 1);
    }
  };

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div className="flex flex-col gap-2">
          <div>
            <h1 className="text-3xl font-bold">Contatos</h1>
            <p className="text-muted-foreground">Catálogo multi-tenant com status de opt-in por canal</p>
          </div>
        </div>

        <Card>
          <CardHeader className="pb-4">
            <CardTitle>Filtros</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <div className="space-y-2">
              <Label>Status</Label>
              <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as typeof statusFilter)}>
                <SelectTrigger>
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Canal</Label>
              <Select value={channelFilter} onValueChange={setChannelFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Canal" />
                </SelectTrigger>
                <SelectContent>
                  {channelOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Status do opt-in</Label>
              <Select value={optInFilter} onValueChange={(value) => setOptInFilter(value as typeof optInFilter)}>
                <SelectTrigger>
                  <SelectValue placeholder="Status do opt-in" />
                </SelectTrigger>
                <SelectContent>
                  {optInStatusOptions.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Endereço do canal</Label>
              <Input
                placeholder="+55 11 99999-9999"
                value={channelAddress}
                onChange={(event) => setChannelAddress(event.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Catálogo</CardTitle>
              <p className="text-sm text-muted-foreground">
                {isFetching ? "Atualizando lista..." : `Mostrando ${contacts.length} de ${totalCount || contacts.length} contatos`}
              </p>
            </div>
            <Button variant="outline" onClick={() => setPage(0)} disabled={isFetching}>
              Recarregar
            </Button>
          </CardHeader>
          <CardContent>
            {error ? (
              <div className="flex h-48 items-center justify-center text-destructive">
                Falha ao carregar contatos: {error.message}
              </div>
            ) : isLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 5 }).map((_, index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              </div>
            ) : contacts.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center text-muted-foreground">
                <p className="font-medium">Nenhum contato encontrado com os filtros atuais.</p>
                <Button variant="link" className="mt-2" onClick={() => {
                  setStatusFilter("all");
                  setChannelFilter("all");
                  setOptInFilter("all");
                  setChannelAddress("");
                }}>
                  Limpar filtros
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Contato</TableHead>
                      <TableHead>Contato principal</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Opt-ins</TableHead>
                      <TableHead className="text-right">Ações</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {contacts.map((contact) => (
                      <TableRow key={contact.id}>
                        <TableCell>
                          <div className="flex flex-col">
                            <span className="font-medium">{getDisplayName(contact)}</span>
                            {contact.external_id && (
                              <span className="text-xs text-muted-foreground">ID externo: {contact.external_id}</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col text-sm">
                            {contact.email && <span>{contact.email}</span>}
                            {contact.phone && <span className="text-muted-foreground">{contact.phone}</span>}
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusVariant[contact.status] ?? "secondary"}>{contact.status}</Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-2">
                            {contact.channel_opt_ins?.length ? (
                              contact.channel_opt_ins.map((optIn) => (
                                <Badge key={`${optIn.channel}-${optIn.channel_address}-${optIn.version}`} variant={optInVariant[optIn.status] ?? "secondary"}>
                                  {getOptInLabel(optIn)}
                                </Badge>
                              ))
                            ) : (
                              <span className="text-xs text-muted-foreground">Sem opt-ins registrados</span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button asChild variant="ghost" size="sm">
                            <Link to={`/contacts/${contact.id}`} state={{ contact }}>
                              Ver detalhes
                            </Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        href="#"
                        onClick={(event) => {
                          event.preventDefault();
                          if (!isFirstPage) handlePrevious();
                        }}
                        className={isFirstPage ? "pointer-events-none opacity-50" : ""}
                      />
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationLink href="#" isActive>
                        Página {page + 1}
                      </PaginationLink>
                    </PaginationItem>
                    <PaginationItem>
                      <PaginationNext
                        href="#"
                        onClick={(event) => {
                          event.preventDefault();
                          if (!isLastPage) handleNext();
                        }}
                        className={isLastPage && contacts.length < PAGE_SIZE ? "pointer-events-none opacity-50" : ""}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </SimpleLayout>
  );
}

