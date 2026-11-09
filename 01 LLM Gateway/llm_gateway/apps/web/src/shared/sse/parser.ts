export type SseMessage = {
  event: string;
  data: string;
  id?: string;
};

export async function* readSse(response: Response): AsyncGenerator<SseMessage> {
  if (!response.body) {
    throw new Error("浏览器未收到可读取的流式响应");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const parseBlock = (block: string): SseMessage | null => {
    if (!block.trim()) return null;
    let event = "message";
    let id: string | undefined;
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
      else if (line.startsWith("id:")) id = line.slice(3).trim();
    }
    return data.length ? { event, data: data.join("\n"), id } : null;
  };

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    buffer = buffer.replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const message = parseBlock(buffer.slice(0, boundary));
      if (message) yield message;
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");
    }
    if (done) break;
  }
  const finalMessage = parseBlock(buffer);
  if (finalMessage) yield finalMessage;
}

export async function consumeSse(
  response: Response,
  onMessage: (message: SseMessage) => void,
): Promise<void> {
  for await (const message of readSse(response)) {
    onMessage(message);
  }
}
