import { useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  Button,
  ButtonGroup,
  Stack,
  Typography,
  Alert,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import UndoIcon from "@mui/icons-material/Undo";
import RedoIcon from "@mui/icons-material/Redo";
import { useGameContext } from "../../context/GameProvider";

const GameActionsCard = () => {
  const [starting, setStarting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const { store, api } = useGameContext();
  const boardState = store(state => state.boardState);
  const error = store(state => state.error);
  const playerConfig = store(state => state.playerConfig);
  const variant = store(state => state.variant);
  const setGameReady = store(state => state.setGameReady);

  const handleStart = async () => {
    if (!boardState) return;
    setStarting(true);
    try {
      await api.configurePlayers(playerConfig);
      setGameReady(true);
      await api.runAITurns();
    } finally {
      setStarting(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await api.resetGame({ variant });
      setGameReady(false);
    } finally {
      setResetting(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Game Controls" />
      <CardContent>
        <Stack spacing={2}>
          <ButtonGroup fullWidth>
            <Button
              variant="contained"
              startIcon={<PlayArrowIcon />}
              onClick={handleStart}
              disabled={starting || !boardState}
            >
              Start / Resume
            </Button>
            <Button
              variant="outlined"
              startIcon={<RestartAltIcon />}
              onClick={handleReset}
              disabled={resetting}
            >
              Restart
            </Button>
          </ButtonGroup>
          <ButtonGroup fullWidth>
            <Button startIcon={<UndoIcon />} disabled={!boardState?.canUndo}>
              Undo
            </Button>
            <Button startIcon={<RedoIcon />} disabled={!boardState?.canRedo}>
              Redo
            </Button>
          </ButtonGroup>
          {error && <Alert severity="error">{error}</Alert>}
          <Typography variant="body2" color="text.secondary">
            Show/hide hints & coordinates in Variant settings. Future toggles: sound, move list, history export.
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default GameActionsCard;
