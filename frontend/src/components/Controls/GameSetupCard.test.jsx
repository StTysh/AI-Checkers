import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GameSetupCard from "./GameSetupCard.jsx";
import { useGameContext } from "../../context/GameProvider";
import { createTestStore } from "../../test/test-utils";

vi.mock("../../context/GameProvider", () => ({
  useGameContext: vi.fn(),
}));

describe("GameSetupCard rollback behavior", () => {
  const api = {
    configurePlayers: vi.fn(),
    changeVariant: vi.fn(),
    resetGame: vi.fn(),
    undoMove: vi.fn(),
    runAITurns: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    api.configurePlayers.mockResolvedValue({ ok: true });
    api.changeVariant.mockResolvedValue({ ok: true });
    api.resetGame.mockResolvedValue({ ok: true });
    api.undoMove.mockResolvedValue({ ok: true });
    api.runAITurns.mockResolvedValue(undefined);
  });

  it("rolls back variant changes when the backend rejects them", async () => {
    const store = createTestStore({ boardState: { canUndo: false } });
    api.changeVariant.mockRejectedValueOnce(new Error("variant failed"));
    vi.mocked(useGameContext).mockReturnValue({ store, api });

    const user = userEvent.setup();
    render(<GameSetupCard />);

    const [, variantSelect] = screen.getAllByRole("combobox");
    await user.click(variantSelect);
    await user.click(screen.getByRole("option", { name: /international/i }));

    await waitFor(() => expect(api.changeVariant).toHaveBeenCalledWith("international"));
    expect(store.getState().variant).toBe("british");
    expect(variantSelect).toHaveTextContent(/british/i);
  });

  it("rolls back mode changes when backend config persistence fails", async () => {
    const store = createTestStore({ boardState: { canUndo: false } });
    api.configurePlayers.mockRejectedValueOnce(new Error("mode failed"));
    vi.mocked(useGameContext).mockReturnValue({ store, api });

    const user = userEvent.setup();
    render(<GameSetupCard />);

    const [modeSelect] = screen.getAllByRole("combobox");
    await user.click(modeSelect);
    await user.click(screen.getByRole("option", { name: /player vs ai/i }));

    await waitFor(() => expect(api.configurePlayers).toHaveBeenCalled());
    expect(store.getState().gameMode).toBe("pvp");
    expect(store.getState().playerConfig.white.type).toBe("human");
    expect(store.getState().playerConfig.black.type).toBe("human");
  });
});
