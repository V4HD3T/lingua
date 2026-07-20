import { useToast } from "../context/ToastContext";
import styles from "./CopyButton.module.css";

export function CopyButton({ text, label = "Copy to clipboard" }: { text: string; label?: string }) {
  const toast = useToast();

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("Copied to clipboard");
    } catch {
      // Clipboard access can be blocked (permissions, insecure context);
      // say so instead of failing silently.
      toast.error("Couldn't copy — clipboard access was blocked.");
    }
  }

  return (
    <button type="button" className={styles.button} onClick={handleCopy} aria-label={label} title={label}>
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
      </svg>
    </button>
  );
}
