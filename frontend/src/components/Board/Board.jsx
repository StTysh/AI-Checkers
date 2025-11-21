import { Box, Paper, Typography } from "@mui/material";
import { useBoardLogic } from "../../hooks/useBoardLogic";
import Square from "./Square";
import CoordinateLabel from "./CoordinateLabel";

const Board = () => {
  const { boardState, squares, showCoordinates } = useBoardLogic();

  if (!boardState) {
    return (
      <Paper sx={{ height: 600, display: "grid", placeItems: "center" }}>
        <Typography variant="h6">Loading board…</Typography>
      </Paper>
    );
  }

  const { boardSize } = boardState;

  return (
    <Box position="relative">
      <Paper
        elevation={6}
        sx={{
          width: "100%",
          aspectRatio: "1 / 1",
          borderRadius: "4%",
          overflow: "hidden",
          background: "#1c1f2b",
          p: "clamp(1rem, 5vw, 2rem)",
        }}
      >
        <Box
          display="grid"
          gridTemplateColumns={`repeat(${boardSize}, 1fr)`}
          gridTemplateRows={`repeat(${boardSize}, 1fr)`}
          width="100%"
          height="100%"
        >
          {squares.flatMap((row, rIdx) =>
            row.map((square, cIdx) => <Square key={`${rIdx}-${cIdx}`} row={rIdx} col={cIdx} square={square} />),
          )}
        </Box>
      </Paper>

      {showCoordinates && <CoordinateLabel boardSize={boardSize} />}
    </Box>
  );
};

export default Board;
