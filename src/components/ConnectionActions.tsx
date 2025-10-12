import { Button } from "@/components/ui/button";
import { Loader2, Send, Settings2 } from "lucide-react";

interface ConnectionActionsProps {
  onTest?: () => void;
  onConfigure?: () => void;
  isTesting?: boolean;
  disableTest?: boolean;
  disableConfigure?: boolean;
  testLabel?: string;
  configureLabel?: string;
}

const ConnectionActions = ({
  onTest,
  onConfigure,
  isTesting = false,
  disableTest = false,
  disableConfigure = false,
  testLabel = "Testar conexão",
  configureLabel = "Reconfigurar",
}: ConnectionActionsProps) => {
  if (!onTest && !onConfigure) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {onTest && (
        <Button
          variant="outline"
          size="sm"
          onClick={onTest}
          disabled={disableTest || isTesting}
        >
          {isTesting ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Send className="mr-2 h-4 w-4" />
          )}
          {isTesting ? "Testando..." : testLabel}
        </Button>
      )}
      {onConfigure && (
        <Button
          variant="outline"
          size="sm"
          onClick={onConfigure}
          disabled={disableConfigure}
        >
          <Settings2 className="mr-2 h-4 w-4" />
          {configureLabel}
        </Button>
      )}
    </div>
  );
};

export default ConnectionActions;
