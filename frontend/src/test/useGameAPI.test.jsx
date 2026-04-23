import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { useGameAPI } from "../hooks/useGameAPI";
import { createJsonResponse, createTextResponse, createTestStore } from "./test-utils";

describe("useGameAPI", () => {
  const fetchMock = vi.fn();
  const deferredResponse = () => {
    let resolve;
    const promise = new Promise(res => {
      resolve = res;
    });
    return { promise, resolve };
  };

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns backend payloads for config mutations", async () => {
    const store = createTestStore();
    fetchMock.mockResolvedValueOnce(createJsonResponse({ variant: "british", boardState: { turn: "white" } }));

    const { result } = renderHook(() => useGameAPI(store));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(store.getState().boardState).toBeTruthy());

    fetchMock.mockResolvedValueOnce(createJsonResponse({ cancelled: true }));
    fetchMock.mockResolvedValueOnce(
      createJsonResponse({ variant: "international", boardState: { turn: "black" }, marker: "variant" }),
    );
    await expect(result.current.changeVariant("international")).resolves.toEqual({
      variant: "international",
      boardState: { turn: "black" },
      marker: "variant",
    });
    expect(fetchMock.mock.calls[1]).toMatchObject([
      "/api/ai-cancel",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    ]);

    fetchMock.mockResolvedValueOnce(createJsonResponse({ cancelled: true }));
    fetchMock.mockResolvedValueOnce(createJsonResponse({ variant: "international", boardState: { reset: true } }));
    await expect(result.current.resetGame({ variant: "international" })).resolves.toEqual({
      variant: "international",
      boardState: { reset: true },
    });

    fetchMock.mockResolvedValueOnce(createJsonResponse({ cancelled: true }));
    fetchMock.mockResolvedValueOnce(
      createJsonResponse({ variant: "international", boardState: { configured: true }, marker: "config" }),
    );
    await expect(result.current.configurePlayers({ white: {}, black: {} })).resolves.toEqual({
      variant: "international",
      boardState: { configured: true },
      marker: "config",
    });
  });

  it.each([
    ["changeVariant", api => api.changeVariant("international")],
    ["resetGame", api => api.resetGame({ variant: "british" })],
    ["configurePlayers", api => api.configurePlayers({ white: {}, black: {} })],
  ])("rethrows failures from %s", async (_, invoke) => {
    const store = createTestStore();
    fetchMock.mockResolvedValueOnce(createJsonResponse({ variant: "british", boardState: { turn: "white" } }));

    const { result } = renderHook(() => useGameAPI(store));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(store.getState().boardState).toBeTruthy());

    fetchMock.mockResolvedValueOnce(createJsonResponse({ cancelled: true }));
    fetchMock.mockResolvedValueOnce(createTextResponse("backend rejected", false, 400));
    await expect(invoke(result.current)).rejects.toThrow("backend rejected");
    expect(store.getState().error).toBe("backend rejected");
  });

  it("ignores stale initial board responses after a newer reset response", async () => {
    const store = createTestStore();
    const initialBoard = deferredResponse();
    fetchMock.mockReturnValueOnce(initialBoard.promise);

    const { result } = renderHook(() => useGameAPI(store));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    fetchMock.mockResolvedValueOnce(createJsonResponse({ cancelled: true }));
    fetchMock.mockResolvedValueOnce(createJsonResponse({ variant: "international", marker: "reset" }));
    await expect(result.current.resetGame({ variant: "international" })).resolves.toEqual({
      variant: "international",
      marker: "reset",
    });

    initialBoard.resolve(createJsonResponse({ variant: "british", marker: "stale-board" }));
    await Promise.resolve();
    await Promise.resolve();

    expect(store.getState().boardState).toMatchObject({ marker: "reset" });
  });
});
