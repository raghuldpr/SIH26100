import React from "react";
import { cn } from "../../lib/utils";

export type StatusType =
  | "online"
  | "offline"
  | "running"
  | "completed"
  | "failed"
  | "pending"
  | "verified"
  | "review";

export interface StatusIndicatorProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusType;
  label?: string;
  ping?: boolean;
}

export const StatusIndicator: React.FC<StatusIndicatorProps> = ({
  status,
  label,
  ping = false,
  className,
  ...props
}) => {
  const statusColors = {
    online: "bg-emerald-500",
    completed: "bg-emerald-600",
    verified: "bg-emerald-600",
    running: "bg-primary-container",
    pending: "bg-amber-400",
    review: "bg-amber-500",
    failed: "bg-error",
    offline: "bg-slate-400",
  };

  const statusLabels: Record<StatusType, string> = {
    online: "Online",
    completed: "Completed",
    verified: "Verified",
    running: "Running",
    pending: "Pending",
    review: "In Review",
    failed: "Failed",
    offline: "Offline",
  };

  const displayLabel = label || statusLabels[status];

  return (
    <span
      className={cn("inline-flex items-center gap-2 text-xs font-medium text-on-surface", className)}
      {...props}
    >
      <span className="relative flex h-2.5 w-2.5">
        {(ping || status === "running") && (
          <span
            className={cn(
              "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
              statusColors[status]
            )}
          />
        )}
        <span
          className={cn(
            "relative inline-flex rounded-full h-2.5 w-2.5",
            statusColors[status]
          )}
        />
      </span>
      {displayLabel && <span>{displayLabel}</span>}
    </span>
  );
};
