import { useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Stack,
  FormGroup,
  FormControlLabel,
  Switch,
} from "@mui/material";
import { PLAYER_KINDS } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const PlayerConfigCard = ({ color }) => {
  const label = color === "white" ? "White" : "Black";
  const { store, api } = useGameContext();
  const config = store(state => state.playerConfig[color]);
  const boardState = store(state => state.boardState);
  const updatePlayer = store(state => state.updatePlayerConfig);
  const gameMode = store(state => state.gameMode);
  const manualAiApproval = store(state => state.manualAiApproval);
  const [performing, setPerforming] = useState(false);

  const syncConfig = changes => {
    updatePlayer(color, changes);
    const { playerConfig } = store.getState();
    api.configurePlayers({
      white: playerConfig.white,
      black: playerConfig.black,
    });
  };

  const isOptionDisabled = option => {
    if (option.disabled) return true;
    if (gameMode === "pvp") return option.value !== "human";
    if (gameMode === "aivai") return option.value === "human";
    return false;
  };

  const pendingMove = boardState?.pendingAiMoves?.[color];
  const showPerformButton =
    manualAiApproval &&
    gameMode !== "pvp" &&
    config.type !== "human" &&
    Boolean(pendingMove) &&
    boardState?.turn === color;

  const handlePerformMove = async () => {
    if (!showPerformButton || performing) return;
    setPerforming(true);
    try {
      await api.performPendingAIMove(color);
    } catch (error) {
      // Error already surfaced via global toast/state.
    } finally {
      setPerforming(false);
    }
  };

  return (
    <Card>
      <CardHeader title={`${label} Player`} subheader="Configure controller / AI options" />
      <CardContent>
        <FormControl fullWidth size="small">
          <InputLabel>Player Type</InputLabel>
          <Select value={config.type} label="Player Type" onChange={event => syncConfig({ type: event.target.value })}>
            {PLAYER_KINDS.map(option => (
              <MenuItem value={option.value} key={option.value} disabled={isOptionDisabled(option)}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {config.type !== "human" && (
          <Stack spacing={2} mt={2}>
            <Slider
              value={config.depth}
              onChange={(_, val) => updatePlayer(color, { depth: val })}
              onChangeCommitted={(_, val) => syncConfig({ depth: val })}
              min={2}
              max={12}
              step={1}
              valueLabelDisplay="auto"
              marks
            />
            {showPerformButton && (
              <Button variant="contained" onClick={handlePerformMove} disabled={performing}>
                Perform move
              </Button>
            )}
            {/* <FormGroup>
              <FormControlLabel
                control={
                  <Switch
                    checked={config.alphaBeta}
                    onChange={event => syncConfig({ alphaBeta: event.target.checked })}
                  />
                }
                label="Alpha-Beta pruning"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={config.transposition}
                    onChange={event => syncConfig({ transposition: event.target.checked })}
                  />
                }
                label="Transposition tables"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={config.moveOrdering}
                    onChange={event => syncConfig({ moveOrdering: event.target.checked })}
                  />
                }
                label="Move ordering"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={config.iterativeDeepening}
                    onChange={event => syncConfig({ iterativeDeepening: event.target.checked })}
                  />
                }
                label="Iterative deepening"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={config.quiescence}
                    onChange={event => syncConfig({ quiescence: event.target.checked })}
                  />
                }
                label="Quiescence search"
              />
            </FormGroup> */}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
};

export default PlayerConfigCard;
