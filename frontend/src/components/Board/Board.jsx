import { Box, Paper, Typography } from "@mui/material";
import { useBoardLogic } from "../../hooks/useBoardLogic";
import Square from "./Square";
import CoordinateLabel from "./CoordinateLabel";
import Piece from "./Piece";

const Board = () => {
  const { boardState, pieces, squares, selectedCell, selectCell, highlightLookup, showCoordinates, flipBoard } =
    useBoardLogic();

  if (!boardState) {
    return (
      <Paper sx={{ height: 600, display: "grid", placeItems: "center" }}>
        <Typography variant="h6">Loading board…</Typography>
      </Paper>
    );
  }

  const { boardSize } = boardState;
  const coordGutter = "clamp(12px, 1.8vw, 18px)";
  const coordFrame = "clamp(0.25rem, 0.9vw, 0.5rem)";
  const paperPadding = showCoordinates ? coordFrame : "clamp(0.75rem, 3.5vw, 1.5rem)";

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
          p: paperPadding,
        }}
      >
        <Box
          sx={{
            width: "100%",
            height: "100%",
            display: "grid",
            gridTemplateColumns: showCoordinates ? `${coordGutter} 1fr ${coordGutter}` : "1fr",
            gridTemplateRows: showCoordinates ? `${coordGutter} 1fr ${coordGutter}` : "1fr",
            gap: showCoordinates ? coordFrame : 0,
          }}
        >
          {showCoordinates && <Box />}
          {showCoordinates && <CoordinateLabel boardSize={boardSize} axis="top" flipped={flipBoard} />}
          {showCoordinates && <Box />}

          {showCoordinates && <CoordinateLabel boardSize={boardSize} axis="left" flipped={flipBoard} />}
          <Box position="relative" width="100%" height="100%" sx={{ minWidth: 0, minHeight: 0 }}>
            <Box
              display="grid"
              gridTemplateColumns={`repeat(${boardSize}, 1fr)`}
              gridTemplateRows={`repeat(${boardSize}, 1fr)`}
              width="100%"
              height="100%"
            >
              {Array.from({ length: boardSize }, (_, displayRow) =>
                Array.from({ length: boardSize }, (_, displayCol) => {
                  const row = flipBoard ? boardSize - 1 - displayRow : displayRow;
                  const col = flipBoard ? boardSize - 1 - displayCol : displayCol;
                  return (
                    <Square
                      key={`${displayRow}-${displayCol}`}
                      row={row}
                      col={col}
                      selectedCell={selectedCell}
                      highlightLookup={highlightLookup}
                      selectCell={selectCell}
                    />
                  );
                }),
              )}
            </Box>
            <Box sx={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 20 }}>
              {pieces.map(piece => (
                <Piece
                  key={piece.id}
                  piece={piece}
                  boardSize={boardSize}
                  lastMove={boardState.lastMove}
                  flipped={flipBoard}
                />
              ))}
            </Box>
          </Box>
          {showCoordinates && <Box />}

          {showCoordinates && <Box />}
          {showCoordinates && <CoordinateLabel boardSize={boardSize} axis="bottom" flipped={flipBoard} />}
          {showCoordinates && <Box />}
        </Box>
      </Paper>
    </Box>
  );
};

export default Board;
