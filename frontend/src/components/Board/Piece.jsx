import { Box } from "@mui/material";

const Piece = ({ piece }) => {
  return (
    <Box
      sx={{
        position: "absolute",
        width: "68%",
        height: "68%",
        borderRadius: "50%",
        top: "16%",
        left: "16%",
        background: piece.color === "white" ? "#f4f6fb" : "#1a1a1f",
        border: "3px solid rgba(0,0,0,0.4)",
        display: "grid",
        placeItems: "center",
        fontWeight: 700,
        color: piece.color === "white" ? "#222" : "#f4f6fb",
        boxShadow: "0 6px 12px rgba(0,0,0,0.4)",
      }}
    >
      {piece.isKing ? "K" : ""}
    </Box>
  );
};

export default Piece;
