import { useCallback, useRef, useState } from "react";

import type { ChatEndpoint } from "@llm-gateway/contracts";

import { fetchChatJson, streamChat, type ChatHistoryMessage } from "./api/stream";

export type ChatUiMessage = ChatHistoryMessage & {
  id: string;
  status: "complete" | "streaming" | "error" | "cancelled";
  model?: string;
  totalTokens?: number;
};

type SendOptions = {
  apiKey: string;
  endpoint: ChatEndpoint;
  model: string;
  stream: boolean;
  input: string;
};

export function useChatStream() {
  const [messages, setMessages] = useState<ChatUiMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setError(null);
    setStreaming(false);
  }, []);

  const send = useCallback(
    async ({ apiKey, endpoint, model, stream, input }: SendOptions) => {
      const prompt = input.trim();
      if (!prompt || streaming) return;
      const requestMessages: ChatHistoryMessage[] = [
        ...messages
          .filter((message) => message.content.trim())
          .map(({ role, content }) => ({ role, content })),
        { role: "user", content: prompt },
      ];
      const userId = crypto.randomUUID();
      const assistantId = crypto.randomUUID();
      setMessages((current) => [
        ...current,
        { id: userId, role: "user", content: prompt, status: "complete" },
        { id: assistantId, role: "assistant", content: "", status: "streaming" },
      ]);
      setError(null);
      setStreaming(true);
      const controller = new AbortController();
      abortRef.current = controller;

      const updateAssistant = (
        updater: (message: ChatUiMessage) => ChatUiMessage,
      ) => {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId ? updater(message) : message,
          ),
        );
      };

      try {
        if (stream) {
          for await (const event of streamChat({
            apiKey,
            endpoint,
            model,
            messages: requestMessages,
            signal: controller.signal,
          })) {
            if (event.type === "start") {
              updateAssistant((message) => ({
                ...message,
                model: event.model ?? message.model,
              }));
            } else if (event.type === "delta") {
              updateAssistant((message) => ({
                ...message,
                content: message.content + event.text,
              }));
            } else if (event.type === "done") {
              updateAssistant((message) => ({
                ...message,
                status: "complete",
                totalTokens: event.usage?.totalTokens,
              }));
            } else if (event.type === "error") {
              setError(event.message);
              updateAssistant((message) => ({
                ...message,
                status: "error",
              }));
            }
          }
        } else {
          const content = await fetchChatJson({
            apiKey,
            endpoint,
            model,
            messages: requestMessages,
            signal: controller.signal,
          });
          updateAssistant((message) => ({
            ...message,
            content,
            status: "complete",
          }));
        }
      } catch (reason) {
        if (controller.signal.aborted) {
          updateAssistant((message) => ({ ...message, status: "cancelled" }));
        } else {
          setError(reason instanceof Error ? reason.message : "请求失败");
          updateAssistant((message) => ({ ...message, status: "error" }));
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setStreaming(false);
      }
    },
    [messages, streaming],
  );

  return { messages, streaming, error, send, stop, clear, setError };
}
