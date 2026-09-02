import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button, Card, CardContent, CardHeader, CardTitle, CardDescription, Input, Select } from "../components/ui";
import { ShieldCheck, Mail, Lock, User, AlertCircle, ArrowRight } from "lucide-react";
import { ApiClientError } from "../api/client";
import { UserRole } from "../types";

export const Register: React.FC = () => {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<UserRole>("PROCUREMENT_OFFICER");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!name.trim() || name.trim().length < 2) {
      setErrorMessage("Full name must be at least 2 characters.");
      return;
    }

    if (!email.trim()) {
      setErrorMessage("Please enter an official email address.");
      return;
    }

    if (!password || password.length < 8) {
      setErrorMessage("Password must be at least 8 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match. Please verify.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register({
        name: name.trim(),
        email: email.trim(),
        password,
        role,
      });
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(err?.message || "Registration failed. Please try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center py-10 sm:px-6 lg:px-8 font-sans">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="inline-flex h-12 w-12 rounded-xl bg-primary text-white items-center justify-center shadow-card">
          <ShieldCheck className="h-7 w-7 text-primary-fixed" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-on-surface">
          Quixotic Procurement
        </h1>
        <p className="text-xs text-on-surface-variant font-mono">
          Create Officer / Evaluator Account
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card variant="elevated" className="bg-surface-container-lowest border-outline-variant/40">
          <CardHeader className="text-center pb-2">
            <CardTitle className="text-xl">Register Account</CardTitle>
            <CardDescription>
              Provide your details to register as a verified officer on the platform.
            </CardDescription>
          </CardHeader>

          <CardContent>
            {errorMessage && (
              <div className="mb-5 p-3.5 rounded-lg bg-error-container text-error text-xs flex items-start gap-2.5 animate-in fade-in">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-error" />
                <div className="flex-1 font-medium">{errorMessage}</div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-3.5">
              <Input
                label="Full Name"
                type="text"
                placeholder="Dr. Rajesh Kumar"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                autoComplete="name"
                leftIcon={<User className="h-4 w-4" />}
                disabled={isSubmitting}
              />

              <Input
                label="Official Email"
                type="email"
                placeholder="rajesh.kumar@procurement.gov.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                leftIcon={<Mail className="h-4 w-4" />}
                disabled={isSubmitting}
              />

              <Select
                label="Platform Role"
                value={role}
                onChange={(e) => setRole(e.target.value as UserRole)}
                options={[
                  { value: "PROCUREMENT_OFFICER", label: "Procurement Officer" },
                  { value: "REVIEWER", label: "Compliance Reviewer" },
                  { value: "BUYER", label: "Government Buyer / Department" },
                  { value: "BIDDER", label: "Registered Bidder Entity" },
                  { value: "ADMIN", label: "Platform Administrator" },
                ]}
                disabled={isSubmitting}
              />

              <Input
                label="Password (min 8 chars)"
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                leftIcon={<Lock className="h-4 w-4" />}
                disabled={isSubmitting}
              />

              <Input
                label="Confirm Password"
                type="password"
                placeholder="••••••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                leftIcon={<Lock className="h-4 w-4" />}
                disabled={isSubmitting}
              />

              <div className="pt-3">
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="w-full"
                  isLoading={isSubmitting}
                  rightIcon={<ArrowRight className="h-4 w-4" />}
                >
                  Complete Registration
                </Button>
              </div>
            </form>

            <div className="mt-6 pt-4 border-t border-outline-variant/30 text-center text-xs text-on-surface-variant">
              <span>Already have an account? </span>
              <Link
                to="/login"
                className="font-semibold text-primary hover:underline hover:text-primary-hover transition-colors"
              >
                Sign in
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
