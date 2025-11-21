import { useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  Stack,
} from "@mui/material";
import { GAME_MODES } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const GameModeCard = () => {
  const { store, api } = useGameContext();
  const gameMode = store(state => state.gameMode);
  const setGameMode = store(state => state.setGameMode);
  const setGameReady = store(state => state.setGameReady);
  const variant = store(state => state.variant);
  const [updating, setUpdating] = useState(false);

  const handleModeChange = async event => {
    if (updating) return;
    const value = event.target.value;
    setUpdating(true);
    try {
      setGameMode(value);
      setGameReady(false);
      const latestConfig = store.getState().playerConfig;
      await api.configurePlayers(latestConfig);
      await api.resetGame({ variant });
    } finally {
      setUpdating(false);
    }
  };

  return (
    <Card>
      <CardHeader title="Game Mode" subheader="Choose who controls each side" />
      <CardContent>
        <FormControl fullWidth size="small">
          <InputLabel>Mode</InputLabel>
          <Select value={gameMode} label="Mode" onChange={handleModeChange}>
            {GAME_MODES.map(mode => (
              <MenuItem value={mode.value} key={mode.value}>
                {mode.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Stack mt={2} spacing={0.5}>
          <Typography variant="body2" color="text.secondary">
            Player vs Player: local head-to-head.
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Player vs AI: practice against Minimax (more bots soon).
          </Typography>
          <Typography variant="body2" color="text.secondary">
            AI vs AI: run tournaments or simulations.
          </Typography>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default GameModeCard;
