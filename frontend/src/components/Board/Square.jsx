import { Box } from "@mui/material";
import clsx from "clsx";
import { useBoardLogic } from "../../hooks/useBoardLogic";

const Square = ({ row, col }) => {
  const { selectedCell, selectCell, highlightMoves } = useBoardLogic();
  const isLight = (row + col) % 2 === 0;
  const isSelected = selectedCell && selectedCell.row === row && selectedCell.col === col;
  const isHighlight = highlightMoves.some(move => move.row === row && move.col === col);

  return (
    <Box
      onClick={() => selectCell({ row, col })}
      className={clsx("board-square", { selected: isSelected, highlight: isHighlight })}
      sx={{
        position: "relative",
        cursor: "pointer",
        backgroundColor: isLight ? "#f1d4a1" : "#6c452b",
        "&.selected": { outline: "3px solid #f9a826" },
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

export default Square;
