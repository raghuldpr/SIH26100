import React, { useState, useEffect, useCallback } from "react";
import { useAuth } from "../context/AuthContext";
import { probeSystemHealth, SystemHealthReport } from "../api/health";
import { ServiceStatusGrid, ConnectionDiagnostics } from "../components/settings";
import { Button, Badge } from "../components/ui";
import {
  Settings as SettingsIcon,
  User,
  Shield,
  Server,
  RefreshCw,
  LogOut,
  Mail,
  Lock,
  Activity,
} from "lucide-react";
import { formatDate } from "../lib/utils";

export const Settings: React.FC = () => {
  const { user, logout } = useAuth();
  const [healthReport, setHealthReport] = useState<SystemHealthReport | null>(null);
  const [isLoadingHealth, setIsLoadingHealth] = useState(true);

  const fetchHealth = useCallback(async () => {
    setIsLoadingHealth(true);
    try {
      const report = await probeSystemHealth();
      setHealthReport(report);
    } catch (err: any) {
      console.error("Failed to probe system health:", err);
    } finally {
      setIsLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
  }, [fetchHealth]);

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="space-y-8 font-sans pb-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-on-surface flex items-center gap-2">
            <SettingsIcon className="h-6 w-6 text-primary" />
            <span>Platform Settings &amp; System Health</span>
          </h1>
          <p className="text-xs text-on-surface-variant mt-1 font-mono">
            Manage authenticated session, view live subsystem health status, and inspect architecture diagnostics
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchHealth}
            isLoading={isLoadingHealth}
            leftIcon={<RefreshCw className="h-4 w-4" />}
          >
            Refresh Health
          </Button>

          <Button
            variant="danger"
            size="sm"
            onClick={handleLogout}
            leftIcon={<LogOut className="h-4 w-4" />}
          >
            Sign Out
          </Button>
        </div>
      </div>

      {/* 1. Profile / Session Information */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-outline-variant/20">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <User className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-on-surface">Authenticated Officer Profile</h3>
              <p className="text-[11px] font-mono text-on-surface-variant">
                Active session verified by FastAPI JWT Bearer authorization
              </p>
            </div>
          </div>
          <Badge variant="success" size="sm" dot>
            Active Session
          </Badge>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono">
          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
              Officer Name
            </span>
            <div className="text-sm font-bold text-on-surface truncate">
              {user?.name || "Procurement Officer"}
            </div>
          </div>

          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold flex items-center gap-1">
              <Mail className="h-3 w-3 text-outline" />
              <span>Email Address</span>
            </span>
            <div className="text-xs font-semibold text-on-surface truncate">
              {user?.email || "officer@gem.gov.in"}
            </div>
          </div>

          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold flex items-center gap-1">
              <Shield className="h-3 w-3 text-outline" />
              <span>Assigned Role</span>
            </span>
            <div>
              <Badge variant="primary" size="sm">
                {user?.role || "PROCUREMENT_OFFICER"}
              </Badge>
            </div>
          </div>

          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold flex items-center gap-1">
              <Lock className="h-3 w-3 text-outline" />
              <span>Account Status</span>
            </span>
            <div className="text-xs font-semibold text-emerald-700">
              {user?.is_active ? "Verified & Active" : "Active"}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Platform & Architecture Specifications */}
      <div className="p-6 bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-subtle space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-outline-variant/20">
          <div className="p-2 rounded-lg bg-primary/10 text-primary">
            <Server className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-on-surface">Platform &amp; Architectural Specifications</h3>
            <p className="text-[11px] font-mono text-on-surface-variant">
              SIH-26100 Quixotic GeM Autonomous Verification Stack
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 text-xs font-mono">
          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
              Platform &amp; System
            </span>
            <div className="font-bold text-on-surface">Quixotic / SIH-26100</div>
            <div className="text-[10px] text-on-surface-variant">GeM AI Compliance Engine</div>
          </div>

          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
              Frontend Client
            </span>
            <div className="font-bold text-on-surface">React 18 + Vite + Tailwind</div>
            <div className="text-[10px] text-on-surface-variant">Stitch Design Tokens (Deep Forest)</div>
          </div>

          <div className="p-3.5 bg-surface-container-low rounded-xl border border-outline-variant/20 space-y-1">
            <span className="text-[10px] uppercase tracking-wider text-on-surface-variant font-semibold">
              API Base Target
            </span>
            <div className="font-bold text-primary">/api/v1</div>
            <div className="text-[10px] text-on-surface-variant">Bearer JWT Authenticated</div>
          </div>
        </div>
      </div>

      {/* 3. Live System Health Grid */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary" />
              <span>Real-Time Subsystem Operational Status</span>
            </h2>
            <p className="text-xs text-on-surface-variant font-mono">
              Live probes against real backend health endpoints (FastAPI /health, /health/db, /verification/health)
            </p>
          </div>
          {healthReport && (
            <span className="text-[11px] font-mono text-on-surface-variant">
              Last checked: {formatDate(healthReport.checkedAt)}
            </span>
          )}
        </div>

        <ServiceStatusGrid report={healthReport} isLoading={isLoadingHealth} />
      </div>

      {/* 4. Diagnostics & Live Terminal Probe */}
      <ConnectionDiagnostics report={healthReport} onRefresh={fetchHealth} />
    </div>
  );
};

export default Settings;
