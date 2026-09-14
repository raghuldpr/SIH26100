const TOKEN_KEY = "sih26100_auth_token";

/**
 * Retrieves the stored JWT access token.
 */
export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

/**
 * Persists the JWT access token in localStorage.
 */
export function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch (err) {
    console.error("Failed to persist auth token:", err);
  }
}

/**
 * Removes the stored JWT access token.
 */
export function clearStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch (err) {
    console.error("Failed to clear auth token:", err);
  }
}
