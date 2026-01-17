import { useCallback, useEffect, useMemo, useRef } from "react";

const API_BASE = "/api";
const SUPPORTED_AI_TYPES = new Set(["minimax", "mcts"]);

const MINIMAX_PAYLOAD_KEYS = [
  "depth",
  "alphaBeta",
  "transposition",
  "moveOrdering",
  "killerMoves",
  "iterativeDeepening",
  "quiescence",
  "maxQuiescenceDepth",
  "aspiration",
  "aspirationWindow",
  "historyHeuristic",
  "butterflyHeuristic",
  "nullMove",
  "nullMoveReduction",
  "lmr",
  "lmrMinDepth",
  "lmrMinMoves",
  "lmrReduction",
  "deterministicOrdering",
  "endgameTablebase",
  "endgameMaxPieces",
  "endgameMaxPlies",
  "timeLimitMs",
  "parallel",
  "workers",
];

const MCTS_PAYLOAD_KEYS = [
  "iterations",
  "rolloutDepth",
  "explorationConstant",
  "randomSeed",
  "mctsParallel",
  "mctsWorkers",
  "rolloutPolicy",
  "guidanceDepth",
  "rolloutCutoffDepth",
  "leafEvaluation",
  "mctsTransposition",
  "mctsTranspositionMaxEntries",
  "progressiveWidening",
  "pwK",
  "pwAlpha",
];

const assignPayloadKeys = (target, source, keys) => {
  keys.forEach(key => {
    if (key === "randomSeed") {
      target.randomSeed = source.randomSeed ?? undefined;
      return;
    }
    target[key] = source[key];
  });
};

const handleResponse = async response => {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Backend error");
  }
  return response.json();
};

