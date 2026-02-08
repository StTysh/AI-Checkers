import { Box } from "@mui/material";
import clsx from "clsx";
import { memo } from "react";

const Square = ({ row, col, selectedCell, highlightLookup, selectCell }) => {
  const isLight = (row + col) % 2 === 0;
  const isSelected = selectedCell && selectedCell.row === row && selectedCell.col === col;
  const isHighlight = highlightLookup.has(`${row},${col}`);

  return (
    <Box
      onClick={() => selectCell({ row, col })}
      className={clsx("board-square", { selected: isSelected, highlight: isHighlight })}
      sx={{
        position: "relative",
        cursor: "pointer",
        backgroundColor: isLight ? "#f1d4a1" : "#6c452b",
        // Use an inset shadow instead of `outline` so the highlight isn't painted underneath
        // neighboring squares in the grid (outline extends outside the box).
        "&.selected": { boxShadow: "inset 0 0 0 3px #f9a826" },
        "&.highlight::after": {
          content: '""',
          position: "absolute",
          inset: "25%",
          borderRadius: "50%",
          backgroundColor: "rgba(249,168,38,0.6)",
        },
      }}
    >
    </Box>
  );
};

export default memo(Square);
