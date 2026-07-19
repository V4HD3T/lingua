import { useState } from "react";
import styles from "./SentenceOrderInput.module.css";

interface SentenceOrderInputProps {
  words: string[];
  onChange: (orderedAnswer: string) => void;
}

export function SentenceOrderInput({ words, onChange }: SentenceOrderInputProps) {
  const [available, setAvailable] = useState(words);
  const [built, setBuilt] = useState<string[]>([]);

  function addWord(index: number) {
    const word = available[index];
    const nextAvailable = available.filter((_, i) => i !== index);
    const nextBuilt = [...built, word];
    setAvailable(nextAvailable);
    setBuilt(nextBuilt);
    onChange(nextBuilt.join(" "));
  }

  function removeWord(index: number) {
    const word = built[index];
    const nextBuilt = built.filter((_, i) => i !== index);
    setBuilt(nextBuilt);
    setAvailable([...available, word]);
    onChange(nextBuilt.join(" "));
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.builtRow}>
        {built.length === 0 && (
          <span className={styles.placeholder}>Tap words below, in order</span>
        )}
        {built.map((word, i) => (
          <button
            key={`${word}-${i}`}
            type="button"
            className={styles.builtWord}
            onClick={() => removeWord(i)}
          >
            {word}
          </button>
        ))}
      </div>
      <div className={styles.availableRow}>
        {available.map((word, i) => (
          <button
            key={`${word}-${i}`}
            type="button"
            className={styles.availableWord}
            onClick={() => addWord(i)}
          >
            {word}
          </button>
        ))}
      </div>
    </div>
  );
}
