import React from "react";
import { cn } from "../../lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value: number; // 0 to 100
  max?: number;
  variant?: "primary" | "success" | "warning" | "error";
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

export const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  (
    {
      className,
      value = 0,
      max = 100,
      variant = "primary",
      size = "md",
      showLabel = false,
      ...props
    },
    ref
  ) => {
    const percentage = Math.min(Math.max(Math.round((value / max) * 100), 0), 100);

    const variantStyles = {
      primary: "bg-primary",
      success: "bg-emerald-600",
      warning: "bg-amber-500",
      error: "bg-error",
    };

    const sizeStyles = {
      sm: "h-1.5",
      md: "h-2.5",
      lg: "h-4",
    };

    return (
      <div className="w-full space-y-1.5" ref={ref} {...props}>
        {showLabel && (
          <div className="flex justify-between text-xs font-medium text-on-surface">
            <span>Progress</span>
            <span className="font-mono">{percentage}%</span>
          </div>
        )}
        <div
          className={cn(
            "w-full overflow-hidden rounded-full bg-surface-container-high",
            sizeStyles[size],
            className
          )}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={max}
        >
          <div
            className={cn(
              "h-full rounded-full transition-all duration-300 ease-out",
              variantStyles[variant]
            )}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    );
  }
);

Progress.displayName = "Progress";
