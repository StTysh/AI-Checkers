import { useMemo, useCallback } from "react";
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

  const squares = useMemo(() => {
    if (!boardState) return [];
    const grid = Array.from({ length: boardState.boardSize }, () =>
      Array.from({ length: boardState.boardSize }, () => ({ piece: null })),
    );
    boardState.pieces.forEach(piece => {
      grid[piece.row][piece.col] = { piece };
    });
    return grid;
  }, [boardState]);

  const selectCell = useCallback(
    async cell => {
      if (!boardState || !gameReady) return;

      if (selectedCell && selectedCell.row === cell.row && selectedCell.col === cell.col) {
        setSelectedCell(null);
        setHighlightMoves([]);
        return;
      }

      const target = highlightStore.find(move => move.row === cell.row && move.col === cell.col);
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
    [api, boardState, gameReady, highlightStore, selectedCell, setHighlightMoves, setSelectedCell, squares],
  );

  return {
    boardState,
    squares,
    selectedCell,
    selectCell,
    highlightMoves: showHints ? highlightStore : [],
    showCoordinates,
  };
};
