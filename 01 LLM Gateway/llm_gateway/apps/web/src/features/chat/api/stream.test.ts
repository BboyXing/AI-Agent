import { afterEach, describe, expect, it, vi } from "vitest";

import { streamChat, type ChatHistoryMessage } from "./stream";

const messages: ChatHistoryMessage[] = [{ role: "user", content: "hi" }];

function sseResponse(frames: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const frame of frames) controller.enqueue(encoder.encode(frame));
        controller.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("streamChat", () => {
  it("maps chat completion deltas and usage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          'data: {"model":"deepseek-chat","choices":[{"delta":{"role":"assistant"}}]}\n\n',
          'data: {"model":"deepseek-chat","choices":[{"delta":{"content":"hello"}}]}\n\n',
          'data: {"choices":[],"usage":{"prompt_tokens":3,"completion_tokens":2,',
          '"total_tokens":5}}\n\n',
          "data: [DONE]\n\n",
        ]),
      ),
    );

    const events = [];
    for await (const event of streamChat({
      apiKey: "test",
      endpoint: "chat.completions",
      model: "default",
      messages,
    })) {
      events.push(event);
    }

    expect(events).toEqual([
      { type: "start", model: "deepseek-chat" },
      { type: "delta", text: "hello" },
      {
        type: "done",
        usage: { inputTokens: 3, outputTokens: 2, totalTokens: 5 },
      },
    ]);
  });

  it("maps named Responses API events", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        sseResponse([
          'event: response.created\ndata: {"type":"response.created"}\n\n',
          'event: response.output_text.delta\ndata: {"type":"response.output_text.delta",',
          '"delta":"world"}\n\n',
          'event: response.completed\ndata: {"type":"response.completed","response":',
          '{"usage":{"input_tokens":4,"output_tokens":1,"total_tokens":5}}}\n\n',
        ]),
      ),
    );

    const events = [];
    for await (const event of streamChat({
      apiKey: "test",
      endpoint: "responses",
      model: "default",
      messages,
    })) {
      events.push(event);
    }

    expect(events).toEqual([
      { type: "start" },
      { type: "delta", text: "world" },
      {
        type: "done",
        usage: { inputTokens: 4, outputTokens: 1, totalTokens: 5 },
      },
    ]);
  });
});
