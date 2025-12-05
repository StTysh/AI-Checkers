import { useCallback, useEffect, useMemo, useRef } from "react";

const API_BASE = "/api";
const SUPPORTED_AI_TYPES = new Set(["minimax", "minimax_simple"]);

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
        await requestAIMove({
          color: turn,
          algorithm: config.type,
          depth: config.depth,
          persist: true,
          commitImmediately: !manualAiApproval,
        });
        if (manualAiApproval) break;
        if (store.getState().gameMode !== "aivai") break;
      }
    } finally {
      aiLoopRef.current = false;
      notifyAiIdle();
    }
  }, [notifyAiIdle, performPendingRequest, requestAIMove, store]);

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

  const performPendingAIMove = useCallback(
    async color => {
      await performPendingRequest(color);
      await runAITurns();
    },
    [performPendingRequest, runAITurns],
  );

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
    ],
  );
};


