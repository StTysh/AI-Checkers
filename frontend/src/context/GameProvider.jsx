import { createContext, useContext, useMemo } from "react";
import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { DEFAULT_PLAYER_CONFIG, VARIANTS, GAME_MODES, PLAYER_KINDS } from "../utils/constants";
import { useGameAPI } from "../hooks/useGameAPI";

const GameStoreContext = createContext(null);

const cloneDefaultPlayerConfig = () => JSON.parse(JSON.stringify(DEFAULT_PLAYER_CONFIG));
const FIRST_AI_TYPE = PLAYER_KINDS.find(option => option.value !== "human" && !option.disabled)?.value || "minimax";

const getStoredGameMode = () => GAME_MODES[0].value;

const enforcePvaiPairing = (state, changedColor) => {
  if (state.gameMode !== "pvai" || !changedColor) return;
  const otherColor = changedColor === "white" ? "black" : "white";
  const changedType = state.playerConfig[changedColor].type;
  if (changedType === "human") {
    state.playerConfig[otherColor].type = FIRST_AI_TYPE;
  } else {
    state.playerConfig[otherColor].type = "human";
  }
};

const useGameStore = create(
  immer(set => ({
    boardState: null,
    loading: true,
    error: null,
    selectedCell: null,
    highlightMoves: [],
    showHints: true,
    showCoordinates: true,
    gameMode: getStoredGameMode(),
    variant: VARIANTS[0].value,
    playerConfig: cloneDefaultPlayerConfig(),
    lastMove: null,
    gameReady: false,
    manualAiApproval: false,
    setBoardState: payload =>
      set(state => {
        state.boardState = payload;
        state.loading = false;
        state.error = null;
        state.lastMove = payload?.lastMove ?? null;
        if (payload?.playerConfig) {
          state.playerConfig = payload.playerConfig;
        }
        if (payload?.variant) {
          state.variant = payload.variant;
        }
        state.selectedCell = null;
        state.highlightMoves = [];
      }),
    setLoading: flag => set({ loading: flag }),
    setError: err => set({ error: err, loading: false }),
    setSelectedCell: cell => set({ selectedCell: cell }),
    setHighlightMoves: moves => set({ highlightMoves: moves }),
    setGameMode: mode =>
      set(state => {
        state.gameMode = mode;
        state.gameReady = false;
        if (mode === "pvai") {
          state.playerConfig.white.type = "human";
          state.playerConfig.black.type = FIRST_AI_TYPE;
        } else if (mode === "pvp") {
          state.playerConfig.white.type = "human";
          state.playerConfig.black.type = "human";
        } else if (mode === "aivai") {
          state.playerConfig.white.type = FIRST_AI_TYPE;
          state.playerConfig.black.type = FIRST_AI_TYPE;
        }
      }),
    setVariant: variant => set({ variant }),
    updatePlayerConfig: (color, changes) =>
      set(state => {
        state.playerConfig[color] = { ...state.playerConfig[color], ...changes };
        if (Object.prototype.hasOwnProperty.call(changes, "type")) {
          enforcePvaiPairing(state, color);
        }
      }),
    setShowHints: flag => set({ showHints: flag }),
    setShowCoordinates: flag => set({ showCoordinates: flag }),
    setManualAiApproval: flag => set({ manualAiApproval: flag }),
    setGameReady: flag => set({ gameReady: flag }),
    setLastMove: move => set({ lastMove: move }),
    resetGameState: () =>
      set(state => {
        state.selectedCell = null;
        state.highlightMoves = [];
        state.lastMove = null;
      }),
  })),
);

export const GameProvider = ({ children }) => {
  const api = useGameAPI(useGameStore);
  const contextValue = useMemo(() => ({ store: useGameStore, api }), [api]);

  return <GameStoreContext.Provider value={contextValue}>{children}</GameStoreContext.Provider>;
};

export const useGameContext = () => {
  const ctx = useContext(GameStoreContext);
  if (!ctx) throw new Error("useGameContext must be used inside GameProvider");
  return ctx;
};
