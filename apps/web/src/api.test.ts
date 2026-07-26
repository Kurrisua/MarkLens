import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "./api";

afterEach(() => vi.restoreAllMocks());

describe("API contract client", () => {
  it("preserves the shared error code and request id", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({
      error: { code: "MODEL_NOT_CONFIGURED", message: "未配置模型", request_id: "req_test" }
    }), { status: 503, headers: { "Content-Type": "application/json" } })));

    await expect(api.login({ email: "demo@example.com", password: "password-123" })).rejects.toMatchObject({
      code: "MODEL_NOT_CONFIGURED",
      requestId: "req_test"
    } satisfies Partial<ApiError>);
  });

  it("sends the deterministic search contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ run_id: "run-1" }), { status: 202 }));
    vi.stubGlobal("fetch", fetchMock);
    await api.createSearch("case-1");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/app/searches", expect.objectContaining({ method: "POST" }));
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ case_id: "case-1", top_k: 10 });
  });
});
