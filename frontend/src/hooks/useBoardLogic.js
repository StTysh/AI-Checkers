import { useMemo, useCallback, useRef, useEffect } from "react";
import { useGameContext } from "../context/GameProvider";

export const useBoardLogic = () => {
  const { store, api } = useGameContext();
  const boardState = store(state => state.boardState);
  const selectedCell = store(state => state.selectedCell);
  const highlightStore = store(state => state.highlightMoves);
  const showHints = store(state => state.showHints);
  const showCoordinates = store(state => state.showCoordinates);
  const gameReady = store(state => state.gameReady);
  const setSelectedCell = store(state => state.setSelectedCell);
  const setHighlightMoves = store(state => state.setHighlightMoves);

  const previousPiecesRef = useRef([]);

  useEffect(() => {
    if (!boardState?.pieces) {
      previousPiecesRef.current = [];
      return;
    }
    previousPiecesRef.current = boardState.pieces.map(piece => ({ ...piece }));
  }, [boardState?.pieces]);

  const pieces = useMemo(() => {
    if (!boardState?.pieces) return [];
    const previousById = new Map(previousPiecesRef.current.map(piece => [piece.id, piece]));
    return boardState.pieces.map(piece => {
      const previous = previousById.get(piece.id);
      return previous ? { ...piece, row: piece.row, col: piece.col, previousRow: previous.row, previousCol: previous.col } : piece;
    });
  }, [boardState?.pieces]);

  const squares = useMemo(() => {
    if (!boardState?.pieces) return [];
    const grid = Array.from({ length: boardState.boardSize }, () =>
      Array.from({ length: boardState.boardSize }, () => ({ piece: null })),
    );
    boardState.pieces.forEach(piece => {
      grid[piece.row][piece.col] = { piece };
    });
    return grid;
  }, [boardState?.pieces, boardState?.boardSize]);

  const highlightMoves = useMemo(() => (showHints ? highlightStore : []), [highlightStore, showHints]);

  const highlightLookup = useMemo(() => {
    const map = new Map();
    highlightMoves.forEach(move => {
      map.set(`${move.row},${move.col}`, move);
    });
    return map;
  }, [highlightMoves]);

  const selectCell = useCallback(
    async cell => {
      if (!boardState || !gameReady) return;

      if (selectedCell && selectedCell.row === cell.row && selectedCell.col === cell.col) {
        setSelectedCell(null);
        setHighlightMoves([]);
        return;
      }

      const target = highlightLookup.get(`${cell.row},${cell.col}`);
      if (selectedCell && target) {
        await api.sendMove({ start: selectedCell, steps: target.move.steps });
        setSelectedCell(null);
        setHighlightMoves([]);
        return;
      }

      const piece = squares[cell.row]?.[cell.col]?.piece;
      if (!piece || piece.color !== boardState.turn) {
        setSelectedCell(null);
        setHighlightMoves([]);
        return;
      }

      setSelectedCell(cell);
      try {
        const data = await api.getValidMoves(cell);
        const targets = data.moves.map(move => {
          const last = move.steps[move.steps.length - 1] ?? move.start;
          return { row: last.row, col: last.col, move };
        });
        setHighlightMoves(targets);
      } catch {
        setHighlightMoves([]);
      }
    },
    [api, boardState, gameReady, highlightLookup, selectedCell, setHighlightMoves, setSelectedCell, squares],
  );

  return {
    boardState,
    pieces,
    squares,
    selectedCell,
    selectCell,
    highlightLookup,
    showCoordinates,
  };
};
