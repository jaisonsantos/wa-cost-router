import { useMemo, useState } from "react";
import SimpleLayout from "@/components/SimpleLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  useContactSegments,
  useCreateContactSegment,
  useUpdateContactSegment,
  useDeleteContactSegment,
} from "@/hooks/useApi";
import {
  ContactSegment,
  SegmentAttributeRule,
  SegmentCriteria,
  SegmentBehaviorRule,
} from "@/types/api";
import { SegmentFormDialog, SegmentFormValues } from "@/components/segments";
import { format } from "date-fns";
import { Plus, Pencil, Trash2, Tags, Filter } from "lucide-react";

const formatDate = (value?: string) => {
  if (!value) return "";
  try {
    return format(new Date(value), "dd/MM/yyyy HH:mm");
  } catch (error) {
    return value;
  }
};

const hasAttributeRules = (attributes?: SegmentAttributeRule[] | null) =>
  Array.isArray(attributes) && attributes.length > 0;

const buildCriteria = (values: SegmentFormValues): SegmentCriteria | undefined => {
  const criteria: SegmentCriteria = {};
  if (values.attributes.length) {
    criteria.attributes = values.attributes;
  }
  if (values.tags.length) {
    criteria.tags = values.tags;
  }
  criteria.behavior = values.behavior as SegmentBehaviorRule;

  return Object.keys(criteria).length ? criteria : undefined;
};

const buildDescription = (description?: string) => {
  const trimmed = description?.trim();
  return trimmed && trimmed.length > 0 ? trimmed : undefined;
};

const Segments = () => {
  const { data, isLoading } = useContactSegments();
  const createSegment = useCreateContactSegment();
  const updateSegment = useUpdateContactSegment();
  const deleteSegment = useDeleteContactSegment();

  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingSegment, setEditingSegment] = useState<ContactSegment | null>(null);
  const [segmentToDelete, setSegmentToDelete] = useState<ContactSegment | null>(null);

  const segments = useMemo(() => data?.items ?? [], [data]);
  const isSubmitting = createSegment.isPending || updateSegment.isPending;
  const isDeleting = deleteSegment.isPending;

  const handleOpenCreate = () => {
    setEditingSegment(null);
    setIsDialogOpen(true);
  };

  const handleOpenEdit = (segment: ContactSegment) => {
    setEditingSegment(segment);
    setIsDialogOpen(true);
  };

  const handleDialogChange = (open: boolean) => {
    setIsDialogOpen(open);
    if (!open) {
      setEditingSegment(null);
    }
  };

  const handleSubmit = async (values: SegmentFormValues) => {
    const criteria = buildCriteria(values);
    const payload = {
      name: values.name,
      slug: values.slug,
      description: buildDescription(values.description),
      criteria,
    };

    if (editingSegment) {
      await updateSegment.mutateAsync({
        segmentId: editingSegment.id,
        updates: payload,
      });
    } else {
      await createSegment.mutateAsync(payload);
    }

    setIsDialogOpen(false);
    setEditingSegment(null);
  };

  const handleDelete = async () => {
    if (!segmentToDelete) return;
    await deleteSegment.mutateAsync(segmentToDelete.id);
    setSegmentToDelete(null);
  };

  return (
    <SimpleLayout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Segmentos de contatos</h1>
            <p className="text-sm text-muted-foreground">
              Organize sua base em clusters reutilizáveis para campanhas, roteamento e governança de opt-in.
            </p>
          </div>
          <Button onClick={handleOpenCreate}>
            <Plus className="mr-2 h-4 w-4" />
            Novo segmento
          </Button>
        </div>

        {isLoading ? (
          <div className="grid gap-4 md:grid-cols-2">
            {[...Array(4)].map((_, index) => (
              <Skeleton key={index} className="h-48 w-full" />
            ))}
          </div>
        ) : segments.length === 0 ? (
          <Card className="border-dashed">
            <CardHeader>
              <CardTitle>Nenhum segmento cadastrado</CardTitle>
              <CardDescription>
                Crie seu primeiro segmento para agrupar contatos por atributos, tags de campanhas ou políticas especiais.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={handleOpenCreate} variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                Começar agora
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {segments.map((segment) => {
              const attributes = segment.criteria?.attributes as SegmentAttributeRule[] | undefined;
              const tags = segment.criteria?.tags as string[] | undefined;

              return (
                <Card key={segment.id} className="h-full">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <CardTitle className="flex items-center gap-2 text-lg">
                          {segment.name}
                          <Badge variant="outline">{segment.slug}</Badge>
                        </CardTitle>
                        {segment.description && (
                          <CardDescription className="mt-1 text-sm text-muted-foreground">
                            {segment.description}
                          </CardDescription>
                        )}
                        <p className="mt-2 text-xs text-muted-foreground">
                          Atualizado em {formatDate(segment.updated_at)}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="ghost" size="icon" onClick={() => handleOpenEdit(segment)} aria-label="Editar segmento">
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-destructive hover:text-destructive"
                          onClick={() => setSegmentToDelete(segment)}
                          aria-label="Remover segmento"
                          disabled={isDeleting}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4 text-sm">
                    <div className="flex items-start gap-2">
                      <Tags className="mt-1 h-4 w-4 text-muted-foreground" />
                      <div>
                        <p className="font-medium">Tags</p>
                        {tags?.length ? (
                          <div className="mt-1 flex flex-wrap gap-2">
                            {tags.map((tag) => (
                              <Badge key={tag} variant="secondary">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        ) : (
                          <p className="text-muted-foreground">Nenhuma tag associada.</p>
                        )}
                      </div>
                    </div>

                    <div className="flex items-start gap-2">
                      <Filter className="mt-1 h-4 w-4 text-muted-foreground" />
                      <div className="flex-1">
                        <p className="font-medium">Critérios de atributos</p>
                        {hasAttributeRules(attributes) ? (
                          <ul className="mt-2 space-y-1">
                            {attributes!.map((rule, index) => (
                              <li key={`${segment.id}-rule-${index}`} className="text-muted-foreground">
                                <span className="font-medium">{rule.key}</span> {rule.operator.replace("_", " ")} {rule.values.join(", ")}
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <p className="text-muted-foreground">Sem filtros configurados.</p>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      <SegmentFormDialog
        open={isDialogOpen}
        onOpenChange={handleDialogChange}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
        segment={editingSegment}
      />

      <AlertDialog
        open={Boolean(segmentToDelete)}
        onOpenChange={(open) => {
          if (!open && !isDeleting) {
            setSegmentToDelete(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirmar exclusão</AlertDialogTitle>
            <AlertDialogDescription>
              Remover o segmento "{segmentToDelete?.name}"? Contatos deixarão de receber regras associadas a ele.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setSegmentToDelete(null)} disabled={isDeleting}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              disabled={isDeleting}
            >
              {isDeleting ? "Removendo..." : "Remover segmento"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SimpleLayout>
  );
};

export default Segments;
