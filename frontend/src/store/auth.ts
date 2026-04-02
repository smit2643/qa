import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '@/lib/types';
import { auth as authApi } from '@/lib/api';

interface AuthState {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  setToken: (token: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: false,

      setToken: (token: string) => {
        if (typeof window !== 'undefined') {
          localStorage.setItem('bug0_token', token);
        }
        set({ token });
      },

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const { access_token } = await authApi.login({ email, password });
          if (typeof window !== 'undefined') {
            localStorage.setItem('bug0_token', access_token);
          }
          set({ token: access_token });
          await get().fetchMe();
        } finally {
          set({ isLoading: false });
        }
      },

      signup: async (name: string, email: string, password: string) => {
        set({ isLoading: true });
        try {
          const { access_token } = await authApi.signup({ name, email, password });
          if (typeof window !== 'undefined') {
            localStorage.setItem('bug0_token', access_token);
          }
          set({ token: access_token });
          await get().fetchMe();
        } finally {
          set({ isLoading: false });
        }
      },

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('bug0_token');
        }
        set({ token: null, user: null });
      },

      fetchMe: async () => {
        try {
          const user = await authApi.me();
          set({ user });
        } catch {
          set({ token: null, user: null });
          if (typeof window !== 'undefined') {
            localStorage.removeItem('bug0_token');
          }
        }
      },
    }),
    {
      name: 'bug0-auth',
      partialize: (state) => ({ token: state.token, user: state.user }),
    }
  )
);
