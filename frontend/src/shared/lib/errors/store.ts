import { create } from 'zustand';

import type { ErrorStore } from './types';

/** Очередь последней ошибки запроса; читает её только ErrorNotifier (прямые notification.error запрещены). */
export const useErrorStore = create<ErrorStore>((set) => ({
  lastError: null,
  report: (error) => set({ lastError: error }),
  clear: () => set({ lastError: null }),
}));
