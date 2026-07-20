import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import styles from "./ToastContext.module.css";

/* General toast system (v0.1.1). AchievementToast stays as its own thing on
   purpose: it's an inline, in-page celebration tied to where the badge was
   earned. This system is the app-wide transient channel ("Copied", "Daily
   goal updated", "Signed out") -- fixed to the viewport corner, auto-
   dismissing, screen-reader announced. */

type ToastKind = "success" | "error";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastContextValue {
  success: (message: string) => void;
  error: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const SUCCESS_DISMISS_MS = 4000;
const ERROR_DISMISS_MS = 7000; // errors linger longer -- people need time to read what went wrong

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextIdRef = useRef(0);
  const timersRef = useRef(new Map<number, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = ++nextIdRef.current;
      setToasts((current) => [...current, { id, kind, message }]);
      const timer = setTimeout(
        () => dismiss(id),
        kind === "error" ? ERROR_DISMISS_MS : SUCCESS_DISMISS_MS
      );
      timersRef.current.set(id, timer);
    },
    [dismiss]
  );

  const value: ToastContextValue = {
    success: useCallback((message: string) => push("success", message), [push]),
    error: useCallback((message: string) => push("error", message), [push]),
  };

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live on the container: additions are announced without moving
          focus. Errors additionally get role="alert" for assertive reading. */}
      <div className={styles.viewport} aria-live="polite" role="status">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`${styles.toast} ${toast.kind === "error" ? styles.error : styles.success}`}
            role={toast.kind === "error" ? "alert" : undefined}
          >
            <span className={styles.message}>{toast.message}</span>
            <button
              type="button"
              className={styles.dismiss}
              onClick={() => dismiss(toast.id)}
              aria-label="Dismiss notification"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used inside a ToastProvider");
  }
  return context;
}
