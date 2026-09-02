import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { PublicRoute } from "./PublicRoute";
import { AppLayout } from "../layouts/AppLayout";
import {
  Login,
  Register,
  Dashboard,
  Tenders,
  TenderDetailsPage,
  Bidders,
  BidderDetailsPage,
  Verification,
  Reports,
  Documents,
  Settings,
} from "../pages";

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public Routes (Accessible only when unauthenticated) */}
      <Route element={<PublicRoute />}>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>

      {/* Protected Routes (Wrapped with ProtectedRoute and AppLayout) */}
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/tenders" element={<Tenders />} />
          <Route path="/tenders/:tenderId" element={<TenderDetailsPage />} />
          <Route path="/bidders" element={<Bidders />} />
          <Route path="/bidders/:bidderId" element={<BidderDetailsPage />} />
          <Route path="/verification" element={<Verification />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>

      {/* Root redirection */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Catch-all fallback */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};
