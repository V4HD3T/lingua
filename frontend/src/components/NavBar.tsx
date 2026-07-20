import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import { ThemeToggle } from "./ThemeToggle";
import styles from "./NavBar.module.css";

export function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  async function handleLogout() {
    await logout();
    toast.success("Signed out");
    navigate("/");
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.link} ${styles.linkActive}` : styles.link;

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <NavLink to="/" className={styles.brand}>
          <span className={styles.brandMark}>訳</span>
          Lingua
        </NavLink>

        <nav className={styles.nav} aria-label="Main">
          <NavLink to="/" end className={linkClass}>
            Translate
          </NavLink>
          <NavLink to="/courses" className={linkClass}>
            Courses
          </NavLink>
          {user && (
            <NavLink to="/review" className={linkClass}>
              Review
            </NavLink>
          )}
          {user && (
            <NavLink to="/progress" className={linkClass}>
              Progress
            </NavLink>
          )}
          {user && (
            <NavLink to="/history" className={linkClass}>
              History
            </NavLink>
          )}
        </nav>

        <div className={styles.authArea}>
          <ThemeToggle />
          {user ? (
            <>
              <span className={styles.username}>{user.username}</span>
              <button type="button" className={styles.logoutButton} onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login" className={styles.link}>
                Log in
              </NavLink>
              <NavLink to="/register" className={styles.ctaLink}>
                Sign up
              </NavLink>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
