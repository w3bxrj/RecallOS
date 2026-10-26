import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiGetMe, apiLogin, apiRegister } from '../api/auth';
import type { LoginPayload, RegisterPayload } from '../api/auth';
import { TOKEN_STORAGE_KEY } from '../api/client';
import type { User } from '../api/types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_STORAGE_KEY));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await apiGetMe();
      setUser(currentUser);
    } catch {
      // If fetching me fails on load, token is likely invalid or expired
      setUser(null);
      setToken(null);
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    }
  }, []);

  // On initial mount, verify token with backend if present
  useEffect(() => {
    async function initAuth() {
      const storedToken = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (storedToken) {
        setToken(storedToken);
        try {
          const currentUser = await apiGetMe();
          setUser(currentUser);
        } catch {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          setToken(null);
          setUser(null);
        }
      } else {
        setUser(null);
        setToken(null);
      }
      setIsLoading(false);
    }

    initAuth();
  }, []);

  const login = useCallback(
    async (payload: LoginPayload) => {
      const res = await apiLogin(payload);
      localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token);
      setToken(res.access_token);
      const currentUser = await apiGetMe();
      setUser(currentUser);
    },
    []
  );

  const register = useCallback(
    async (payload: RegisterPayload) => {
      await apiRegister(payload);
      // Auto login after registration
      const loginRes = await apiLogin({
        email: payload.email,
        password: payload.password,
      });
      localStorage.setItem(TOKEN_STORAGE_KEY, loginRes.access_token);
      setToken(loginRes.access_token);
      const currentUser = await apiGetMe();
      setUser(currentUser);
    },
    []
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
