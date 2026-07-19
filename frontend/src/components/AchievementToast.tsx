import type { Achievement } from "../types";
import styles from "./AchievementToast.module.css";

export function AchievementToast({ achievements }: { achievements: Achievement[] }) {
  if (achievements.length === 0) return null;

  return (
    <div className={styles.stack}>
      {achievements.map((a) => (
        <div key={a.code} className={styles.toast} role="status">
          <span className={styles.icon} aria-hidden="true">
            🏅
          </span>
          <div>
            <span className={styles.title}>Badge earned: {a.name}</span>
            <span className={styles.description}>{a.description}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
