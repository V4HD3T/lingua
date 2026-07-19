export interface User {
  id: number;
  username: string;
  email: string;
  native_language: string;
  daily_review_goal: number;
  is_verified: boolean;
}

export interface Language {
  code: string;
  name: string;
}

export interface IdiomWarning {
  phrase: string;
  note: string;
}

export interface Achievement {
  code: string;
  name: string;
  description: string;
  earned_at: string;
}

export interface TranslateResult {
  source_text: string;
  translated_text: string;
  source_lang: string;
  target_lang: string;
  confidence: number;
  alternatives: string[];
  idiom_warnings: IdiomWarning[];
  new_achievements: Achievement[];
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
  grammar_note: string;
  cultural_note: string;
}

export interface VocabularyItem {
  id: number;
  word: string;
  translation: string;
  example_sentence: string;
}

export type QuestionType = "multiple_choice" | "fill_blank" | "listening" | "sentence_order";

export interface QuizQuestion {
  id: number;
  question_type: QuestionType;
  question_text: string;
  options: string[];
  audio_text?: string | null;
}

export interface Quiz {
  id: number;
  title: string;
  quiz_type: string;
  language_code: string;
  questions: QuizQuestion[];
}

export interface QuizResult {
  score: number;
  total_questions: number;
  correct_count: number;
  new_achievements: Achievement[];
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
  daily_goal: number;
  reviews_today: number;
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
  new_achievements: Achievement[];
}

export interface VocabularySuggestion {
  vocabulary_item_id: number;
  word: string;
  translation: string;
  lesson_id: number;
  frequency: number;
}
