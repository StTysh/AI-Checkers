import { useCallback, useEffect, useMemo, useRef } from "react";

const API_BASE = "/api";

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

  const runAITurns = useCallback(async () => {
    if (aiLoopRef.current) return;
    aiLoopRef.current = true;
    try {
      while (true) {
        const { boardState, gameReady, gameMode, playerConfig } = store.getState();
        if (!gameReady || !boardState || boardState.winner) break;
        if (gameMode === "pvp") break;
        const turn = boardState.turn;
        const config = playerConfig[turn];
        if (!config || config.type !== "minimax") break;
        await requestAIMove({
          color: turn,
          algorithm: "minimax",
          depth: config.depth,
          persist: true,
        });
        if (store.getState().gameMode !== "aivai") break;
      }
    } finally {
      aiLoopRef.current = false;
    }
  }, [requestAIMove, store]);

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

  useEffect(() => {
    loadBoard();
  }, [loadBoard]);

  return useMemo(
    () => ({
      loadBoard,
      sendMove,
      requestAIMove,
      runAITurns,
      getValidMoves,
      changeVariant,
      resetGame,
      configurePlayers,
    }),
    [loadBoard, sendMove, requestAIMove, runAITurns, getValidMoves, changeVariant, resetGame, configurePlayers],
  );
};


