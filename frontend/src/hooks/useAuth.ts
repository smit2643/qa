'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/auth';

export function useAuth(redirectIfUnauthenticated = true) {
  const router = useRouter();
  const { token, user, isLoading, login, logout, fetchMe } = useAuthStore();

  useEffect(() => {
    if (token && !user) {
      fetchMe();
    }
  }, [token, user, fetchMe]);

  useEffect(() => {
    if (!isLoading && !token && redirectIfUnauthenticated) {
      router.push('/login');
    }
  }, [token, isLoading, redirectIfUnauthenticated, router]);

  return { token, user, isLoading, login, logout };
}
