export interface User {
  id: number;
  username: string;
  email: string;
  native_language: string;
}

export interface Language {
  code: string;
  name: string;
}

export interface IdiomWarning {
  phrase: string;
  note: string;
}

export interface TranslateResult {
  source_text: string;
  translated_text: string;
  source_lang: string;
  target_lang: string;
  confidence: number;
  alternatives: string[];
  idiom_warnings: IdiomWarning[];
}

export interface Course {
  id: number;
  language_code: string;
  title: string;
  level: string;
  description: string;
}

export interface Lesson {
  id: number;
  course_id: number;
  title: string;
  content: string;
  order: number;
  language_code: string;
}

export interface VocabularyItem {
  id: number;
  word: string;
  translation: string;
  example_sentence: string;
}

export interface QuizQuestion {
  id: number;
  question_text: string;
  options: string[];
}

export interface Quiz {
  id: number;
  title: string;
  quiz_type: string;
  questions: QuizQuestion[];
}

export interface QuizResult {
  score: number;
  total_questions: number;
  correct_count: number;
}

export interface CourseProgress {
  course_id: number;
  course_title: string;
  total_lessons: number;
  completed_lessons: number;
  completion_percentage: number;
}

export interface UserStats {
  current_streak: number;
  longest_streak: number;
  total_translations: number;
  total_quiz_attempts: number;
  average_quiz_score: number;
  courses: CourseProgress[];
}

export interface ReviewQueueItem {
  vocabulary_item_id: number;
  word: string;
  translation: string;
  example_sentence: string;
  lesson_id: number;
  language_code: string;
  is_new: boolean;
}

export interface ReviewResult {
  vocabulary_item_id: number;
  repetitions: number;
  ease_factor: number;
  interval_days: number;
  next_review_date: string;
}

export interface VocabularySuggestion {
  vocabulary_item_id: number;
  word: string;
  translation: string;
  lesson_id: number;
  frequency: number;
}
