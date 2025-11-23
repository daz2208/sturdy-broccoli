'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import toast from 'react-hot-toast';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, register, setToken, isLoading, error } = useAuthStore();
  const [isRegister, setIsRegister] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Handle OAuth callback
  useEffect(() => {
    const token = searchParams.get('token');
    const oauthUsername = searchParams.get('username');
    const oauthError = searchParams.get('error');

    if (oauthError) {
      const errorMessages: Record<string, string> = {
        'invalid_state': 'Session expired. Please try again.',
        'token_exchange_failed': 'Authentication failed. Please try again.',
        'no_access_token': 'Could not authenticate with provider.',
        'user_info_failed': 'Could not fetch user information.',
        'no_email': 'No email found in your account.',
        'network_error': 'Network error. Please try again.',
        'callback_failed': 'Login failed. Please try again.',
        'missing_params': 'Invalid callback. Please try again.',
      };
      toast.error(errorMessages[oauthError] || `OAuth error: ${oauthError}`);
      // Clear URL params
      router.replace('/login');
      return;
    }

    if (token && oauthUsername) {
      // Store token and redirect
      setToken(token, oauthUsername);
      toast.success(`Welcome, ${oauthUsername}!`);
      router.push('/dashboard');
    }
  }, [searchParams, router, setToken]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!username || !password) {
      toast.error('Please fill in all fields');
      return;
    }

    if (isRegister) {
      const success = await register(username, password);
      if (success) {
        toast.success('Registration successful! Please login.');
        setIsRegister(false);
      } else {
        toast.error(error || 'Registration failed');
      }
    } else {
      const success = await login(username, password);
      if (success) {
        toast.success('Welcome back!');
        router.push('/dashboard');
      } else {
        toast.error(error || 'Login failed');
      }
    }
  };

  const handleOAuthLogin = (provider: 'google' | 'github') => {
    // Redirect to backend OAuth endpoint
    window.location.href = `${API_URL}/auth/${provider}/login`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-dark">
      <div className="w-full max-w-md p-8 bg-dark-100 rounded-xl border border-dark-300">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary mb-2">SyncBoard 3.0</h1>
          <p className="text-gray-500">AI-Powered Knowledge Management</p>
        </div>

        {/* OAuth Buttons */}
        <div className="space-y-3 mb-6">
          <button
            onClick={() => handleOAuthLogin('google')}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 bg-white hover:bg-gray-100 text-gray-800 rounded-lg transition-colors font-medium"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </button>

          <button
            onClick={() => handleOAuthLogin('github')}
            className="w-full flex items-center justify-center gap-3 py-3 px-4 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors font-medium"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path
                fillRule="evenodd"
                clipRule="evenodd"
                d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z"
              />
            </svg>
            Continue with GitHub
          </button>
        </div>

        {/* Divider */}
        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-dark-300"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-4 bg-dark-100 text-gray-500">or continue with email</span>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="input"
              placeholder="Enter username"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-400 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
              placeholder="Enter password"
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full btn btn-primary disabled:opacity-50"
          >
            {isLoading ? 'Loading...' : isRegister ? 'Register' : 'Login'}
          </button>
        </form>

        <div className="mt-6 text-center">
          <button
            onClick={() => setIsRegister(!isRegister)}
            className="text-sm text-gray-400 hover:text-primary"
          >
            {isRegister ? 'Already have an account? Login' : "Don't have an account? Register"}
          </button>
        </div>
      </div>
    </div>
  );
}
