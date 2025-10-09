import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "./ui/button";
import {
  LayoutDashboard,
  FileText,
  Settings,
  Activity,
  LogOut,
  Satellite,
  MessageSquare,
  Users,
  Tags,
} from "lucide-react";

interface SimpleLayoutProps {
  children: React.ReactNode;
}

export default function SimpleLayout({ children }: SimpleLayoutProps) {
  const { logout } = useAuth();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold">WA Cost Router</h1>
            
            <nav className="flex items-center gap-2">
              <Button
                variant={location.pathname === "/dashboard" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/dashboard">
                  <LayoutDashboard className="h-4 w-4 mr-2" />
                  Dashboard
                </Link>
              </Button>
              <Button
                variant={location.pathname.startsWith("/contacts") ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/contacts">
                  <Users className="h-4 w-4 mr-2" />
                  Contatos
                </Link>
              </Button>
              <Button
                variant={location.pathname === "/segments" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/segments">
                  <Tags className="h-4 w-4 mr-2" />
                  Segmentos
                </Link>
              </Button>
              <Button
                variant={location.pathname === "/providers" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/providers">
                  <Satellite className="h-4 w-4 mr-2" />
                  Provedores
                </Link>
              </Button>
              <Button
                variant={location.pathname === "/messages" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/messages">
                  <MessageSquare className="h-4 w-4 mr-2" />
                  Mensagens
                </Link>
              </Button>
              <Button
                variant={location.pathname === "/rules" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/rules">
                  <Activity className="h-4 w-4 mr-2" />
                  Regras
                </Link>
              </Button>
              <Button
                variant={location.pathname === "/reports" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/reports">
                  <FileText className="h-4 w-4 mr-2" />
                  Relatórios
                </Link>
              </Button>
              <Button
                variant={location.pathname === "/settings" ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to="/settings">
                  <Settings className="h-4 w-4 mr-2" />
                  Configurações
                </Link>
              </Button>
              
              <Button
                variant="ghost"
                size="sm"
                onClick={logout}
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </nav>
          </div>
        </div>
      </header>
      
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>
    </div>
  );
}
