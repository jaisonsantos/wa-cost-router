import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/contexts/AuthContext";
import { useSummary } from "@/hooks/useApi";
import { 
  BarChart3, 
  Settings, 
  MessageSquare, 
  TrendingDown, 
  Menu,
  X,
  Shield,
  Target,
  LogOut
} from "lucide-react";

interface LayoutProps {
  children: React.ReactNode;
  currentPage: string;
  onPageChange: (page: string) => void;
}

interface SummaryData {
  cost_7d_minor: number;
  saved_7d_minor: number;
  pct_saved: number;
}

const Layout = ({ children, currentPage, onPageChange }: LayoutProps) => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const { logout } = useAuth();
  const { data: summary } = useSummary() as { data: SummaryData | undefined };

  const navigation = [
    { name: "Dashboard", id: "dashboard", icon: BarChart3 },
    { name: "Regras", id: "rules", icon: Target },
    { name: "Relatórios", id: "reports", icon: TrendingDown },
    { name: "Configurações", id: "settings", icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted/20">
      {/* Mobile menu overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-300 ease-in-out
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 lg:static lg:inset-0
      `}>
        <Card className="h-full rounded-none border-r bg-card/50 backdrop-blur supports-[backdrop-filter]:bg-card/50">
          <div className="flex h-full flex-col">
            {/* Header */}
            <div className="flex h-14 items-center justify-between border-b px-4">
              <div className="flex items-center space-x-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary/80">
                  <MessageSquare className="h-4 w-4 text-primary-foreground" />
                </div>
                <div>
                  <h1 className="text-sm font-semibold">WA Cost Router</h1>
                  <Badge variant="secondary" className="h-4 text-xs">
                    Beta
                  </Badge>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="lg:hidden"
                onClick={() => setIsSidebarOpen(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-1 p-4">
              {navigation.map((item) => {
                const Icon = item.icon;
                const isActive = currentPage === item.id;
                
                return (
                  <Button
                    key={item.id}
                    variant={isActive ? "default" : "ghost"}
                    className={`w-full justify-start ${
                      isActive 
                        ? "bg-primary text-primary-foreground shadow-md" 
                        : "hover:bg-accent"
                    }`}
                    onClick={() => {
                      onPageChange(item.id);
                      setIsSidebarOpen(false);
                    }}
                  >
                    <Icon className="mr-2 h-4 w-4" />
                    {item.name}
                  </Button>
                );
              })}
            </nav>

            {/* Footer */}
            <div className="border-t p-4 space-y-2">
              <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                <Shield className="h-4 w-4" />
                <span>Dados seguros</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="w-full justify-start text-muted-foreground hover:text-destructive"
                onClick={logout}
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sair
              </Button>
            </div>
          </div>
        </Card>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 flex h-14 items-center border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4">
          <Button
            variant="ghost"
            size="sm"
            className="lg:hidden"
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu className="h-4 w-4" />
          </Button>
          
          <div className="flex flex-1 items-center justify-between">
            <h2 className="text-lg font-semibold capitalize">
              {navigation.find(nav => nav.id === currentPage)?.name || "Dashboard"}
            </h2>
            
            <div className="flex items-center space-x-2">
              {summary && (
                <Badge variant="outline" className="bg-success/10 text-success border-success/20">
                  €{((summary.saved_7d_minor || 0) / 100).toFixed(2)} economizados (7d)
                </Badge>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-6">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;