import React from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "../../lib/utils";
import { Skeleton } from "../ui/Skeleton";

export interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  variant?: "default" | "primary" | "warning" | "error" | "success";
  isLoading?: boolean;
  actionText?: string;
  onAction?: () => void;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = "default",
  isLoading = false,
  actionText,
  onAction,
}) => {
  const iconBgStyles = {
    default: "bg-surface-container text-on-surface-variant",
    primary: "bg-primary-container/10 text-primary",
    warning: "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
    error: "bg-error-container text-error",
    success: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300",
  };

  const borderStyles = {
    default: "border-outline-variant/30",
    primary: "border-primary/20",
    warning: "border-l-4 border-l-amber-500 border-outline-variant/30",
    error: "border-l-4 border-l-error border-outline-variant/30",
    success: "border-outline-variant/30",
  };

  return (
    <div
      className={cn(
        "bg-surface-container-lowest rounded-xl p-6 shadow-subtle border flex flex-col justify-between transition-all duration-200 hover:shadow-card",
        borderStyles[variant]
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <div className={cn("p-2.5 rounded-lg flex items-center justify-center", iconBgStyles[variant])}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
        {actionText && (
          <button
            onClick={onAction}
            className="text-xs font-semibold text-primary hover:underline hover:text-primary-hover transition-colors"
          >
            {actionText}
          </button>
        )}
      </div>

      <div>
        <p className="text-[11px] font-mono uppercase tracking-wider text-on-surface-variant mb-1.5 font-medium">
          {title}
        </p>
        {isLoading ? (
          <Skeleton className="h-9 w-24 mb-1" />
        ) : (
          <p className="text-2xl sm:text-3xl font-bold tracking-tight text-on-surface font-sans">
            {value}
          </p>
        )}
        {subtitle && (
          <p className="text-xs text-on-surface-variant/80 mt-1 truncate">
            {subtitle}
          </p>
        )}
      </div>
    </div>
  );
};
