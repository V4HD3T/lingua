import { apiRequest } from "./client";
import type { Course, Lesson, VocabularyItem } from "../types";

export function listCourses(): Promise<Course[]> {
  return apiRequest<Course[]>("/courses");
}

export function getCourse(courseId: number): Promise<Course> {
  return apiRequest<Course>(`/courses/${courseId}`);
}

export function listLessons(courseId: number): Promise<Lesson[]> {
  return apiRequest<Lesson[]>(`/courses/${courseId}/lessons`);
}

export function getLesson(lessonId: number): Promise<Lesson> {
  return apiRequest<Lesson>(`/lessons/${lessonId}`);
}

export function listVocabulary(lessonId: number): Promise<VocabularyItem[]> {
  return apiRequest<VocabularyItem[]>(`/lessons/${lessonId}/vocabulary`);
}
