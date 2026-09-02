import {
  LayoutDashboard,
  FileText,
  Building2,
  FolderOpen,
  ShieldCheck,
  BarChart3,
  Settings,
  LucideIcon,
} from "lucide-react";

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: LucideIcon;
  badge?: string;
  description?: string;
}

export const PRIMARY_NAV_ITEMS: NavItem[] = [
  {
    id: "dashboard",
    label: "Dashboard",
    path: "/dashboard",
    icon: LayoutDashboard,
    description: "Procurement overview & compliance analytics",
  },
  {
    id: "tenders",
    label: "Tenders",
    path: "/tenders",
    icon: FileText,
    description: "GeM tender management & clause requirements",
  },
  {
    id: "bidders",
    label: "Bidders",
    path: "/bidders",
    icon: Building2,
    description: "Registered bidder entities & statutory filings",
  },
  {
    id: "documents",
    label: "Documents",
    path: "/documents",
    icon: FolderOpen,
    description: "Document vault, OCR & evidence extraction",
  },
  {
    id: "verification",
    label: "Verification",
    path: "/verification",
    icon: ShieldCheck,
    badge: "10 Agents",
    description: "Multi-agent compliance verification & audit trail",
  },
  {
    id: "reports",
    label: "Reports",
    path: "/reports",
    icon: BarChart3,
    description: "Compliance summaries & tamper-evident digests",
  },
];

export const SECONDARY_NAV_ITEMS: NavItem[] = [
  {
    id: "settings",
    label: "Settings",
    path: "/settings",
    icon: Settings,
    description: "Platform configurations & audit logs",
  },
];
