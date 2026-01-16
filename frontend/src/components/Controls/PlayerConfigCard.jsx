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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  TextField,
  Typography,
  FormGroup,
  FormControlLabel,
  Switch,
  Divider,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
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

  const isMinimax = config.type === "minimax";
  const isMcts = config.type === "mcts";

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
            {isMinimax && (
              <>
                <Typography variant="body2">Max depth</Typography>
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
                <FormGroup>
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.alphaBeta}
                        onChange={event => {
                          const enabled = event.target.checked;
                          const updates = { alphaBeta: enabled };
                          if (!enabled) {
                            updates.moveOrdering = false;
                            updates.killerMoves = false;
                          }
                          syncConfig(updates);
                        }}
                      />
                    }
                    label="Enable Alpha–Beta"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.transposition}
                        onChange={event => syncConfig({ transposition: event.target.checked })}
                      />
                    }
                    label="Enable Transposition Table"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.moveOrdering}
                        onChange={event => {
                          const enabled = event.target.checked;
                          const updates = { moveOrdering: enabled };
                          if (!enabled) {
                            updates.killerMoves = false;
                          }
                          syncConfig(updates);
                        }}
                        disabled={!config.alphaBeta}
                      />
                    }
                    label="Enable Move Ordering"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.killerMoves}
                        onChange={event => syncConfig({ killerMoves: event.target.checked })}
                        disabled={!config.alphaBeta || !config.moveOrdering}
                      />
                    }
                    label="Enable Killer Moves"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.quiescence}
                        onChange={event => syncConfig({ quiescence: event.target.checked })}
                      />
                    }
                    label="Enable Quiescence Search"
                  />
                </FormGroup>
                <Accordion elevation={0} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Search controls</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <FormGroup>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.iterativeDeepening}
                            onChange={event => syncConfig({ iterativeDeepening: event.target.checked })}
                          />
                        }
                        label="Use Iterative Deepening"
                      />
                    </FormGroup>
                    <TextField
                      label="Time limit (ms)"
                      type="number"
                      size="small"
                      value={config.timeLimitMs}
                      onChange={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        updatePlayer(color, { timeLimitMs: nextValue });
                      }}
                      onBlur={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        syncConfig({ timeLimitMs: nextValue });
                      }}
                      inputProps={{ step: 50, min: 10, max: 60000 }}
                      fullWidth
                      disabled={!config.iterativeDeepening}
                      sx={{ mt: 2 }}
                    />
                    <TextField
                      label="Max quiescence depth"
                      type="number"
                      size="small"
                      value={config.maxQuiescenceDepth}
                      onChange={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        updatePlayer(color, { maxQuiescenceDepth: nextValue });
                      }}
                      onBlur={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        syncConfig({ maxQuiescenceDepth: nextValue });
                      }}
                      inputProps={{ step: 1, min: 1, max: 16 }}
                      fullWidth
                      sx={{ mt: 2 }}
                    />
                  </AccordionDetails>
                </Accordion>
                <Accordion elevation={0} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Parallel search</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <FormGroup>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.parallel}
                            onChange={event => syncConfig({ parallel: event.target.checked })}
                          />
                        }
                        label="Enable Parallel Search"
                      />
                    </FormGroup>
                    <TextField
                      label="Workers"
                      type="number"
                      size="small"
                      value={config.workers}
                      onChange={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        updatePlayer(color, { workers: nextValue });
                      }}
                      onBlur={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        syncConfig({ workers: nextValue });
                      }}
                      inputProps={{ step: 1, min: 1, max: 16 }}
                      fullWidth
                      disabled={!config.parallel}
                      sx={{ mt: 2 }}
                    />
                  </AccordionDetails>
                </Accordion>
                <Divider />
              </>
            )}
            {isMcts && (
              <>
                <Typography variant="body2">Iterations</Typography>
                <Slider
                  value={config.iterations}
                  onChange={(_, val) => updatePlayer(color, { iterations: val })}
                  onChangeCommitted={(_, val) => syncConfig({ iterations: val })}
                  min={50}
                  max={5000}
                  step={50}
                  valueLabelDisplay="auto"
                  marks
                />
                <Typography variant="body2">Rollout depth</Typography>
                <Slider
                  value={config.rolloutDepth}
                  onChange={(_, val) => updatePlayer(color, { rolloutDepth: val })}
                  onChangeCommitted={(_, val) => syncConfig({ rolloutDepth: val })}
                  min={10}
                  max={200}
                  step={5}
                  valueLabelDisplay="auto"
                  marks
                />
                <Accordion elevation={0} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Advanced</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <TextField
                      label="Exploration constant (C)"
                      type="number"
                      size="small"
                      value={config.explorationConstant}
                      onChange={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        updatePlayer(color, { explorationConstant: nextValue });
                      }}
                      onBlur={event => {
                        const nextValue = Number(event.target.value);
                        if (Number.isNaN(nextValue)) return;
                        syncConfig({ explorationConstant: nextValue });
                      }}
                      inputProps={{ step: 0.1, min: 0.1, max: 10 }}
                      fullWidth
                    />
                  </AccordionDetails>
                </Accordion>
              </>
            )}
            {showPerformButton && (
              <Button variant="contained" onClick={handlePerformMove} disabled={performing}>
                Perform move
              </Button>
            )}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
};

export default PlayerConfigCard;
