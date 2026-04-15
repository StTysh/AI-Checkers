import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EvaluationPanel from "./EvaluationPanel.jsx";
import { useGameContext } from "../../context/GameProvider";
import { DEFAULT_PLAYER_CONFIG } from "../../utils/constants";
import { createTestStore } from "../../test/test-utils";

vi.mock("../../context/GameProvider", () => ({
  useGameContext: vi.fn(),
}));

const clone = value => JSON.parse(JSON.stringify(value));

const createAiConfig = overrides => ({
  white: {
    ...clone(DEFAULT_PLAYER_CONFIG.white),
    type: "minimax",
    depth: 4,
    timeLimitMs: 1000,
    ...overrides?.white,
  },
  black: {
    ...clone(DEFAULT_PLAYER_CONFIG.black),
    type: "mcts",
    iterations: 500,
    rolloutDepth: 80,
    rolloutPolicy: "random",
    ...overrides?.black,
  },
});

describe("EvaluationPanel", () => {
  const api = {
    startEvaluation: vi.fn(),
    getEvaluationStatus: vi.fn(),
    stopEvaluation: vi.fn(),
    getEvaluationResults: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.startEvaluation.mockResolvedValue({
      evaluationId: "eval-1",
      running: true,
      completedGames: 0,
      totalGames: 10,
      score: { whiteWins: 0, blackWins: 0, draws: 0 },
      summary: { avgMoves: 0, avgDuration: 0, avgMoveTimeWhite: 0, avgMoveTimeBlack: 0 },
      results: [],
    });
    api.getEvaluationStatus.mockResolvedValue({
      evaluationId: "eval-1",
      running: false,
      completedGames: 10,
      totalGames: 10,
      score: { whiteWins: 6, blackWins: 2, draws: 2 },
      summary: { avgMoves: 20, avgDuration: 1, avgMoveTimeWhite: 0.1, avgMoveTimeBlack: 0.1 },
      results: [],
    });
    api.stopEvaluation.mockResolvedValue({ running: false });
    api.getEvaluationResults.mockResolvedValue("csv");
    localStorage.clear();
  });

  it("syncs from live Play state on activation and freezes the running payload", async () => {
    const store = createTestStore({
      gameMode: "aivai",
      variant: "british",
      playerConfig: createAiConfig(),
    });
    vi.mocked(useGameContext).mockReturnValue({ store, api });

    const { rerender } = render(<EvaluationPanel isEvaluateTabActive={false} />);

    store.setState({
      variant: "international",
      playerConfig: createAiConfig({
        white: { type: "mcts", iterations: 700, rolloutDepth: 60, rolloutPolicy: "heuristic" },
        black: { type: "minimax", depth: 6, timeLimitMs: 2000 },
      }),
    });

    rerender(<EvaluationPanel isEvaluateTabActive />);

    await waitFor(() => {
      expect(screen.getByText(/White: MCTS iter=700, depth=60, policy=heuristic/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Black: Minimax d=6, id=off, t=2000ms, p=1/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /run evaluation/i }));

    await waitFor(() => expect(api.startEvaluation).toHaveBeenCalledTimes(1));
    expect(api.startEvaluation.mock.calls[0][0]).toMatchObject({
      variant: "international",
      white: expect.objectContaining({ type: "mcts", iterations: 700 }),
      black: expect.objectContaining({ type: "minimax", depth: 6 }),
    });

    store.setState({
      variant: "british",
      playerConfig: createAiConfig({
        white: { type: "minimax", depth: 2, timeLimitMs: 500 },
        black: { type: "mcts", iterations: 50, rolloutDepth: 20, rolloutPolicy: "random" },
      }),
    });

    rerender(<EvaluationPanel isEvaluateTabActive />);

    expect(screen.getByText(/White: MCTS iter=700, depth=60, policy=heuristic/i)).toBeInTheDocument();
    expect(screen.getByText(/Black: Minimax d=6, id=off, t=2000ms, p=1/i)).toBeInTheDocument();
  });

  it("stops the currently active sweep evaluation", async () => {
    const store = createTestStore({
      gameMode: "aivai",
      variant: "british",
      playerConfig: createAiConfig(),
    });
    vi.mocked(useGameContext).mockReturnValue({ store, api });

    render(<EvaluationPanel isEvaluateTabActive />);

    fireEvent.click(screen.getByRole("button", { name: /sweep mode/i }));
    fireEvent.click(screen.getByRole("button", { name: /run sweep/i }));

    await waitFor(() => expect(api.startEvaluation).toHaveBeenCalledWith(expect.objectContaining({ variant: "british" })));

    fireEvent.click(screen.getByRole("button", { name: /stop sweep/i }));

    await waitFor(() => expect(api.stopEvaluation).toHaveBeenCalledWith("eval-1"));
  });

  it("disables evaluation actions when a human player is present in the draft", () => {
    const store = createTestStore({
      gameMode: "aivai",
      variant: "british",
      playerConfig: createAiConfig({
        white: { type: "human" },
      }),
    });
    vi.mocked(useGameContext).mockReturnValue({ store, api });

    render(<EvaluationPanel isEvaluateTabActive />);

    expect(screen.getByRole("button", { name: /run evaluation/i })).toBeDisabled();
  });
});
