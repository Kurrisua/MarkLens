export type AIProvider = "openai_compatible" | "anthropic";
export type ImageStrategy = "vector" | "model";

export interface AISessionConfig {
  provider: AIProvider;
  model: string;
  apiKey: string;
  baseUrl: string;
  imageStrategy: ImageStrategy;
  visionEnabled: boolean;
}

const defaultConfig: AISessionConfig = {
  provider: "openai_compatible", model: "", apiKey: "", baseUrl: "https://api.openai.com/v1",
  imageStrategy: "vector", visionEnabled: false,
};

let current = { ...defaultConfig };

export const aiSession = {
  get: (): AISessionConfig => ({ ...current }),
  set: (next: AISessionConfig) => { current = { ...next }; },
  clear: () => { current = { ...defaultConfig }; },
  isConfigured: (): boolean => Boolean(current.model.trim() && current.apiKey.trim()),
  headers: (): HeadersInit => !current.model.trim() || !current.apiKey.trim() ? {} : {
    "X-Marklens-AI-Provider": current.provider,
    "X-Marklens-AI-Model": current.model,
    "X-Marklens-AI-Key": current.apiKey,
    "X-Marklens-AI-Base-Url": current.provider === "openai_compatible" ? current.baseUrl : "",
    "X-Marklens-Image-Strategy": current.imageStrategy,
    "X-Marklens-Vision-Enabled": String(current.visionEnabled),
  },
};
