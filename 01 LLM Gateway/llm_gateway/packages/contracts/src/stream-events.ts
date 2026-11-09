export type ChatEndpoint = "chat.completions" | "responses";

export type UiTokenUsage = {
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
};

export type UiStreamEvent =
  | {
      type: "start";
      model?: string;
    }
  | {
      type: "delta";
      text: string;
    }
  | {
      type: "done";
      usage?: UiTokenUsage;
    }
  | {
      type: "error";
      message: string;
      code?: string;
    };
