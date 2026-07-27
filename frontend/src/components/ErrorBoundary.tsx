import { Component, type ErrorInfo, type ReactNode } from "react";
import styles from "./ErrorBoundary.module.css";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * The last line between a render-time exception and a white screen
 * (v0.1.21).
 *
 * React's behaviour on an uncaught render error is to unmount the entire
 * tree — deliberately, on the grounds that a half-rendered UI is worse
 * than none. Without a boundary above the routes, one thrown error in one
 * page therefore took the whole app with it, nav bar included, leaving a
 * blank document with no message, no way back, and nothing in the UI to
 * suggest reloading would help.
 *
 * Deliberately a class: `componentDidCatch` and `getDerivedStateFromError`
 * have no hook equivalents, and React still provides none — this is the
 * one place in the codebase where a class component is the only option
 * rather than a stylistic choice.
 *
 * It sits *inside* the router so the nav bar survives, which is the
 * difference between "this page broke" and "the app broke".
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // The component stack is the part that actually locates the failure,
    // and React only hands it to this method -- it isn't on the Error.
    console.error("Unhandled render error:", error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className={styles.page} role="alert">
        <h1>Something went wrong on this page</h1>
        <p className={styles.subtitle}>
          The rest of the app is still fine — reloading usually clears it.
        </p>
        <button
          type="button"
          className={styles.reload}
          onClick={() => window.location.reload()}
        >
          Reload the page
        </button>
        {/* The message, not the stack: enough for someone to quote in a
            bug report, without a wall of minified frames. */}
        <details className={styles.details}>
          <summary>Technical details</summary>
          <p className={styles.message}>{error.message}</p>
        </details>
      </div>
    );
  }
}
