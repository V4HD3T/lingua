import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ToastProvider } from "./context/ToastContext";
import { UpdatePrompt } from "./components/UpdatePrompt";
import { NavBar } from "./components/NavBar";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { TranslatePage } from "./pages/TranslatePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";
import { CoursesPage } from "./pages/CoursesPage";
import { CourseDetailPage } from "./pages/CourseDetailPage";
import { LessonDetailPage } from "./pages/LessonDetailPage";
import { QuizPage } from "./pages/QuizPage";
import { HistoryPage } from "./pages/HistoryPage";
import { ProgressPage } from "./pages/ProgressPage";
import { ReviewPage } from "./pages/ReviewPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <AuthProvider>
            {/* First tabbable element on every page (v0.1.1 a11y round):
                keyboard users can jump past the navigation. */}
            <a href="#main" className="skipLink">
              Skip to main content
            </a>
            <UpdatePrompt />
            <NavBar />
            <main id="main">
              {/* Inside the nav rather than around it (v0.1.21): a page
                  that throws leaves the rest of the app reachable, which
                  is the difference between "this page broke" and "the app
                  broke". */}
              <ErrorBoundary>
                <Routes>
                  <Route path="/" element={<TranslatePage />} />
                  <Route path="/login" element={<LoginPage />} />
                  <Route path="/register" element={<RegisterPage />} />
                  <Route path="/forgot-password" element={<ForgotPasswordPage />} />
                  <Route path="/reset-password" element={<ResetPasswordPage />} />
                  <Route path="/verify-email" element={<VerifyEmailPage />} />
                  <Route path="/courses" element={<CoursesPage />} />
                  <Route path="/courses/:courseId" element={<CourseDetailPage />} />
                  <Route path="/lessons/:lessonId" element={<LessonDetailPage />} />
                  <Route path="/lessons/:lessonId/quiz" element={<QuizPage />} />
                  <Route
                    path="/review"
                    element={
                      <ProtectedRoute>
                        <ReviewPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/progress"
                    element={
                      <ProtectedRoute>
                        <ProgressPage />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="/history"
                    element={
                      <ProtectedRoute>
                        <HistoryPage />
                      </ProtectedRoute>
                    }
                  />
                  {/* Catch-all. Without it an unknown address matched no
                      route and rendered an empty <main> (v0.1.21). */}
                  <Route path="*" element={<NotFoundPage />} />
                </Routes>
              </ErrorBoundary>
            </main>
          </AuthProvider>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  );
}
