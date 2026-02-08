import { Box, Typography } from "@mui/material";

const CoordinateLabel = ({ boardSize, axis }) => {
  const fontSize = "clamp(10px, 1.2vw, 12px)";
  const lettersRaw = Array.from({ length: boardSize }, (_, idx) => String.fromCharCode(65 + idx));
  const numbersRaw = Array.from({ length: boardSize }, (_, idx) => boardSize - idx);

  // Keep coordinates in the board's canonical orientation even when the board is flipped.
  // (Flip affects piece/square rendering only; labels stay A..H / N..1 left-to-right, top-to-bottom.)
  const letters = lettersRaw;
  const numbers = numbersRaw;

  if (axis === "top" || axis === "bottom") {
    return (
      <Box
        sx={{
          width: "100%",
          height: "100%",
          display: "grid",
          gridTemplateColumns: `repeat(${boardSize}, 1fr)`,
          alignItems: "center",
          pointerEvents: "none",
        }}
      >
        {letters.map(letter => (
          <Typography
            key={letter}
            color="text.secondary"
            sx={{ fontSize, textAlign: "center", lineHeight: 1 }}
          >
            {letter}
          </Typography>
        ))}
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "grid",
        gridTemplateRows: `repeat(${boardSize}, 1fr)`,
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      {numbers.map(num => (
        <Typography
          key={num}
          color="text.secondary"
          sx={{ fontSize, textAlign: "center", lineHeight: 1 }}
        >
          {num}
        </Typography>
      ))}
    </Box>
  );
};

export default CoordinateLabel;
