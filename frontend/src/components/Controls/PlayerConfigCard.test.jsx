import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import PlayerConfigCard from "/src/components/Controls/PlayerConfigCard.jsx";
import { useGameContext } from "../../context/GameProvider";
import { createTestStore } from "../../test/test-utils";

vi.mock("../../context/GameProvider", () => ({
  useGameContext: vi.fn(),
}));

describe("PlayerConfigCard rollback behavior", () => {
  const api = {
    configurePlayers: vi.fn(),
    performPendingAIMove: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.configurePlayers.mockResolvedValue({ ok: true });
    api.performPendingAIMove.mockResolvedValue(undefined);
  });

  it("restores the previous config when commit fails", async () => {
    const store = createTestStore({
      gameMode: "pvai",
      boardState: { turn: "white", winner: null, pendingAiMoves: {} },
    });
    api.configurePlayers.mockRejectedValueOnce(new Error("config failed"));
    vi.mocked(useGameContext).mockReturnValue({ store, api });

    const user = userEvent.setup();
    render(<PlayerConfigCard color="white" />);

    const playerTypeSelect = screen.getByRole("combobox");
    await user.click(playerTypeSelect);
    await user.click(screen.getByRole("option", { name: /minimax/i }));

    await waitFor(() => expect(api.configurePlayers).toHaveBeenCalled());
    expect(store.getState().playerConfig.white.type).toBe("human");
    expect(playerTypeSelect).toHaveTextContent(/human/i);
  });
});
