import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography } from "@mui/material";
import CelebrationIcon from "@mui/icons-material/Celebration";
import SentimentNeutralIcon from "@mui/icons-material/SentimentNeutral";
import { useGameContext } from "../../context/GameProvider";

const GameOverDialog = () => {
  const { store, api } = useGameContext();
  const boardState = store(state => state.boardState);
  const winner = boardState?.winner;

  if (!winner) return null;

  return (
    <Dialog open onClose={() => api.loadBoard()}>
      <DialogTitle display="flex" alignItems="center" gap={1}>
        {winner === "draw" ? <SentimentNeutralIcon color="warning" /> : <CelebrationIcon color="primary" />}
        {winner === "draw" ? "Draw" : `${winner} wins!`}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary">
          Try tweaking AI options or switching variants for a rematch.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => api.loadBoard()}>Restart</Button>
      </DialogActions>
    </Dialog>
  );
};

export default GameOverDialog;
