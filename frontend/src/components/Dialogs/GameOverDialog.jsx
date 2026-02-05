import { useState } from "react";
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Typography } from "@mui/material";
import CelebrationIcon from "@mui/icons-material/Celebration";
import SentimentNeutralIcon from "@mui/icons-material/SentimentNeutral";
import { useGameContext } from "../../context/GameProvider";

const GameOverDialog = () => {
  const { store, api } = useGameContext();
  const boardState = store(state => state.boardState);
  const winner = boardState?.winner;
  const variant = store(state => state.variant);
  const setGameReady = store(state => state.setGameReady);
  const [restarting, setRestarting] = useState(false);

  const handleRestart = async () => {
    if (restarting) return;
    setRestarting(true);
    try {
      setGameReady(false);
      await api.resetGame({ variant });
    } finally {
      setRestarting(false);
    }
  };

  if (!winner) return null;

  return (
    <Dialog open onClose={handleRestart}>
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
        <Button onClick={handleRestart} disabled={restarting}>
          Restart
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default GameOverDialog;
