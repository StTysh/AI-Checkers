import { useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Stack,
  FormControlLabel,
  Switch,
  Button,
  ButtonGroup,
  Alert,
  Divider,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import UndoIcon from "@mui/icons-material/Undo";
import { GAME_MODES, VARIANTS } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const GameSetupCard = () => {
  const { store, api } = useGameContext();
  const boardState = store(state => state.boardState);
  const error = store(state => state.error);
  const playerConfig = store(state => state.playerConfig);
  const gameMode = store(state => state.gameMode);
  const variant = store(state => state.variant);
  const showHints = store(state => state.showHints);
  const showCoordinates = store(state => state.showCoordinates);
  const manualAiApproval = store(state => state.manualAiApproval);
  const setGameMode = store(state => state.setGameMode);
  const setGameReady = store(state => state.setGameReady);
  const setVariant = store(state => state.setVariant);
  const setShowHints = store(state => state.setShowHints);
  const setShowCoordinates = store(state => state.setShowCoordinates);
  const setManualAiApproval = store(state => state.setManualAiApproval);

  const [updatingMode, setUpdatingMode] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [undoing, setUndoing] = useState(false);

  const handleModeChange = async event => {
    if (updatingMode) return;
    const value = event.target.value;
    setUpdatingMode(true);
    try {
      setGameMode(value);
      setGameReady(false);
      const latestConfig = store.getState().playerConfig;
      await api.configurePlayers(latestConfig);
      await api.resetGame({ variant });
    } finally {
      setUpdatingMode(false);
    }
  };

  const handleVariantChange = async event => {
    const value = event.target.value;
    setVariant(value);
    await api.changeVariant(value);
  };

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
      <CardHeader title="Game Setup" />
      <CardContent>
        <Stack spacing={2}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth size="small" sx={{ maxWidth: "65%" }}>
                <InputLabel>Mode</InputLabel>
                <Select value={gameMode} label="Mode" onChange={handleModeChange}>
                  {GAME_MODES.map(mode => (
                    <MenuItem value={mode.value} key={mode.value}>
                      {mode.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={6}>
              <FormControl fullWidth size="small" sx={{ maxWidth: "80%" }}>
                <InputLabel>Variant</InputLabel>
                <Select value={variant} label="Variant" onChange={handleVariantChange}>
                  {VARIANTS.map(option => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
          </Grid>

          <Stack direction="row" spacing={2} alignItems="center" justifyContent="center" flexWrap="nowrap">
            <FormControlLabel
              control={<Switch checked={showHints} onChange={event => setShowHints(event.target.checked)} />}
              label="Move hints"
              sx={{
                mr: 0,
                ".MuiFormControlLabel-label": { whiteSpace: "nowrap" },
              }}
            />
            <FormControlLabel
              control={<Switch checked={showCoordinates} onChange={event => setShowCoordinates(event.target.checked)} />}
              label="Coordinates"
              sx={{
                mr: 0,
                ".MuiFormControlLabel-label": { whiteSpace: "nowrap" },
              }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={manualAiApproval}
                  onChange={async event => {
                    const enabled = event.target.checked;
                    setManualAiApproval(enabled);
                    if (!enabled) {
                      await api.runAITurns();
                    }
                  }}
                />
              }
              label="Confirm AI moves"
              sx={{
                mr: 0,
                ".MuiFormControlLabel-label": { whiteSpace: "nowrap" },
              }}
            />
          </Stack>

          <Divider />

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
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default GameSetupCard;
