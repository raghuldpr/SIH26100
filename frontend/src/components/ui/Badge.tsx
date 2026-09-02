import React from "react";
import { cn } from "../../lib/utils";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?:
    | "primary"
    | "secondary"
    | "success"
    | "warning"
    | "danger"
    | "outline"
    | "neutral";
  size?: "sm" | "md";
  dot?: boolean;
}

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  (
    {
      className,
      variant = "neutral",
      size = "md",
      dot = false,
      children,
      ...props
    },
    ref
  ) => {
    const variantStyles = {
      primary:
        "bg-primary-fixed text-primary-fixed-on border-primary/20",
      secondary:
        "bg-secondary-container text-secondary-on-container border-secondary/20",
      success:
        "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
      warning:
        "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
      danger:
        "bg-red-50 text-red-800 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800",
      outline:
        "bg-transparent text-on-surface border-outline-variant",
      neutral:
        "bg-surface-container text-on-surface-variant border-outline-variant/50",
    };

    const dotColors = {
      primary: "bg-primary",
      secondary: "bg-secondary",
      success: "bg-emerald-500",
      warning: "bg-amber-500",
      danger: "bg-red-500",
      outline: "bg-outline",
      neutral: "bg-slate-400",
    };

    const sizeStyles = {
      sm: "text-[11px] px-2 py-0.5 font-medium tracking-wide",
      md: "text-xs px-2.5 py-1 font-medium",
    };

    return (
      <span
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border transition-colors",
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {dot && (
          <span
            className={cn("h-1.5 w-1.5 rounded-full shrink-0", dotColors[variant])}
            aria-hidden="true"
          />
        )}
        {children}
      </span>
    );
  }
);

Badge.displayName = "Badge";
