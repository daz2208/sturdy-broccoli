import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import api from '@/lib/api';

interface AuthState {
  isAuthenticated: boolean;
  username: string | null;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  register: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  checkAuth: () => void;
  setToken: (token: string, username: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      isAuthenticated: false,
      username: null,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          await api.login(username, password);
          set({ isAuthenticated: true, username, isLoading: false });
          return true;
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'Login failed';
          set({ error: message, isLoading: false });
          return false;
        }
      },

      register: async (username: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          await api.register(username, password);
          set({ isLoading: false });
          return true;
        } catch (err: unknown) {
          const message = err instanceof Error ? err.message : 'Registration failed';
          set({ error: message, isLoading: false });
          return false;
        }
      },

      logout: () => {
        api.logout();
        set({ isAuthenticated: false, username: null });
      },

      checkAuth: () => {
        // Check if we have a token in localStorage
        const hasToken = api.isAuthenticated();

        // If we have a token, trust the persisted state from zustand
        // The persist middleware already restored username and isAuthenticated
        if (hasToken) {
          // Only update if not already authenticated (prevents unnecessary re-renders)
          set((state) => state.isAuthenticated ? {} : { isAuthenticated: true });
        } else {
          // No token means definitely not authenticated
          set({ isAuthenticated: false, username: null });
        }
      },

      setToken: (token: string, username: string) => {
        // Set token directly (for OAuth callbacks)
        api.setToken(token);
        set({ isAuthenticated: true, username });
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({ username: state.username, isAuthenticated: state.isAuthenticated }),
    }
  )
);
