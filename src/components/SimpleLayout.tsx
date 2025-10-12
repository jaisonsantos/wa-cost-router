import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Button } from "./ui/button";
import { Sheet, SheetClose, SheetContent, SheetTrigger } from "./ui/sheet";
import { LogOut, Menu } from "lucide-react";
import { navigationItems, type NavigationItem } from "@/config/navigation";
import { cn } from "@/lib/utils";
import {
  NavigationMenu,
  NavigationMenuContent,
  NavigationMenuItem,
  NavigationMenuLink,
  NavigationMenuList,
  NavigationMenuTrigger,
  navigationMenuTriggerStyle,
} from "./ui/navigation-menu";

interface SimpleLayoutProps {
  children: ReactNode;
}

export default function SimpleLayout({ children }: SimpleLayoutProps) {
  const { logout } = useAuth();
  const location = useLocation();

  const renderMobileItems = (items: NavigationItem[], level = 0) =>
    items.map((item) => {
      const Icon = item.icon;
      const isActive = isItemActive(location.pathname, item);
      const isSelfActive = isItemSelfActive(location.pathname, item);

      return (
        <div key={item.href} className="flex flex-col gap-2">
          <SheetClose asChild>
            <Button
              variant={isActive ? "default" : "ghost"}
              size="sm"
              className={cn(
                "justify-start gap-2",
                getMobileLevelClasses(level),
              )}
              asChild
            >
              <Link
                to={item.href}
                className="flex items-center gap-2"
                aria-current={isSelfActive ? "page" : undefined}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            </Button>
          </SheetClose>

          {item.children?.length ? (
            <div className="flex flex-col gap-2">
              {renderMobileItems(item.children, level + 1)}
            </div>
          ) : null}
        </div>
      );
    });

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
                      {renderMobileItems(navigationItems)}
                      <SheetClose asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="justify-start gap-2"
                          onClick={logout}
                        >
                          <LogOut className="h-4 w-4" aria-hidden />
                          Sair
                        </Button>
                      </SheetClose>
                    </nav>
                  </SheetContent>
                </Sheet>
              </div>
            </div>

            <div className="hidden w-full md:flex md:w-auto md:flex-wrap md:items-center md:justify-end md:gap-2 lg:gap-3">
              <NavigationMenu className="max-w-none">
                <NavigationMenuList>
                  {navigationItems.map((item) => {
                    const Icon = item.icon;
                    const isActive = isItemActive(location.pathname, item);

                    if (item.children?.length) {
                      return (
                        <NavigationMenuItem key={item.href}>
                          <NavigationMenuTrigger
                            className={cn(
                              "gap-2 justify-start",
                              isActive && "bg-primary text-primary-foreground hover:bg-primary/90",
                            )}
                            data-active={isActive || undefined}
                          >
                            <Icon className="h-4 w-4" />
                            {item.label}
                          </NavigationMenuTrigger>
                          <NavigationMenuContent>
                            <ul className="grid gap-1 p-2 md:w-64">
                              {item.children.map((child) => {
                                const ChildIcon = child.icon;
                                const isChildActive = isItemActive(location.pathname, child);
                                const isChildSelfActive = isItemSelfActive(location.pathname, child);

                                return (
                                  <li key={child.href}>
                                    <NavigationMenuLink asChild>
                                      <Link
                                        to={child.href}
                                        className={cn(
                                          "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-accent",
                                          isChildActive &&
                                            "bg-primary text-primary-foreground hover:bg-primary/90",
                                        )}
                                        aria-current={isChildSelfActive ? "page" : undefined}
                                      >
                                        <ChildIcon className="h-4 w-4" />
                                        {child.label}
                                      </Link>
                                    </NavigationMenuLink>
                                  </li>
                                );
                              })}
                            </ul>
                          </NavigationMenuContent>
                        </NavigationMenuItem>
                      );
                    }

                    return (
                      <NavigationMenuItem key={item.href}>
                        <NavigationMenuLink
                          asChild
                          className={cn(
                            navigationMenuTriggerStyle(),
                            "gap-2 justify-start",
                            isActive && "bg-primary text-primary-foreground hover:bg-primary/90",
                          )}
                        >
                          <Link
                            to={item.href}
                            className="flex items-center gap-2"
                            aria-current={isItemSelfActive(location.pathname, item) ? "page" : undefined}
                          >
                            <Icon className="h-4 w-4" />
                            {item.label}
                          </Link>
                        </NavigationMenuLink>
                      </NavigationMenuItem>
                    );
                  })}
                </NavigationMenuList>
              </NavigationMenu>

              <Button variant="ghost" size="sm" onClick={logout}>
                <LogOut className="h-4 w-4" aria-hidden />
                <span className="sr-only">Sair</span>
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 sm:px-6 md:px-8 py-6">
        {children}
      </main>
    </div>
  );
}

const normalizePath = (value: string) => {
  if (!value) {
    return "/";
  }

  if (value === "/") {
    return value;
  }

  return value.replace(/\/+$/, "");
};

const matchesPath = (pathname: string, href: string, match: NavigationItem["match"] = "exact") => {
  const normalizedPath = normalizePath(pathname);
  const normalizedHref = normalizePath(href);

  if (match === "startsWith") {
    if (normalizedHref === "/") {
      return normalizedPath === normalizedHref;
    }

    return (
      normalizedPath === normalizedHref ||
      normalizedPath.startsWith(`${normalizedHref}/`)
    );
  }

  return normalizedPath === normalizedHref;
};

const isItemSelfActive = (pathname: string, item: NavigationItem) =>
  matchesPath(pathname, item.href, item.match);

const isItemActive = (pathname: string, item: NavigationItem): boolean =>
  isItemSelfActive(pathname, item) ||
  item.children?.some((child) => isItemActive(pathname, child)) === true;

const getMobileLevelClasses = (level: number) => {
  if (level <= 0) {
    return undefined;
  }

  if (level === 1) {
    return "pl-6 text-sm";
  }

  return "pl-10 text-sm";
};
