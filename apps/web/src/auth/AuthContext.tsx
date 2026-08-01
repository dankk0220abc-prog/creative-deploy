import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  AUTH_EXPIRED_EVENT,
  getSessionStatus,
  logout as logoutRequest,
  type AuthenticatedUser,
} from "../api/auth";

type AuthState =
  | { status: "anonymous"; reason: "logged_out" | "session_expired" }
  | { status: "authenticated"; user: AuthenticatedUser; expiresAt: string }
  | { status: "error" }
  | { status: "loading" };

interface AuthContextValue {
  state: AuthState;
  logout: () => Promise<void>;
  retry: () => void;
}

const defaultContext: AuthContextValue = {
  state: {
    status: "authenticated",
    user: {
      id: "00000000-0000-4000-8000-000000000001",
      display_name: "Test user",
      email: null,
    },
    expiresAt: "2099-01-01T00:00:00Z",
  },
  logout: async () => undefined,
  retry: () => undefined,
};

const AuthContext = createContext<AuthContextValue>(defaultContext);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void getSessionStatus(controller.signal)
      .then((session) => {
        if (controller.signal.aborted) {
          return;
        }
        setState(
          session.authenticated
            ? {
                status: "authenticated",
                user: session.user,
                expiresAt: session.expires_at,
              }
            : { status: "anonymous", reason: "logged_out" },
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setState({ status: "error" });
        }
      });
    return () => controller.abort();
  }, [reloadToken]);

  useEffect(() => {
    const expire = () =>
      setState({ status: "anonymous", reason: "session_expired" });
    window.addEventListener(AUTH_EXPIRED_EVENT, expire);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expire);
  }, []);

  const logout = useCallback(async () => {
    await logoutRequest();
    setState({ status: "anonymous", reason: "logged_out" });
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      logout,
      retry: () => {
        setState({ status: "loading" });
        setReloadToken((current) => current + 1);
      },
    }),
    [logout, state],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// This colocated hook intentionally consumes the provider-private context.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
