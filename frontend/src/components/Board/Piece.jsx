import { Box } from "@mui/material";
import { useLayoutEffect, useMemo, useRef } from "react";

const Piece = ({ piece, boardSize }) => {
  const cellPercent = useMemo(() => 100 / boardSize, [boardSize]);
  const scale = 0.78;
  const size = cellPercent * scale;
  const offset = (cellPercent - size) / 2;
  const ref = useRef(null);

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

    const from = computePosition(piece.previousRow, piece.previousCol);
    node.style.transition = "none";
    node.style.top = from.top;
    node.style.left = from.left;

    const frame = requestAnimationFrame(() => {
      node.style.transition = "top 220ms ease, left 220ms ease";
      node.style.top = target.top;
      node.style.left = target.left;
    });

    return () => cancelAnimationFrame(frame);
  }, [cellPercent, offset, piece.previousCol, piece.previousRow, piece.col, piece.row]);

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
