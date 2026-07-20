import { useEffect, useState } from "react";
import { fetchTranslationHistory } from "../api/translate";
import { CopyButton } from "../components/CopyButton";
import { LoadingState, ErrorState } from "../components/StatusMessage";
import type { TranslateResult } from "../types";
import styles from "./HistoryPage.module.css";

const PAGE_SIZE = 20;

export function HistoryPage() {
  const [history, setHistory] = useState<TranslateResult[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  useEffect(() => {
    fetchTranslationHistory(PAGE_SIZE, 0)
      .then((page) => {
        setHistory(page.items);
        setTotal(page.total);
      })
      .catch(() => setError("Something went wrong loading your history."));
  }, []);

  async function handleLoadMore() {
    if (!history) return;
    setIsLoadingMore(true);
    try {
      // Offset by what's already on screen, so the next page continues
      // exactly where the list ends. If new translations were made in
      // another tab meanwhile, the newest-first ordering shifts rows
      // *down* -- worst case is one repeated row, never a silent gap.
      const page = await fetchTranslationHistory(PAGE_SIZE, history.length);
      setHistory([...history, ...page.items]);
      setTotal(page.total);
    } catch {
      setError("Something went wrong loading more history.");
    } finally {
      setIsLoadingMore(false);
    }
  }

  const hasMore = history !== null && history.length < total;

  return (
    <div className={styles.page}>
      <h1>Translation history</h1>
      <p className={styles.subtitle}>Translations you've made in the past.</p>

      {error && <ErrorState message={error} />}
      {!error && !history && <LoadingState label="Loading history" />}

      {history && history.length === 0 && (
        <p className={styles.empty}>You haven't translated anything yet.</p>
      )}

      <div className={styles.list}>
        {history?.map((item, index) => (
          <div key={index} className={styles.row}>
            <div className={styles.textCol}>
              <span className={styles.langTag}>{item.source_lang}</span>
              <p>{item.source_text}</p>
            </div>
            <span className={styles.arrow}>→</span>
            <div className={styles.textCol}>
              <span className={styles.langTag}>{item.target_lang}</span>
              <p>{item.translated_text}</p>
            </div>
            <div className={styles.rowCopy}>
              <CopyButton text={item.translated_text} label="Copy translation" />
            </div>
          </div>
        ))}
      </div>

      {hasMore && (
        <div className={styles.loadMoreRow}>
          <button
            type="button"
            className={styles.loadMoreButton}
            onClick={handleLoadMore}
            disabled={isLoadingMore}
          >
            {isLoadingMore ? "Loading…" : "Load more"}
          </button>
          <span className={styles.countNote}>
            Showing {history?.length} of {total}
          </span>
        </div>
      )}
    </div>
  );
}
