import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { createTestStore } from "./test-utils";

const mockedContext = vi.hoisted(() => ({ current: null }));

vi.mock("../context/GameProvider", () => ({
  useGameContext: () => mockedContext.current,
}));

vi.mock("../components/Board/Board", () => ({
  default: () => <div>Board</div>,
}));

vi.mock("../components/Controls/GameSetupCard", () => ({
  default: () => <div>GameSetupCard</div>,
}));

vi.mock("../components/Controls/PlayerConfigCard", () => ({
  default: ({ color }) => <div>PlayerConfigCard {color}</div>,
}));

vi.mock("../components/Dialogs/GameOverDialog", () => ({
  default: () => <div>GameOverDialog</div>,
}));

vi.mock("../components/Controls/EvaluationPanel", () => ({
  default: ({ isEvaluateTabActive }) => <div>EvaluationPanel {String(isEvaluateTabActive)}</div>,
}));

const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

import GamePage from "../pages/GamePage";

describe("GamePage", () => {
  beforeEach(() => {
    consoleErrorSpy.mockClear();
  });

  afterEach(() => {
    mockedContext.current = null;
  });

  it("fetches system info on mount and keeps Evaluate disabled outside AI-vs-AI mode", async () => {
    const store = createTestStore({ gameMode: "pvai", systemInfo: null });
    const api = {
      fetchSystemInfo: vi.fn().mockResolvedValue({ recommendedMaxWorkers: 6 }),
    };
    mockedContext.current = { store, api };

    render(<GamePage />);

    await waitFor(() => expect(api.fetchSystemInfo).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(store.getState().systemInfo).toEqual({ recommendedMaxWorkers: 6 }),
    );

    expect(screen.getByRole("tab", { name: /evaluate/i })).toBeDisabled();
  });

  it("shows the lazy evaluation panel in AI-vs-AI mode and returns to Play when mode changes", async () => {
    const user = userEvent.setup();
    const store = createTestStore({ gameMode: "aivai", systemInfo: null });
    const api = {
      fetchSystemInfo: vi.fn().mockResolvedValue({ recommendedMaxWorkers: 8 }),
    };
    mockedContext.current = { store, api };

    render(<GamePage />);

    await user.click(screen.getByRole("tab", { name: /evaluate/i }));
    expect(await screen.findByText("EvaluationPanel true")).toBeInTheDocument();

    await act(async () => {
      store.getState().setGameMode("pvp");
    });

    await waitFor(() =>
      expect(screen.queryByText("EvaluationPanel true")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("GameSetupCard")).toBeInTheDocument();
  });

  it("logs system info failures instead of swallowing them silently", async () => {
    const store = createTestStore({ gameMode: "pvai", systemInfo: null });
    const api = {
      fetchSystemInfo: vi.fn().mockRejectedValue(new Error("system info down")),
    };
    mockedContext.current = { store, api };

    render(<GamePage />);

    await waitFor(() => expect(api.fetchSystemInfo).toHaveBeenCalledTimes(1));
    await waitFor(() =>
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Failed to fetch system info",
        expect.objectContaining({ message: "system info down" }),
      ),
    );
  });
});
