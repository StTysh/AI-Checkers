import { Box } from "@mui/material";
import { useLayoutEffect, useMemo, useRef } from "react";

const Piece = ({ piece, boardSize, lastMove }) => {
  const cellPercent = useMemo(() => 100 / boardSize, [boardSize]);
  const scale = 0.78;
  const size = cellPercent * scale;
  const offset = (cellPercent - size) / 2;
  const ref = useRef(null);
  const animationRef = useRef({ timeouts: [] });

  const computePosition = (row, col) => ({
    top: `${row * cellPercent + offset}%`,
    left: `${col * cellPercent + offset}%`,
  });

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    const hasPrevious =
      typeof piece.previousRow === "number" && typeof piece.previousCol === "number";
    const moved = hasPrevious && (piece.previousRow !== piece.row || piece.previousCol !== piece.col);
    const target = computePosition(piece.row, piece.col);
    if (!moved) {
      node.style.top = target.top;
      node.style.left = target.left;
      return;
    }

    const cleanup = () => {
      animationRef.current.timeouts.forEach(timeoutId => clearTimeout(timeoutId));
      animationRef.current.timeouts = [];
    };

    cleanup();

    const from = computePosition(piece.previousRow, piece.previousCol);
    node.style.transition = "none";
    node.style.top = from.top;
    node.style.left = from.left;

    const steps = Array.isArray(lastMove?.steps) ? lastMove.steps : [];
    const end = steps[steps.length - 1];
    const isMultiCapture =
      steps.length > 1 &&
      lastMove?.start?.row === piece.previousRow &&
      lastMove?.start?.col === piece.previousCol &&
      end?.row === piece.row &&
      end?.col === piece.col;

    const animationSteps = isMultiCapture ? steps : [{ row: piece.row, col: piece.col }];
    const durationMs = 220;

    const frame = requestAnimationFrame(() => {
      node.style.transition = `top ${durationMs}ms ease, left ${durationMs}ms ease`;
      animationSteps.forEach((step, index) => {
        const timeoutId = setTimeout(() => {
          const position = computePosition(step.row, step.col);
          node.style.top = position.top;
          node.style.left = position.left;
        }, index * durationMs);
        animationRef.current.timeouts.push(timeoutId);
      });
    });

    return () => {
      cancelAnimationFrame(frame);
      cleanup();
    };
  }, [cellPercent, offset, lastMove, piece.previousCol, piece.previousRow, piece.col, piece.row]);

  return (
    <Box
      ref={ref}
      data-piece
      sx={{
        position: "absolute",
        width: `${size}%`,
        height: `${size}%`,
        borderRadius: "50%",
        top: `${piece.row * cellPercent + offset}%`,
        left: `${piece.col * cellPercent + offset}%`,
        background: piece.color === "white" ? "#f4f6fb" : "#1a1a1f",
        border: "3px solid rgba(0,0,0,0.35)",
        display: "grid",
        placeItems: "center",
        fontWeight: 700,
        color: piece.color === "white" ? "#222" : "#f4f6fb",
        boxShadow: "0 6px 16px rgba(0,0,0,0.45)",
        willChange: "top, left",
      }}
    >
      {piece.isKing ? "K" : ""}
    </Box>
  );
};

export default Piece;
