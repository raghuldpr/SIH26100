import React, { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Menu, Search, Bell, LogOut, User as UserIcon, Shield, ChevronDown } from "lucide-react";
import { Badge, StatusIndicator } from "../components/ui";

interface HeaderProps {
  onOpenMobileNav: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onOpenMobileNav }) => {
  const { user, logout } = useAuth();
  const location = useLocation();

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Compute page title from path
  const getPageTitle = (pathname: string) => {
    const cleanPath = pathname.split("/")[1] || "dashboard";
    switch (cleanPath) {
      case "dashboard":
        return { title: "Tender Analytics Dashboard", subtitle: "Overview & Compliance" };
      case "tenders":
        return { title: "Procurement Tenders", subtitle: "GeM Tender Registry & Clause Intelligence" };
      case "bidders":
        return { title: "Bidder Organizations", subtitle: "Statutory Filings & Evidence Verification" };
      case "documents":
        return { title: "Document Processing Vault", subtitle: "OCR & Structured Parameter Extraction" };
      case "verification":
        return { title: "Multi-Agent Verification", subtitle: "n8n Orchestration & Traceability" };
      case "reports":
        return { title: "Audit & Compliance Reports", subtitle: "Tamper-Evident SHA-256 Certificates" };
      case "settings":
        return { title: "Platform Settings", subtitle: "Access Control & Integrations" };
      default:
        return { title: "Procurement Workspace", subtitle: "SIH-26100 Platform" };
    }
  };

  const { title, subtitle } = getPageTitle(location.pathname);

  // Compute user initials
  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "PO";

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-16 px-4 sm:px-6 bg-surface-container-lowest border-b border-outline-variant/40 shadow-subtle shrink-0">
      {/* Left: Mobile Menu Toggle & Breadcrumbs */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileNav}
          className="lg:hidden rounded-lg p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
          aria-label="Open navigation menu"
        >
          <Menu className="h-5 w-5" />
        </button>

        <div className="flex flex-col">
          <h1 className="text-sm sm:text-base font-bold text-on-surface tracking-tight leading-tight">
            {title}
          </h1>
          <span className="hidden sm:inline text-[11px] text-on-surface-variant font-mono">
            {subtitle}
          </span>
        </div>
      </div>

      {/* Right: Search, Live Indicator, Notifications & User Profile */}
      <div className="flex items-center gap-2 sm:gap-4">
        {/* Global Search UI Placeholder */}
        <div className="hidden md:flex items-center relative w-64">
          <Search className="absolute left-3 h-4 w-4 text-outline pointer-events-none" />
          <input
            type="text"
            placeholder="Search tenders, GSTIN, PAN..."
            readOnly
            className="w-full h-9 pl-9 pr-8 text-xs rounded-lg border border-outline-variant/60 bg-surface-container-low text-on-surface placeholder:text-outline cursor-pointer focus:outline-none hover:border-outline-variant"
            title="Global search functionality (Non-functional placeholder)"
          />
          <kbd className="absolute right-2 px-1.5 py-0.5 text-[10px] font-mono font-medium text-outline bg-surface-container rounded border border-outline-variant/50">
            ⌘K
          </kbd>
        </div>

        {/* Live Engine Status Indicator */}
        <div className="hidden sm:flex items-center">
          <StatusIndicator status="online" label="Orchestrator" ping />
        </div>

        {/* Notification Bell */}
        <button
          className="relative rounded-lg p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
          aria-label="View notifications"
          title="Notifications"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute top-1.5 right-1.5 h-2 w-2 rounded-full bg-primary" />
        </button>

        {/* User Profile Menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setIsUserMenuOpen(!isUserMenuOpen)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-surface-container transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            aria-expanded={isUserMenuOpen}
            aria-haspopup="true"
            aria-label="User account menu"
          >
            <div className="h-8 w-8 rounded-lg bg-primary text-primary-fixed flex items-center justify-center text-xs font-bold font-mono shadow-sm">
              {initials}
            </div>
            <div className="hidden md:flex flex-col text-left">
              <span className="text-xs font-semibold text-on-surface leading-snug">
                {user?.name || "Procurement Officer"}
              </span>
              <span className="text-[10px] text-on-surface-variant font-mono leading-none">
                {user?.role || "OFFICER"}
              </span>
            </div>
            <ChevronDown className="hidden md:block h-3.5 w-3.5 text-on-surface-variant" />
          </button>

          {/* User Popover Dropdown */}
          {isUserMenuOpen && (
            <div
              className="absolute right-0 mt-2 w-64 rounded-xl bg-surface-container-lowest border border-outline-variant/30 shadow-elevated py-2 z-50 animate-in fade-in zoom-in-95 duration-150"
              role="menu"
            >
              {/* Profile Details */}
              <div className="px-4 py-3 border-b border-outline-variant/20 space-y-1">
                <div className="text-xs font-bold text-on-surface truncate">
                  {user?.name || "Procurement Officer"}
                </div>
                <div className="text-[11px] text-on-surface-variant font-mono truncate">
                  {user?.email || "officer@procurement.gov.in"}
                </div>
                <div className="pt-1.5">
                  <Badge variant="primary" size="sm">
                    {user?.role || "PROCUREMENT_OFFICER"}
                  </Badge>
                </div>
              </div>

              {/* Account Quick Links */}
              <div className="py-1">
                <div className="px-4 py-2 text-xs text-on-surface-variant flex items-center gap-2">
                  <Shield className="h-3.5 w-3.5 text-primary" />
                  <span>Clearance: Verified Level 3</span>
                </div>
                <div className="px-4 py-2 text-xs text-on-surface-variant flex items-center gap-2">
                  <UserIcon className="h-3.5 w-3.5 text-primary" />
                  <span>Session: Active Bearer JWT</span>
                </div>
              </div>

              {/* Logout Button */}
              <div className="pt-1 border-t border-outline-variant/20">
                <button
                  onClick={() => {
                    setIsUserMenuOpen(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-2 px-4 py-2.5 text-xs font-semibold text-error hover:bg-error-container/40 transition-colors text-left"
                  role="menuitem"
                >
                  <LogOut className="h-4 w-4" />
                  <span>Sign Out Session</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
