import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import styles from "./NavBar.module.css";

export function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
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

        <nav className={styles.nav}>
          <NavLink to="/" end className={linkClass}>
            Translate
          </NavLink>
          <NavLink to="/courses" className={linkClass}>
            Courses
          </NavLink>
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
