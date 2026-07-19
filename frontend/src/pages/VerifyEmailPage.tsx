import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api/auth";
import { ApiError } from "../api/client";
import { LoadingState } from "../components/StatusMessage";
import styles from "./AuthPage.module.css";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("This link is missing its token. Please use the link from your email.");
      return;
    }
    verifyEmail(token)
      .then(() => setStatus("success"))
      .catch((err) => {
        setStatus("error");
        setError(err instanceof ApiError ? err.message : "This verification link is invalid or has expired.");
      });
  }, [token]);

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h1>Email verification</h1>

        {status === "loading" && <LoadingState label="Verifying your email" />}
        {status === "success" && <p className={styles.subtitle}>Your email has been verified ✓</p>}
        {status === "error" && <div className={styles.errorText}>{error}</div>}

        <p className={styles.footer}>
          <Link to="/">Go to Lingua</Link>
        </p>
      </div>
    </div>
  );
}
