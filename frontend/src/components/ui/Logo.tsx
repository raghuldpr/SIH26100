import React from "react";
import { cn } from "../../lib/utils";

export interface LogoProps {
  size?: "sm" | "md" | "lg" | "xl";
  variant?: "icon-only" | "horizontal" | "stacked";
  showTagline?: boolean;
  className?: string;
  iconClassName?: string;
}

export const TenderTrustLogo: React.FC<LogoProps> = ({
  size = "md",
  variant = "horizontal",
  showTagline = false,
  className,
  iconClassName,
}) => {
  // Dimensions based on size
  const iconDimensions = {
    sm: "h-7 w-7",
    md: "h-9 w-9",
    lg: "h-12 w-12",
    xl: "h-14 w-14",
  }[size];

  const titleSizes = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-xl",
    xl: "text-2xl",
  }[size];

  const taglineSizes = {
    sm: "text-[9px]",
    md: "text-[10px]",
    lg: "text-xs",
    xl: "text-xs",
  }[size];

  const IconSVG = (
    <div
      className={cn(
        "rounded-xl bg-primary flex items-center justify-center shrink-0 shadow-sm p-1.5 transition-transform",
        iconDimensions,
        iconClassName
      )}
      role="img"
      aria-label="TenderTrust emblem"
    >
      <svg
        viewBox="0 0 36 36"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full"
      >
        {/* Shield contour */}
        <path
          d="M18 3L5 8V16.5C5 24.5 10.5 31.8 18 33.8C25.5 31.8 31 24.5 31 16.5V8L18 3Z"
          fill="#004430"
          stroke="#125D44"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        {/* Stylized tender document */}
        <path
          d="M12.5 11.5H20.5L24.5 15.5V25C24.5 25.8 23.8 26.5 23 26.5H12.5C11.7 26.5 11 25.8 11 25V13C11 12.2 11.7 11.5 12.5 11.5Z"
          fill="#125D44"
        />
        {/* Document fold */}
        <path
          d="M20.5 11.5V15.5H24.5"
          fill="none"
          stroke="#ABF1D0"
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {/* Verification trust checkmark */}
        <path
          d="M14 19.5L17 22.5L23.5 16"
          fill="none"
          stroke="#ABF1D0"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );

  if (variant === "icon-only") {
    return (
      <div className={cn("inline-flex items-center", className)} title="TenderTrust">
        {IconSVG}
      </div>
    );
  }

  if (variant === "stacked") {
    return (
      <div className={cn("flex flex-col items-center text-center space-y-2", className)}>
        {IconSVG}
        <div className="flex flex-col items-center">
          <span className={cn("font-bold tracking-tight text-on-surface font-sans", titleSizes)}>
            TenderTrust
          </span>
          {showTagline && (
            <span className={cn("text-on-surface-variant font-medium tracking-normal mt-0.5 font-sans", taglineSizes)}>
              Reliable Procurement Decisions
            </span>
          )}
        </div>
      </div>
    );
  }

  // Default "horizontal"
  return (
    <div className={cn("inline-flex items-center gap-2.5 overflow-hidden", className)}>
      {IconSVG}
      <div className="flex flex-col truncate text-left">
        <span className={cn("font-bold tracking-tight text-on-surface truncate font-sans", titleSizes)}>
          TenderTrust
        </span>
        {showTagline && (
          <span className={cn("text-on-surface-variant font-medium truncate font-sans tracking-tight", taglineSizes)}>
            Reliable Procurement Decisions
          </span>
        )}
      </div>
    </div>
  );
};

export const Logo = TenderTrustLogo;
export default TenderTrustLogo;
