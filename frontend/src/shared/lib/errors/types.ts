/** Ошибка запроса, показанная пользователю: текст без стек-трейса и без данных запроса. */
export interface ReportedError {
  id: number;
  messageKey: string;
  requestId?: string;
}

export interface ErrorStore {
  lastError: ReportedError | null;
  report: (error: ReportedError) => void;
  clear: () => void;
}
