import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiClient, ApiError } from '../api/client';
import type { LoginRequest, RegisterRequest, User } from '../types/api';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  authError: string | null;
  login: (req: LoginRequest) => Promise<void>;
  register: (req: RegisterRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);

  const refreshUser = async () => {
    try {
      const current = await apiClient.getMe();
      setUser(current);
      setAuthError(null);
    } catch (err: any) {
      setUser(null);
      // Suppress 401/404 during initial passive session check
      if (err instanceof ApiError && (err.status === 401 || err.status === 404)) {
        // Unauthenticated session, no error banner needed
      } else if (err?.message) {
        console.warn('Session verification check:', err.message);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (req: LoginRequest) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      const res = await apiClient.login(req);
      setUser(res.user);
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.message : 'Authentication failed. Please check your credentials.';
      setAuthError(msg);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (req: RegisterRequest) => {
    setIsLoading(true);
    setAuthError(null);
    try {
      await apiClient.register(req);
      // Auto-login after successful registration
      await login({ email: req.email, password: req.password });
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.message : 'Registration failed. Please verify account parameters.';
      setAuthError(msg);
      setIsLoading(false);
      throw err;
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await apiClient.logout();
    } catch (err) {
      console.warn('Logout notification error:', err);
    } finally {
      setUser(null);
      setAuthError(null);
      setIsLoading(false);
    }
  };

  const clearError = () => {
    setAuthError(null);
  };

  useEffect(() => {
    refreshUser();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        authError,
        login,
        register,
        logout,
        clearError,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
