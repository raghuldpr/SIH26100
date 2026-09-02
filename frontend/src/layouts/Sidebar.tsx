import React from "react";
import { NavLink } from "react-router-dom";
import { PRIMARY_NAV_ITEMS, SECONDARY_NAV_ITEMS } from "../config/navigation";
import { ShieldCheck, X, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "../lib/utils";

interface SidebarProps {
  isMobileOpen: boolean;
  onCloseMobile: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isMobileOpen,
  onCloseMobile,
  isCollapsed,
  onToggleCollapse,
}) => {
  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden transition-opacity"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={cn(
          "fixed top-0 bottom-0 left-0 z-50 flex flex-col bg-surface-container-lowest border-r border-outline-variant/40 transition-all duration-200 ease-in-out lg:static lg:z-auto",
          isCollapsed ? "w-20" : "w-64",
          // Mobile responsive slide-in
          isMobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
        aria-label="Main Navigation"
      >
        {/* Brand Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-outline-variant/30 shrink-0">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="h-10 w-10 rounded-lg bg-primary text-white flex items-center justify-center shrink-0 shadow-sm">
              <ShieldCheck className="h-6 w-6 text-primary-fixed" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col truncate">
                <span className="text-sm font-bold tracking-tight text-on-surface truncate">
                  Quixotic
                </span>
                <span className="text-[10px] text-on-surface-variant font-mono truncate">
                  SIH-26100 Platform
                </span>
              </div>
            )}
          </div>

          {/* Close button for mobile */}
          <button
            onClick={onCloseMobile}
            className="lg:hidden rounded-lg p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
            aria-label="Close navigation drawer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-3 py-4 space-y-6">
          {/* Primary Navigation */}
          <div>
            {!isCollapsed && (
              <div className="px-3 mb-2 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/80">
                Procurement
              </div>
            )}
            <nav className="space-y-1">
              {PRIMARY_NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    onClick={onCloseMobile}
                    title={isCollapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                        isActive
                          ? "bg-primary text-white shadow-subtle font-semibold"
                          : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          className={cn(
                            "h-5 w-5 shrink-0 transition-colors",
                            isActive ? "text-primary-fixed" : "text-on-surface-variant group-hover:text-primary"
                          )}
                          aria-hidden="true"
                        />
                        {!isCollapsed && (
                          <div className="flex items-center justify-between flex-1 truncate">
                            <span className="truncate">{item.label}</span>
                            {item.badge && (
                              <span
                                className={cn(
                                  "text-[10px] px-1.5 py-0.5 rounded-full font-mono font-medium",
                                  isActive
                                    ? "bg-primary-container text-primary-fixed"
                                    : "bg-surface-container-high text-on-surface-variant"
                                )}
                              >
                                {item.badge}
                              </span>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </nav>
          </div>

          {/* Secondary Navigation */}
          <div>
            {!isCollapsed && (
              <div className="px-3 mb-2 text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/80">
                System
              </div>
            )}
            <nav className="space-y-1">
              {SECONDARY_NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <NavLink
                    key={item.id}
                    to={item.path}
                    onClick={onCloseMobile}
                    title={isCollapsed ? item.label : undefined}
                    className={({ isActive }) =>
                      cn(
                        "group flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
                        isActive
                          ? "bg-primary text-white shadow-subtle font-semibold"
                          : "text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          className={cn(
                            "h-5 w-5 shrink-0 transition-colors",
                            isActive ? "text-primary-fixed" : "text-on-surface-variant group-hover:text-primary"
                          )}
                          aria-hidden="true"
                        />
                        {!isCollapsed && <span className="truncate">{item.label}</span>}
                      </>
                    )}
                  </NavLink>
                );
              })}
            </nav>
          </div>
        </div>

        {/* Sidebar Footer Collapse Toggle (Desktop only) */}
        <div className="hidden lg:flex items-center justify-between p-3 border-t border-outline-variant/30 shrink-0">
          <button
            onClick={onToggleCollapse}
            className="flex items-center justify-center w-full py-2 px-3 rounded-lg text-xs font-medium text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors gap-2"
            aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span>Collapse View</span>
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  );
};
