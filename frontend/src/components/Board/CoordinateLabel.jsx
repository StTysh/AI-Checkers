import { Box, Typography } from "@mui/material";

const CoordinateLabel = ({ boardSize }) => {
  const letters = Array.from({ length: boardSize }, (_, idx) => String.fromCharCode(65 + idx));
  const numbers = Array.from({ length: boardSize }, (_, idx) => boardSize - idx);

  return (
    <>
      <Box
        position="absolute"
        top="1%"
        left="50%"
        display="flex"
        justifyContent="space-between"
        width="82%"
        sx={{ transform: "translateX(-50%)" }}
      >
        {letters.map(letter => (
          <Typography key={letter} color="text.secondary" fontSize={12}>
            {letter}
          </Typography>
        ))}
      </Box>
      <Box
        position="absolute"
        left="1.4%"
        top="50%"
        display="flex"
        flexDirection="column"
        justifyContent="space-between"
        height="83%"
        sx={{ transform: "translateY(-50%)" }}
      >
        {numbers.map(num => (
          <Typography key={num} color="text.secondary" fontSize={12}>
            {num}
          </Typography>
        ))}
      </Box>
    </>
  );
};

export default CoordinateLabel;
