import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { UserCreate, UserLogin, UserResponse } from "../types";
import { fetchMe, loginUser, registerUser } from "../api/auth";
import { apiClient } from "../api/client";
import { clearStoredToken, getStoredToken, setStoredToken } from "../lib/token";

export interface AuthContextType {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: UserLogin) => Promise<void>;
  register: (userData: UserCreate) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    clearStoredToken();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const userProfile = await fetchMe();
      setUser(userProfile);
    } catch (err) {
      console.warn("Session restore failed, clearing token:", err);
      clearStoredToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Register automatic session clearing on 401
    apiClient.setOnUnauthorized(() => {
      logout();
    });

    refreshUser();
  }, [refreshUser, logout]);

  const login = async (credentials: UserLogin) => {
    setIsLoading(true);
    try {
      const response = await loginUser(credentials);
      if (response.token?.access_token) {
        setStoredToken(response.token.access_token);
        setUser(response.user);
      } else {
        throw new Error("Invalid authentication response received from server.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (userData: UserCreate) => {
    setIsLoading(true);
    try {
      await registerUser(userData);
      // Automatically log the user in upon successful registration
      const loginRes = await loginUser({
        email: userData.email,
        password: userData.password,
      });
      if (loginRes.token?.access_token) {
        setStoredToken(loginRes.token.access_token);
        setUser(loginRes.user);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
