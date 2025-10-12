import type { ComponentType, ReactNode, SVGProps } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "./ui/button";
import { Sheet, SheetClose, SheetContent, SheetTrigger } from "./ui/sheet";
import {
  LayoutDashboard,
  FileSpreadsheet,
  FileText,
  Settings,
  Activity,
  LogOut,
  Satellite,
  MessageSquare,
  Users,
  Tags,
  Menu,
} from "lucide-react";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
  match?: "exact" | "startsWith";
}

const navItems: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/contacts", label: "Contatos", icon: Users, match: "startsWith" },
  { to: "/segments", label: "Segmentos", icon: Tags },
  { to: "/providers", label: "Provedores", icon: Satellite },
  { to: "/messages", label: "Mensagens", icon: MessageSquare },
  { to: "/rules", label: "Regras", icon: Activity },
  { to: "/reports", label: "Relatórios", icon: FileText },
  { to: "/settings", label: "Configurações", icon: Settings },
];

const isActiveRoute = (pathname: string, item: NavItem) => {
  if (item.match === "startsWith") {
    return pathname.startsWith(item.to);
  }

  return pathname === item.to;
};

interface SimpleLayoutProps {
  children: ReactNode;
}

export default function SimpleLayout({ children }: SimpleLayoutProps) {
  const { logout } = useAuth();
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="container mx-auto px-4 sm:px-6 md:px-8 py-3 md:py-4">
          <div className="flex flex-wrap items-center justify-between gap-3 md:flex-nowrap md:gap-4">
            <div className="flex w-full items-center justify-between gap-3 md:w-auto">
              <h1 className="text-lg font-bold whitespace-nowrap sm:text-xl">WA Cost Router</h1>

              <div className="md:hidden">
                <Sheet>
                  <SheetTrigger asChild>
                    <Button variant="outline" size="icon" aria-label="Abrir menu">
                      <Menu className="h-5 w-5" />
                    </Button>
                  </SheetTrigger>
                  <SheetContent side="left" className="flex w-72 flex-col gap-4 sm:w-80">
                    <div>
                      <h2 className="text-lg font-semibold">Navegação</h2>
                      <p className="text-sm text-muted-foreground">
                        Acesse rapidamente as principais áreas
                      </p>
                    </div>
                    <nav className="flex flex-col gap-2">
                      {navItems.map((item) => {
                        const Icon = item.icon;
                        const isActive = isActiveRoute(location.pathname, item);

                        return (
                          <SheetClose asChild key={item.to}>
                            <Button
                              variant={isActive ? "default" : "ghost"}
                              size="sm"
                              className="justify-start"
                              asChild
                            >
                              <Link to={item.to}>
                                <Icon className="mr-2 h-4 w-4" />
                                {item.label}
                              </Link>
                            </Button>
                          </SheetClose>
                        );
                      })}
                      <SheetClose asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="justify-start"
                          onClick={logout}
                        >
                          <LogOut className="mr-2 h-4 w-4" />
                          Sair
                        </Button>
                      </SheetClose>
                    </nav>
                  </SheetContent>
                </Sheet>
              </div>
            </div>

            <nav className="hidden w-full overflow-x-auto md:flex md:w-auto md:items-center md:justify-end md:gap-2 lg:gap-3">
              {navItems.map((item) => {
                const Icon = item.icon;
                const isActive = isActiveRoute(location.pathname, item);

                return (
                  <Button key={item.to} variant={isActive ? "default" : "ghost"} size="sm" asChild>
                    <Link to={item.to} className="flex items-center">
                      <Icon className="mr-2 h-4 w-4" />
                      {item.label}
                    </Link>
                  </Button>
                );
              })}

              <Button variant="ghost" size="sm" onClick={logout}>
                <LogOut className="h-4 w-4" />
              </Button>
            </nav>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 sm:px-6 md:px-8 py-6">
        {children}
      </main>
    </div>
  );
}