export const useGameAPI = store => {
  if (!store) throw new Error("useGameAPI requires a zustand store instance");

  const loadBoard = useCallback(async () => {
    const { setBoardState, setLoading, setError, setGameReady } = store.getState();
    try {
      setLoading(true);
      const data = await handleResponse(await fetch(`${API_BASE}/board`));
      setBoardState(data);
      setGameReady(false);
    } catch (error) {
      setError(error.message);
    }
  }, [store]);

  const requestAIMove = useCallback(
    async payload => {
      const { setBoardState, setError } = store.getState();
      try {
        const data = await handleResponse(
          await fetch(`${API_BASE}/ai-move`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload ?? {}),
          }),
        );
        setBoardState(data);
      } catch (error) {
        setError(error.message);
        throw error;
      }
    },
    [store],
  );

  const aiLoopRef = useRef(false);
  const aiIdleWaitersRef = useRef([]);

  const notifyAiIdle = useCallback(() => {
    aiIdleWaitersRef.current.forEach(resolve => resolve());
    aiIdleWaitersRef.current = [];
  }, []);

  const waitForAiIdle = useCallback(() => {
    if (!aiLoopRef.current) {
      return Promise.resolve();
    }
    return new Promise(resolve => {
      aiIdleWaitersRef.current.push(resolve);
    });
  }, []);

  const performPendingRequest = useCallback(
    async color => {
      const { setBoardState, setError } = store.getState();
      try {
        const data = await handleResponse(
          await fetch(`${API_BASE}/ai-perform`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ color }),
          }),
        );
        setBoardState(data);
      } catch (error) {
        setError(error.message);
        throw error;
      }
    },
    [store],
  );

  const runAITurns = useCallback(async () => {
    if (aiLoopRef.current) return;
    aiLoopRef.current = true;
    try {
      while (true) {
        const { boardState, gameReady, gameMode, playerConfig, manualAiApproval } = store.getState();
        if (!gameReady || !boardState || boardState.winner) break;
        if (gameMode === "pvp") break;
        const turn = boardState.turn;
        const config = playerConfig[turn];
        if (!config || !SUPPORTED_AI_TYPES.has(config.type)) break;
        const pendingMove = boardState.pendingAiMoves?.[turn];
        if (pendingMove) {
          if (manualAiApproval) break;
          await performPendingRequest(turn);
          continue;
        }
        const payload = buildAiPayload(turn, config, manualAiApproval);
        await requestAIMove(payload);
        if (manualAiApproval) break;
        if (store.getState().gameMode !== "aivai") break;
      }
    } finally {
      aiLoopRef.current = false;
      notifyAiIdle();
    }
  }, [notifyAiIdle, performPendingRequest, requestAIMove, store]);

  const buildAiPayload = (turn, config, manualAiApproval) => {
    const payload = {
      color: turn,
      algorithm: config.type,
      persist: true,
      commitImmediately: !manualAiApproval,
    };
    if (config.type === "minimax") {
      assignPayloadKeys(payload, config, MINIMAX_PAYLOAD_KEYS);
    }
    if (config.type === "mcts") {
      assignPayloadKeys(payload, config, MCTS_PAYLOAD_KEYS);
    }
    return payload;
  };

  const sendMove = useCallback(
    async payload => {
      const { setBoardState, setLastMove, setError } = store.getState();
      try {
        const data = await handleResponse(
          await fetch(`${API_BASE}/move`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          }),
        );
        setBoardState(data);
        setLastMove(payload);
        await runAITurns();
      } catch (error) {
        setError(error.message);
        throw error;
      }
    },
    [runAITurns, store],
  );

  const getValidMoves = useCallback(
    async ({ row, col }) => {
      const { setError } = store.getState();
      try {
        return await handleResponse(await fetch(`${API_BASE}/valid-moves?row=${row}&col=${col}`));
      } catch (error) {
        setError(error.message);
        throw error;
      }
    },
    [store],
  );

  const changeVariant = useCallback(
    async variant => {
      const { setBoardState, setError, setGameReady } = store.getState();
      try {
        const data = await handleResponse(
          await fetch(`${API_BASE}/variant`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ variant }),
          }),
        );
        setBoardState(data);
        setGameReady(false);
      } catch (error) {
        setError(error.message);
      }
    },
    [store],
  );

  const resetGame = useCallback(
    async payload => {
      const { setBoardState, setError, setGameReady } = store.getState();
      try {
        const data = await handleResponse(
          await fetch(`${API_BASE}/reset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: payload ? JSON.stringify(payload) : undefined,
          }),
        );
        setBoardState(data);
        setGameReady(false);
      } catch (error) {
        setError(error.message);
      }
    },
    [store],
  );

  const configurePlayers = useCallback(
    async config => {
      const { setBoardState, setError } = store.getState();
      try {
        const data = await handleResponse(
          await fetch(`${API_BASE}/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config),
          }),
        );
        setBoardState(data);
      } catch (error) {
        setError(error.message);
      }
    },
    [store],
  );

  const undoMove = useCallback(async () => {
    const { setBoardState, setError } = store.getState();
    try {
      const data = await handleResponse(
        await fetch(`${API_BASE}/undo`, {
          method: "POST",
        }),
      );
      setBoardState(data);
    } catch (error) {
      setError(error.message);
      throw error;
    }
  }, [store]);

  const fetchSystemInfo = useCallback(async () => {
    const { setError } = store.getState();
    try {
      return await handleResponse(await fetch(`${API_BASE}/system-info`));
    } catch (error) {
      setError(error.message);
      throw error;
    }
  }, [store]);

  const performPendingAIMove = useCallback(
    async color => {
      await performPendingRequest(color);
      await runAITurns();
    },
    [performPendingRequest, runAITurns],
  );

  const startEvaluation = useCallback(async payload => {
    const { setError } = store.getState();
    try {
      return await handleResponse(
        await fetch(`${API_BASE}/evaluate/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }),
      );
    } catch (error) {
      setError(error.message);
      throw error;
    }
  }, [store]);

  const getEvaluationStatus = useCallback(async evaluationId => {
    const { setError } = store.getState();
    try {
      return await handleResponse(
        await fetch(`${API_BASE}/evaluate/status?evaluation_id=${evaluationId}`),
      );
    } catch (error) {
      setError(error.message);
      throw error;
    }
  }, [store]);

  const stopEvaluation = useCallback(async evaluationId => {
    const { setError } = store.getState();
    try {
      return await handleResponse(
        await fetch(`${API_BASE}/evaluate/stop`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ evaluationId }),
        }),
      );
    } catch (error) {
      setError(error.message);
      throw error;
    }
  }, [store]);

  const getEvaluationResults = useCallback(async (evaluationId, format = "csv") => {
    const response = await fetch(`${API_BASE}/evaluate/results?evaluation_id=${evaluationId}&format=${format}`);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || "Backend error");
    }
    if (format === "json") {
      return response.json();
    }
    return response.text();
  }, []);

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  return useMemo(
    () => ({
      loadBoard,
      sendMove,
      requestAIMove,
      runAITurns,
      waitForAiIdle,
      undoMove,
      performPendingAIMove,
      getValidMoves,
      changeVariant,
      resetGame,
      configurePlayers,
      fetchSystemInfo,
      startEvaluation,
      getEvaluationStatus,
      stopEvaluation,
      getEvaluationResults,
    }),
    [
      loadBoard,
      sendMove,
      requestAIMove,
      runAITurns,
      waitForAiIdle,
      getValidMoves,
      changeVariant,
      resetGame,
      configurePlayers,
      undoMove,
      performPendingAIMove,
      fetchSystemInfo,
      startEvaluation,
      getEvaluationStatus,
      stopEvaluation,
      getEvaluationResults,
    ],
  );
};


