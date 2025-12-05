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
import { useGameContext } from "../../context/GameProvider";

const GameActionsCard = () => {
  const [starting, setStarting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [undoing, setUndoing] = useState(false);
  const { store, api } = useGameContext();
  const boardState = store(state => state.boardState);
  const error = store(state => state.error);
  const playerConfig = store(state => state.playerConfig);
  const variant = store(state => state.variant);
  const setGameReady = store(state => state.setGameReady);
  const gameMode = store(state => state.gameMode);

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
      setGameReady(false);
      await api.waitForAiIdle();
      await api.resetGame({ variant });
    } finally {
      setResetting(false);
    }
  };

  const handleUndo = async () => {
    if (!boardState?.canUndo || gameMode === "aivai") return;
    setUndoing(true);
    try {
      await api.waitForAiIdle();
      await api.undoMove();
    } finally {
      setUndoing(false);
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
          <Button
            fullWidth
            startIcon={<UndoIcon />}
            onClick={handleUndo}
            disabled={!boardState?.canUndo || gameMode === "aivai" || undoing}
          >
            Undo
          </Button>
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
