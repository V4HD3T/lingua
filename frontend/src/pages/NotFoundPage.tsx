import { Link } from "react-router-dom";
import styles from "./NotFoundPage.module.css";

/**
 * The catch-all route (v0.1.21). Without one, `<Routes>` matched nothing
 * for an unknown address and rendered nothing: the nav bar stayed, the
 * main region was empty, and the page looked like something that had
 * failed to load rather than an address that doesn't exist. A stale
 * bookmark or a mistyped URL both landed there.
 *
 * The links matter more than the message — a dead end is only useful if
 * it points somewhere, and these are the three places anyone arriving
 * here actually wanted.
 */
export function NotFoundPage() {
  return (
    <div className={styles.page}>
      <span className={styles.code} aria-hidden="true">
        404
      </span>
      <h1>This page doesn't exist</h1>
      <p className={styles.subtitle}>
        The link may be out of date, or the address may have a typo in it.
      </p>
      <div className={styles.links}>
        <Link to="/" className={styles.link}>
          Translate
        </Link>
        <Link to="/courses" className={styles.link}>
          Courses
        </Link>
        <Link to="/review" className={styles.link}>
          Review
        </Link>
      </div>
    </div>
  );
}
