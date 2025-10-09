import { useState, type KeyboardEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SegmentTagsFieldProps {
  value: string[];
  onChange: (value: string[]) => void;
  disabled?: boolean;
  className?: string;
}

const normalizeTags = (tags: string[] = []) =>
  tags
    .map((tag) => tag.trim())
    .filter((tag, index, array) => Boolean(tag) && array.indexOf(tag) === index);

export const SegmentTagsField = ({ value, onChange, disabled = false, className }: SegmentTagsFieldProps) => {
  const [inputValue, setInputValue] = useState("");
  const tags = normalizeTags(Array.isArray(value) ? value : []);

  const addTag = (tag: string) => {
    const normalized = tag.trim();
    if (!normalized) return;
    if (tags.includes(normalized)) {
      setInputValue("");
      return;
    }
    onChange([...tags, normalized]);
    setInputValue("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addTag(inputValue);
    }
  };

  const removeTag = (tag: string) => {
    onChange(tags.filter((existing) => existing !== tag));
  };

  return (
    <Card className={cn("border-dashed", className)}>
      <CardHeader>
        <CardTitle className="text-base font-semibold">Tags estratégicas</CardTitle>
        <p className="text-sm text-muted-foreground">
          Use tags para alinhar o segmento com campanhas, jornadas ou squads responsáveis.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="segment-tag-input">Adicionar tag</Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              id="segment-tag-input"
              placeholder="Ex.: black_friday, ciclo_piloto"
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              onKeyDown={handleKeyDown}
              disabled={disabled}
            />
            <Button type="button" onClick={() => addTag(inputValue)} disabled={disabled || !inputValue.trim()}>
              Adicionar
            </Button>
          </div>
        </div>

        <Separator />

        {tags.length === 0 ? (
          <p className="text-sm text-muted-foreground">Nenhuma tag configurada até o momento.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <Badge key={tag} variant="secondary" className="flex items-center gap-1">
                <span>{tag}</span>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-4 w-4 text-muted-foreground hover:text-destructive"
                  onClick={() => removeTag(tag)}
                  disabled={disabled}
                  aria-label={`Remover tag ${tag}`}
                >
                  <X className="h-3 w-3" />
                </Button>
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default SegmentTagsField;
