import { apiClient } from "./client";
import { AuthResponse, UserCreate, UserLogin, UserResponse } from "../types";

/**
 * Authenticates user credentials and returns JWT access token.
 */
export async function loginUser(credentials: UserLogin): Promise<AuthResponse> {
  return apiClient.post<AuthResponse>("/auth/login", credentials, {
    requiresAuth: false,
  });
}

/**
 * Registers a new user account with initial role.
 */
export async function registerUser(userData: UserCreate): Promise<UserResponse> {
  return apiClient.post<UserResponse>("/auth/register", userData, {
    requiresAuth: false,
  });
}

/**
 * Fetches the currently authenticated user profile using Bearer JWT.
 */
export async function fetchMe(): Promise<UserResponse> {
  return apiClient.get<UserResponse>("/auth/me", {
    requiresAuth: true,
  });
}
