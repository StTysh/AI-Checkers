import { create } from "zustand";
import { immer } from "zustand/middleware/immer";
import { DEFAULT_PLAYER_CONFIG, GAME_MODES, PLAYER_KINDS, VARIANTS } from "../utils/constants";

const clone = value => JSON.parse(JSON.stringify(value));
const FIRST_AI_TYPE = PLAYER_KINDS.find(option => option.value !== "human" && !option.disabled)?.value || "minimax";

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

export const createJsonResponse = (payload, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: async () => payload,
  text: async () => (typeof payload === "string" ? payload : JSON.stringify(payload)),
});

export const createTextResponse = (message, ok = false, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: async () => {
    throw new Error("json() should not be called for text responses");
  },
  text: async () => message,
});

export const createTestStore = overrides => {
  const initialPlayerConfig = clone(overrides?.playerConfig ?? DEFAULT_PLAYER_CONFIG);
  return create(
    immer(set => ({
      boardState: overrides?.boardState ?? null,
      loading: overrides?.loading ?? false,
      error: overrides?.error ?? null,
      selectedCell: null,
      highlightMoves: [],
      showHints: overrides?.showHints ?? true,
      showCoordinates: overrides?.showCoordinates ?? true,
      gameMode: overrides?.gameMode ?? GAME_MODES[0].value,
      variant: overrides?.variant ?? VARIANTS[0].value,
      playerConfig: initialPlayerConfig,
      lastMove: null,
      gameReady: overrides?.gameReady ?? false,
      systemInfo: overrides?.systemInfo ?? { recommendedMaxWorkers: 8 },
      manualAiApproval: overrides?.manualAiApproval ?? false,
      flipBoard: overrides?.flipBoard ?? false,
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
      setPlayerConfig: playerConfig =>
        set(state => {
          state.playerConfig = playerConfig;
        }),
      updatePlayerConfig: (color, changes) =>
        set(state => {
          state.playerConfig[color] = { ...state.playerConfig[color], ...changes };
          if (Object.prototype.hasOwnProperty.call(changes, "type")) {
            enforcePvaiPairing(state, color);
          }
        }),
      swapPlayerConfigs: () =>
        set(state => {
          const prevWhite = state.playerConfig.white;
          const prevBlack = state.playerConfig.black;
          state.playerConfig.white = prevBlack;
          state.playerConfig.black = prevWhite;
        }),
      setShowHints: flag => set({ showHints: flag }),
      setShowCoordinates: flag => set({ showCoordinates: flag }),
      setManualAiApproval: flag => set({ manualAiApproval: flag }),
      setFlipBoard: flag => set({ flipBoard: flag }),
      setGameReady: flag => set({ gameReady: flag }),
      setSystemInfo: info => set({ systemInfo: info }),
      setLastMove: move => set({ lastMove: move }),
      resetGameState: () =>
        set(state => {
          state.selectedCell = null;
          state.highlightMoves = [];
          state.lastMove = null;
        }),
    })),
  );
};
