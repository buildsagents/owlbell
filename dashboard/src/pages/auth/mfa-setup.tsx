import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";
import { Loader2, PhoneCall, Smartphone, ShieldCheck } from "lucide-react";
import type { ApiError, MfaSetup } from "@/types";

export default function MfaSetupPage() {
  const [searchParams] = useSearchParams();
  const tempToken = searchParams.get("tempToken") || useAuthStore((s) => s.mfaTempToken);

  const [step, setStep] = useState<"setup" | "verify" | "done">("setup");
  const [code, setCode] = useState("");
  const [mfaSetup, setMfaSetup] = useState<MfaSetup | null>(null);
  const [error, setError] = useState("");

  const setupMfa = useMutation({
    mutationFn: async () => {
      const response = await api.post<MfaSetup>("/auth/mfa/setup", {
        tempToken,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setMfaSetup(data);
    },
    onError: (err: AxiosError<ApiError>) => {
      setError(err.response?.data?.error?.message || "Failed to set up MFA");
    },
  });

  const verifyMfa = useMutation({
    mutationFn: async (code: string) => {
      const response = await api.post("/auth/mfa/verify", {
        code,
        tempToken,
      });
      return response.data;
    },
    onSuccess: () => {
      setStep("done");
    },
    onError: (err: AxiosError<ApiError>) => {
      setError(err.response?.data?.error?.message || "Invalid verification code");
    },
  });

  useEffect(() => {
    if (step === "setup" && !mfaSetup) {
      setupMfa.mutate();
    }
  }, [step]);

  const handleVerify = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (code.length !== 6) {
      setError("Please enter a 6-digit code");
      return;
    }
    verifyMfa.mutate(code);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-100 to-slate-200 p-4 dark:from-slate-900 dark:to-slate-800">
      <div className="w-full max-w-md">
        <div className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <PhoneCall className="h-5 w-5" />
          </div>
          <span className="text-2xl font-bold">Owlbell</span>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Two-Factor Authentication</CardTitle>
            <CardDescription>Secure your account with MFA</CardDescription>
          </CardHeader>
          <CardContent>
            {setupMfa.isPending && (
              <div className="flex flex-col items-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="mt-4 text-sm text-muted-foreground">Setting up MFA...</p>
              </div>
            )}

            {step === "setup" && !setupMfa.isPending && mfaSetup && (
              <div className="space-y-4">
                {mfaSetup.qrCodeUrl && (
                  <div className="flex justify-center p-4 bg-muted rounded-lg">
                    <img src={mfaSetup.qrCodeUrl} alt="MFA QR Code" className="h-40 w-40" />
                  </div>
                )}
                {mfaSetup.secret && (
                  <div className="rounded-lg bg-muted p-3 text-center">
                    <p className="text-xs text-muted-foreground mb-1">Or enter this key manually:</p>
                    <p className="font-mono text-sm font-bold tracking-wider">{mfaSetup.secret}</p>
                  </div>
                )}
                <p className="text-sm text-center text-muted-foreground">
                  Scan the QR code with your authenticator app
                </p>
                <Button className="w-full" onClick={() => setStep("verify")}>
                  <Smartphone className="mr-2 h-4 w-4" /> I've scanned the code
                </Button>
                {mfaSetup.backupCodes && mfaSetup.backupCodes.length > 0 && (
                  <div className="rounded-lg border p-3">
                    <p className="text-xs font-medium text-muted-foreground mb-2">Backup Codes (save these):</p>
                    <div className="grid grid-cols-2 gap-1">
                      {mfaSetup.backupCodes.map((c, i) => (
                        <code key={i} className="text-xs font-mono">{c}</code>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {step === "verify" && !setupMfa.isPending && (
              <form onSubmit={handleVerify} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">Verification Code</label>
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                    placeholder="000000"
                    maxLength={6}
                  />
                </div>
                {error && <p className="text-sm text-rose-500">{error}</p>}
                <Button type="submit" className="w-full" disabled={verifyMfa.isPending}>
                  {verifyMfa.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Verify
                </Button>
              </form>
            )}

            {step === "done" && (
              <div className="flex flex-col items-center py-4 text-center">
                <ShieldCheck className="h-12 w-12 text-emerald-500" />
                <p className="mt-3 text-emerald-600 font-medium">MFA enabled successfully!</p>
                <Link to="/dashboard" className="mt-4 text-sm text-primary hover:underline">
                  Go to Dashboard
                </Link>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
