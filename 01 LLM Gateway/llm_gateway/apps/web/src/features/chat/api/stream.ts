import type {
  ChatEndpoint,
  UiStreamEvent,
  UiTokenUsage,
} from "@llm-gateway/contracts";

import { responseToError } from "../../../shared/api/client";
import { readSse } from "../../../shared/sse/parser";

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

type ChatRequest = {
  apiKey: string;
  endpoint: ChatEndpoint;
  model: string;
  messages: ChatHistoryMessage[];
  signal?: AbortSignal;
};

export async function* streamChat({
  apiKey,
  endpoint,
  model,
  messages,
  signal,
}: ChatRequest): AsyncGenerator<UiStreamEvent> {
  const isResponses = endpoint === "responses";
  const response = await fetch(
    isResponses ? "/v1/responses" : "/v1/chat/completions",
    {
      method: "POST",
      signal,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(
        isResponses
          ? {
              model,
              input: messages,
              stream: true,
            }
          : {
              model,
              messages,
              stream: true,
            },
      ),
    },
  );
  if (!response.ok) {
    const error = await responseToError(response);
    yield { type: "error", message: error.message, code: error.code };
    return;
  }

  let emittedStart = false;
  let usage: UiTokenUsage | undefined;
  let streamError = false;

  for await (const message of readSse(response)) {
    if (message.data === "[DONE]") break;
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(message.data) as Record<string, unknown>;
    } catch {
      continue;
    }
    if ("error" in payload) {
      const error = payload.error as { message?: string; code?: string };
      streamError = true;
      yield {
        type: "error",
        message: error.message ?? "流式请求失败",
        code: error.code,
      };
      return;
    }

    if (!isResponses) {
      const payloadModel = typeof payload.model === "string" ? payload.model : undefined;
      if (!emittedStart && payloadModel) {
        emittedStart = true;
        yield { type: "start", model: payloadModel };
      }
      const choices = Array.isArray(payload.choices)
        ? (payload.choices as Array<Record<string, unknown>>)
        : [];
      const delta = choices[0]?.delta as { content?: string } | undefined;
      if (delta?.content) {
        yield { type: "delta", text: delta.content };
      }
      if (payload.usage) {
        usage = mapChatUsage(payload.usage as Record<string, number>);
      }
      continue;
    }

    const type = typeof payload.type === "string" ? payload.type : message.event;
    if (type === "response.created" || type === "response.output_item.added") {
      if (!emittedStart) {
        emittedStart = true;
        yield { type: "start" };
      }
    } else if (type === "response.output_text.delta") {
      const delta = typeof payload.delta === "string" ? payload.delta : "";
      if (delta) {
        yield { type: "delta", text: delta };
      }
    } else if (type === "response.completed") {
      const responsePayload = payload.response as
        | { usage?: Record<string, number> }
        | undefined;
      if (responsePayload?.usage) {
        usage = mapResponseUsage(responsePayload.usage);
      }
    } else if (type === "error") {
      streamError = true;
      yield {
        type: "error",
        message: typeof payload.message === "string" ? payload.message : "流式请求失败",
        code: typeof payload.code === "string" ? payload.code : undefined,
      };
      return;
    }
  }
  if (!streamError) {
    if (!emittedStart) yield { type: "start" };
    yield { type: "done", usage };
  }
}

export async function fetchChatJson({
  apiKey,
  endpoint,
  model,
  messages,
  signal,
}: ChatRequest): Promise<string> {
  const isResponses = endpoint === "responses";
  const response = await fetch(
    isResponses ? "/v1/responses" : "/v1/chat/completions",
    {
      method: "POST",
      signal,
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(
        isResponses
          ? {
              model,
              input: messages,
            }
          : {
              model,
              messages,
          },
      ),
    },
  );
  if (!response.ok) {
    throw await responseToError(response);
  }
  const payload = (await response.json()) as Record<string, unknown>;
  if (isResponses) {
    return typeof payload.output_text === "string" ? payload.output_text : "";
  }
  const choices = payload.choices as
    | Array<{ message?: { content?: string } }>
    | undefined;
  return choices?.[0]?.message?.content ?? "";
}

function mapChatUsage(usage: Record<string, number>): UiTokenUsage {
  return {
    inputTokens: usage.prompt_tokens ?? 0,
    outputTokens: usage.completion_tokens ?? 0,
    totalTokens: usage.total_tokens ?? 0,
  };
}

function mapResponseUsage(usage: Record<string, number>): UiTokenUsage {
  return {
    inputTokens: usage.input_tokens ?? 0,
    outputTokens: usage.output_tokens ?? 0,
    totalTokens: usage.total_tokens ?? 0,
  };
}
