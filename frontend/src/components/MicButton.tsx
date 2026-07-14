import styles from "./MicButton.module.css";

interface MicButtonProps {
  isListening: boolean;
  onClick: () => void;
  disabled?: boolean;
  title?: string;
}

export function MicButton({ isListening, onClick, disabled, title }: MicButtonProps) {
  return (
    <button
      type="button"
      className={`${styles.button} ${isListening ? styles.listening : ""}`}
      onClick={onClick}
      disabled={disabled}
      title={title ?? (isListening ? "Listening..." : "Speak")}
      aria-label={title ?? (isListening ? "Listening" : "Speak into the microphone")}
      aria-pressed={isListening}
    >
      {isListening && <span className={styles.pulse} aria-hidden="true" />}
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
        <path d="M12 2a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v1a7 7 0 0 1-14 0v-1" />
        <line x1="12" y1="18" x2="12" y2="22" />
      </svg>
    </button>
  );
}
