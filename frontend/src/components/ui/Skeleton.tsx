import React from "react";
import { cn } from "../../lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "rectangular" | "circular" | "text";
}

export const Skeleton: React.FC<SkeletonProps> = ({
  className,
  variant = "rectangular",
  ...props
}) => {
  const variantStyles = {
    rectangular: "rounded-lg",
    circular: "rounded-full",
    text: "rounded h-4 w-full",
  };

  return (
    <div
      className={cn(
        "animate-pulse bg-surface-container-high/60",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
};
