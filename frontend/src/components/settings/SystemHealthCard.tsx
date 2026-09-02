import React from "react";
import { ServiceHealth } from "../../api/health";
import { Badge, StatusIndicator } from "../ui";
import {
  Server,
  Database,
  Cpu,
  ShieldCheck,
  FileSearch,
  Sparkles,
  Clock,
} from "lucide-react";

export interface SystemHealthCardProps {
  service: ServiceHealth;
}

export const SystemHealthCard: React.FC<SystemHealthCardProps> = ({ service }) => {
  const getIcon = () => {
    switch (service.id) {
      case "fastapi-backend":
        return <Server className="h-4 w-4 text-primary" />;
      case "database-layer":
        return <Database className="h-4 w-4 text-primary" />;
      case "n8n-orchestrator":
        return <Cpu className="h-4 w-4 text-primary" />;
      case "verification-engine":
        return <ShieldCheck className="h-4 w-4 text-primary" />;
      case "document-engine":
        return <FileSearch className="h-4 w-4 text-primary" />;
      case "ai-gateway":
        return <Sparkles className="h-4 w-4 text-primary" />;
      default:
        return <Server className="h-4 w-4 text-primary" />;
    }
  };

  const getStatusIndicatorType = (): "online" | "offline" | "review" | "pending" => {
    switch (service.status) {
      case "ONLINE":
        return "online";
      case "DEGRADED":
        return "review";
      case "OFFLINE":
        return "offline";
      default:
        return "pending";
    }
  };

  const getStatusBadge = () => {
    switch (service.status) {
      case "ONLINE":
        return <Badge variant="success" size="sm" dot>ONLINE</Badge>;
      case "DEGRADED":
        return <Badge variant="warning" size="sm" dot>DEGRADED</Badge>;
      case "OFFLINE":
        return <Badge variant="danger" size="sm" dot>OFFLINE</Badge>;
      default:
        return <Badge variant="neutral" size="sm" dot>UNKNOWN</Badge>;
    }
  };

  return (
    <div className="p-4 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-3 hover:border-primary/40 transition-colors">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 truncate">
          <div className="p-1.5 rounded-lg bg-surface-container text-primary shrink-0">
            {getIcon()}
          </div>
          <span className="font-semibold text-xs text-on-surface truncate">
            {service.name}
          </span>
        </div>
        <div className="shrink-0 flex items-center gap-1.5">
          <StatusIndicator status={getStatusIndicatorType()} />
          {getStatusBadge()}
        </div>
      </div>

      <div className="space-y-1">
        <p className="text-[11px] text-on-surface font-mono leading-relaxed">
          {service.message || "Operational"}
        </p>
        <div className="flex items-center justify-between text-[10px] font-mono text-on-surface-variant pt-2 border-t border-outline-variant/20">
          <span className="truncate">{service.endpoint}</span>
          {service.latencyMs !== undefined && (
            <span className="flex items-center gap-1 text-primary shrink-0">
              <Clock className="h-3 w-3" />
              <span>{service.latencyMs}ms</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
