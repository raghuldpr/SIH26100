import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Button, Card, CardContent, CardHeader, CardTitle, CardDescription, Input } from "../components/ui";
import { ShieldCheck, Mail, Lock, AlertCircle, ArrowRight } from "lucide-react";
import { ApiClientError } from "../api/client";

export const Login: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!email.trim() || !password) {
      setErrorMessage("Please enter both email and password.");
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage(err?.message || "Failed to authenticate. Please check credentials.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col justify-center py-12 sm:px-6 lg:px-8 font-sans">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center space-y-2">
        <div className="inline-flex h-12 w-12 rounded-xl bg-primary text-white items-center justify-center shadow-card">
          <ShieldCheck className="h-7 w-7 text-primary-fixed" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-on-surface">
          Quixotic Procurement
        </h1>
        <p className="text-xs text-on-surface-variant font-mono">
          SIH-26100 — Multi-Agent Bid Verification System
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <Card variant="elevated" className="bg-surface-container-lowest border-outline-variant/40">
          <CardHeader className="text-center pb-2">
            <CardTitle className="text-xl">Sign in to your account</CardTitle>
            <CardDescription>
              Enter your official procurement credentials to access the analytics workspace.
            </CardDescription>
          </CardHeader>

          <CardContent>
            {errorMessage && (
              <div className="mb-5 p-3.5 rounded-lg bg-error-container text-error text-xs flex items-start gap-2.5 animate-in fade-in">
                <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-error" />
                <div className="flex-1 font-medium">{errorMessage}</div>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Official Email"
                type="email"
                placeholder="officer@procurement.gov.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                leftIcon={<Mail className="h-4 w-4" />}
                disabled={isSubmitting}
              />

              <Input
                label="Password"
                type="password"
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                leftIcon={<Lock className="h-4 w-4" />}
                disabled={isSubmitting}
              />

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="w-full"
                  isLoading={isSubmitting}
                  rightIcon={<ArrowRight className="h-4 w-4" />}
                >
                  Sign In
                </Button>
              </div>
            </form>

            <div className="mt-6 pt-4 border-t border-outline-variant/30 text-center text-xs text-on-surface-variant">
              <span>Don&apos;t have an officer account? </span>
              <Link
                to="/register"
                className="font-semibold text-primary hover:underline hover:text-primary-hover transition-colors"
              >
                Register here
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
