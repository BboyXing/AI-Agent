import {
  createContext,
  use,
  useCallback,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

const API_KEY_STORAGE = "llm_gateway_api_key";

type GatewaySession = {
  apiKey: string | null;
  setApiKey: (value: string | null) => void;
};

const GatewaySessionContext = createContext<GatewaySession | null>(null);

function readStoredKey(): string | null {
  return window.sessionStorage.getItem(API_KEY_STORAGE);
}

export function GatewaySessionProvider({ children }: PropsWithChildren) {
  const [apiKey, setApiKeyState] = useState<string | null>(readStoredKey);

  const setApiKey = useCallback((value: string | null) => {
    const normalized = value?.trim() || null;
    if (normalized) {
      window.sessionStorage.setItem(API_KEY_STORAGE, normalized);
    } else {
      window.sessionStorage.removeItem(API_KEY_STORAGE);
    }
    setApiKeyState(normalized);
  }, []);

  const value = useMemo(() => ({ apiKey, setApiKey }), [apiKey, setApiKey]);
  return (
    <GatewaySessionContext.Provider value={value}>
      {children}
    </GatewaySessionContext.Provider>
  );
}

export function useGatewaySession(): GatewaySession {
  const context = use(GatewaySessionContext);
  if (!context) {
    throw new Error("useGatewaySession must be used inside GatewaySessionProvider");
  }
  return context;
}
