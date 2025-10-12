import type { ComponentType, SVGProps } from "react";
import {
  Activity,
  FileText,
  LayoutDashboard,
  MessageSquare,
  Satellite,
  Settings,
  Tags,
  Upload,
  Users,
} from "lucide-react";

export type LucideIconComponent = ComponentType<SVGProps<SVGSVGElement>>;

export interface NavigationItem {
  label: string;
  href: string;
  icon: LucideIconComponent;
  match?: "exact" | "startsWith";
  children?: NavigationItem[];
}

export const navigationItems: NavigationItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
  },
  {
    label: "Contatos",
    href: "/contacts",
    icon: Users,
    match: "startsWith",
    children: [
      {
        label: "Catálogo",
        href: "/contacts",
        icon: Users,
      },
      {
        label: "Importação",
        href: "/contacts/import",
        icon: Upload,
      },
    ],
  },
  {
    label: "Segmentos",
    href: "/segments",
    icon: Tags,
  },
  {
    label: "Mensagens",
    href: "/messages",
    icon: MessageSquare,
    match: "startsWith",
    children: [
      {
        label: "Campanhas",
        href: "/messages",
        icon: MessageSquare,
      },
      {
        label: "Templates",
        href: "/templates",
        icon: FileText,
      },
    ],
  },
  {
    label: "Regras",
    href: "/rules",
    icon: Activity,
  },
  {
    label: "Relatórios",
    href: "/reports",
    icon: FileText,
  },
  {
    label: "Provedores",
    href: "/providers",
    icon: Satellite,
  },
  {
    label: "Configurações",
    href: "/settings",
    icon: Settings,
  },
];
