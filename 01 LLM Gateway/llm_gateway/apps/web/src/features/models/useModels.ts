import { useEffect, useState } from "react";

import { fetchModels } from "../../shared/api/client";
import type { ModelRouteInfo } from "../../shared/api/types";

export function useModels(apiKey: string | null) {
  const [models, setModels] = useState<ModelRouteInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiKey) {
      setModels([]);
      setError(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    fetchModels(apiKey, controller.signal)
      .then((response) => setModels(response.data))
      .catch((reason: unknown) => {
        if (!controller.signal.aborted) {
          setError(reason instanceof Error ? reason.message : "模型列表加载失败");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [apiKey]);

  return { models, loading, error };
}
