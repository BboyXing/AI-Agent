import { describe, expect, it } from "vitest";

import { readSse } from "./parser";

describe("readSse", () => {
  it("handles fragmented chunks and named events", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'event: response.output_text.delta\r\ndata: {"delta":"he',
      'llo"}\r\n\r\n',
      "data: [DONE]\n\n",
    ];
    const response = new Response(
      new ReadableStream({
        start(controller) {
          for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
          controller.close();
        },
      }),
    );
    const messages = [];
    for await (const message of readSse(response)) messages.push(message);

    expect(messages).toEqual([
      {
        event: "response.output_text.delta",
        data: '{"delta":"hello"}',
      },
      {
        event: "message",
        data: "[DONE]",
      },
    ]);
  });
});
