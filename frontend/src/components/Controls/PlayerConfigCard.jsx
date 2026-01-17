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
  const gameReady = store(state => state.gameReady);
  const manualAiApproval = store(state => state.manualAiApproval);
  const systemInfo = store(state => state.systemInfo);
  const otherColor = color === "white" ? "black" : "white";
  const otherConfig = store(state => state.playerConfig[otherColor]);
  const globalMaxWorkers = systemInfo?.recommendedMaxWorkers ?? 16;
  const [performing, setPerforming] = useState(false);

  const commitConfig = (primaryUpdates, secondaryUpdates) => {
    updatePlayer(color, primaryUpdates);
    if (secondaryUpdates) {
      updatePlayer(otherColor, secondaryUpdates);
    }
    const { playerConfig } = store.getState();
    api.configurePlayers({
      white: playerConfig.white,
      black: playerConfig.black,
    });
  };

  const adjustParallelWorkers = (key, parallelKey, value, commit = false, extraUpdates = {}) => {
    const currentParallel = config[parallelKey];
    const otherKeys =
      otherConfig.type === "mcts"
        ? { parallelKey: "mctsParallel", workersKey: "mctsWorkers" }
        : otherConfig.type === "minimax"
          ? { parallelKey: "parallel", workersKey: "workers" }
          : null;
    const otherParallel = otherKeys ? otherConfig[otherKeys.parallelKey] : false;
    const otherWorkers = otherKeys ? otherConfig[otherKeys.workersKey] || 1 : 1;
    let currentValue = value;
    let secondaryUpdates = null;

    if (currentParallel && otherParallel) {
      const remaining = Math.max(1, globalMaxWorkers - otherWorkers);
      currentValue = Math.min(value, remaining);
      const otherMax = Math.max(1, globalMaxWorkers - currentValue);
      if (otherWorkers > otherMax && otherKeys) {
        secondaryUpdates = { [otherKeys.workersKey]: otherMax };
      }
    }

    const primaryUpdates = { [key]: currentValue, ...extraUpdates };
    if (commit) {
      commitConfig(primaryUpdates, secondaryUpdates);
    } else {
      updatePlayer(color, primaryUpdates);
      if (secondaryUpdates) {
        updatePlayer(otherColor, secondaryUpdates);
      }
    }
  };

  const numberFieldHandlers = (key, maxValue, clampHandler) => ({
    onChange: event => {
      const nextValue = Number(event.target.value);
      if (Number.isNaN(nextValue)) return;
      const clamped = maxValue ? Math.min(nextValue, maxValue) : nextValue;
      if (clampHandler) {
        clampHandler(clamped, false);
        return;
      }
      updatePlayer(color, { [key]: clamped });
    },
    onBlur: event => {
      const nextValue = Number(event.target.value);
      if (Number.isNaN(nextValue)) return;
      const clamped = maxValue ? Math.min(nextValue, maxValue) : nextValue;
      if (clampHandler) {
        clampHandler(clamped, true);
        return;
      }
      syncConfig({ [key]: clamped });
    },
  });

  const sliderHandlers = key => ({
    onChange: (_, val) => updatePlayer(color, { [key]: val }),
    onChangeCommitted: (_, val) => syncConfig({ [key]: val }),
  });


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
  const configLocked = gameMode === "aivai" && gameReady && boardState && !boardState.winner;

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
          <Select
            value={config.type}
            label="Player Type"
            onChange={event => syncConfig({ type: event.target.value })}
            disabled={configLocked}
          >
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
                  {...sliderHandlers("depth")}
                  min={2}
                  max={12}
                  step={1}
                  valueLabelDisplay="auto"
                  marks
                  disabled={configLocked}
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
                        disabled={configLocked}
                      />
                    }
                    label="Enable Alpha–Beta"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.transposition}
                        onChange={event => syncConfig({ transposition: event.target.checked })}
                        disabled={configLocked}
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
                        disabled={configLocked || !config.alphaBeta}
                      />
                    }
                    label="Enable Move Ordering"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.killerMoves}
                        onChange={event => syncConfig({ killerMoves: event.target.checked })}
                        disabled={configLocked || !config.alphaBeta || !config.moveOrdering}
                      />
                    }
                    label="Enable Killer Moves"
                  />
                  <FormControlLabel
                    control={
                      <Switch
                        checked={config.quiescence}
                        onChange={event => syncConfig({ quiescence: event.target.checked })}
                        disabled={configLocked}
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
                            disabled={configLocked}
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
                      {...numberFieldHandlers("timeLimitMs")}
                      inputProps={{ step: 50, min: 10, max: 60000 }}
                      fullWidth
                      disabled={configLocked || !config.iterativeDeepening}
                      sx={{ mt: 2 }}
                    />
                    <TextField
                      label="Max quiescence depth"
                      type="number"
                      size="small"
                      value={config.maxQuiescenceDepth}
                      {...numberFieldHandlers("maxQuiescenceDepth")}
                      inputProps={{ step: 1, min: 1, max: 16 }}
                      fullWidth
                      disabled={configLocked}
                      sx={{ mt: 2 }}
                    />
                  </AccordionDetails>
                </Accordion>
                <Accordion elevation={0} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Advanced pruning</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <FormGroup>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.aspiration}
                            onChange={event => syncConfig({ aspiration: event.target.checked })}
                            disabled={configLocked || !config.alphaBeta}
                          />
                        }
                        label="Use Aspiration Windows"
                      />
                    </FormGroup>
                    <Typography variant="body2">Aspiration window</Typography>
                    <Slider
                      value={config.aspirationWindow}
                      {...sliderHandlers("aspirationWindow")}
                      min={10}
                      max={200}
                      step={5}
                      valueLabelDisplay="auto"
                      marks
                      disabled={configLocked || !config.aspiration}
                    />
                    <FormGroup>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.historyHeuristic}
                            onChange={event => syncConfig({ historyHeuristic: event.target.checked })}
                            disabled={configLocked || !config.moveOrdering}
                          />
                        }
                        label="Enable History Heuristic"
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.butterflyHeuristic}
                            onChange={event => syncConfig({ butterflyHeuristic: event.target.checked })}
                            disabled={configLocked || !config.moveOrdering || !config.historyHeuristic}
                          />
                        }
                        label="Enable Butterfly Heuristic"
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.nullMove}
                            onChange={event => syncConfig({ nullMove: event.target.checked })}
                            disabled={configLocked || !config.alphaBeta}
                          />
                        }
                        label="Enable Null-Move Pruning"
                      />
                    </FormGroup>
                    <Typography variant="body2">Null-move reduction</Typography>
                    <Slider
                      value={config.nullMoveReduction}
                      {...sliderHandlers("nullMoveReduction")}
                      min={1}
                      max={4}
                      step={1}
                      valueLabelDisplay="auto"
                      marks
                      disabled={configLocked || !config.nullMove}
                    />
                    <FormGroup>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.lmr}
                            onChange={event => syncConfig({ lmr: event.target.checked })}
                            disabled={configLocked || !config.alphaBeta || !config.moveOrdering}
                          />
                        }
                        label="Enable Late Move Reductions"
                      />
                    </FormGroup>
                    <Typography variant="body2">LMR reduction</Typography>
                    <Slider
                      value={config.lmrReduction}
                      {...sliderHandlers("lmrReduction")}
                      min={1}
                      max={3}
                      step={1}
                      valueLabelDisplay="auto"
                      marks
                      disabled={configLocked || !config.lmr}
                    />
                    <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mt: 2 }}>
                      <TextField
                        label="LMR min depth"
                        type="number"
                        size="small"
                        value={config.lmrMinDepth}
                        {...numberFieldHandlers("lmrMinDepth")}
                        inputProps={{ step: 1, min: 1, max: 10 }}
                        fullWidth
                        disabled={configLocked || !config.lmr}
                      />
                      <TextField
                        label="LMR min moves"
                        type="number"
                        size="small"
                        value={config.lmrMinMoves}
                        {...numberFieldHandlers("lmrMinMoves")}
                        inputProps={{ step: 1, min: 1, max: 12 }}
                        fullWidth
                        disabled={configLocked || !config.lmr}
                      />
                    </Stack>
                    <FormGroup sx={{ mt: 2 }}>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.deterministicOrdering}
                            onChange={event => syncConfig({ deterministicOrdering: event.target.checked })}
                            disabled={configLocked}
                          />
                        }
                        label="Deterministic fallback ordering"
                      />
                      <FormControlLabel
                        control={
                          <Switch
                            checked={config.endgameTablebase}
                            onChange={event => syncConfig({ endgameTablebase: event.target.checked })}
                            disabled={configLocked}
                          />
                        }
                        label="Enable Endgame Tablebase"
                      />
                    </FormGroup>
                    <Typography variant="body2">Endgame max pieces</Typography>
                    <Slider
                      value={config.endgameMaxPieces}
                      {...sliderHandlers("endgameMaxPieces")}
                      min={2}
                      max={12}
                      step={1}
                      valueLabelDisplay="auto"
                      marks
                      disabled={configLocked || !config.endgameTablebase}
                    />
                    <Typography variant="body2">Endgame max plies</Typography>
                    <Slider
                      value={config.endgameMaxPlies}
                      {...sliderHandlers("endgameMaxPlies")}
                      min={10}
                      max={200}
                      step={5}
                      valueLabelDisplay="auto"
                      marks
                      disabled={configLocked || !config.endgameTablebase}
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
                            onChange={event => {
                              const enabled = event.target.checked;
                              adjustParallelWorkers("workers", "parallel", config.workers, true, { parallel: enabled });
                            }}
                            disabled={configLocked}
                          />
                        }
                        label="Enable Parallel Search"
                      />
                    </FormGroup>
                    <Typography variant="body2">Workers</Typography>
                    <Slider
                      value={config.workers}
                      onChange={(_, val) => adjustParallelWorkers("workers", "parallel", val, false)}
                      onChangeCommitted={(_, val) => adjustParallelWorkers("workers", "parallel", val, true)}
                      min={1}
                      max={globalMaxWorkers}
                      step={1}
                      valueLabelDisplay="auto"
                      marks
                      disabled={configLocked || !config.parallel}
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
                  {...sliderHandlers("iterations")}
                  min={50}
                  max={1000}
                  step={50}
                  valueLabelDisplay="auto"
                  marks
                  disabled={configLocked}
                />
                <Typography variant="body2">Rollout depth</Typography>
                <Slider
                  value={config.rolloutDepth}
                  {...sliderHandlers("rolloutDepth")}
                  min={10}
                  max={100}
                  step={5}
                  valueLabelDisplay="auto"
                  marks
                  disabled={configLocked}
                />
                <Accordion elevation={0} disableGutters>
                  <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                    <Typography variant="subtitle2">Advanced MCTS Settings</Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    <Stack spacing={2}>
                      <TextField
                        label="Exploration constant (C)"
                        type="number"
                        size="small"
                        value={config.explorationConstant}
                        {...numberFieldHandlers("explorationConstant")}
                        inputProps={{ step: 0.1, min: 0.1, max: 10 }}
                        fullWidth
                        disabled={configLocked}
                      />
                      <FormGroup>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={config.mctsParallel}
                              onChange={event => {
                                const enabled = event.target.checked;
                                adjustParallelWorkers("mctsWorkers", "mctsParallel", config.mctsWorkers, true, { mctsParallel: enabled });
                              }}
                              disabled={configLocked}
                            />
                          }
                          label="Enable Parallel MCTS"
                        />
                        <FormControlLabel
                          control={
                            <Switch
                              checked={config.mctsTransposition}
                              onChange={event => syncConfig({ mctsTransposition: event.target.checked })}
                              disabled={configLocked}
                            />
                          }
                          label="Enable MCTS Transposition"
                        />
                      </FormGroup>
                      <Typography variant="body2">Workers</Typography>
                      <Slider
                        value={config.mctsWorkers}
                        onChange={(_, val) => adjustParallelWorkers("mctsWorkers", "mctsParallel", val, false)}
                        onChangeCommitted={(_, val) => adjustParallelWorkers("mctsWorkers", "mctsParallel", val, true)}
                        min={1}
                        max={globalMaxWorkers}
                        step={1}
                        valueLabelDisplay="auto"
                        marks
                        disabled={configLocked || !config.mctsParallel}
                      />
                      <TextField
                        label="Transposition max entries"
                        type="number"
                        size="small"
                        value={config.mctsTranspositionMaxEntries}
                        {...numberFieldHandlers("mctsTranspositionMaxEntries")}
                        inputProps={{ step: 1000, min: 1000, max: 1000000 }}
                        fullWidth
                        disabled={configLocked || !config.mctsTransposition}
                      />
                      <FormGroup>
                        <FormControlLabel
                          control={
                            <Switch
                              checked={config.progressiveWidening}
                              onChange={event => syncConfig({ progressiveWidening: event.target.checked })}
                              disabled={configLocked}
                            />
                          }
                          label="Enable Progressive Widening"
                        />
                      </FormGroup>
                      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                        <TextField
                          label="PW k"
                          type="number"
                          size="small"
                          value={config.pwK}
                          {...numberFieldHandlers("pwK")}
                          inputProps={{ step: 0.1, min: 0.1, max: 10 }}
                          fullWidth
                          disabled={configLocked || !config.progressiveWidening}
                        />
                        <TextField
                          label="PW alpha"
                          type="number"
                          size="small"
                          value={config.pwAlpha}
                          {...numberFieldHandlers("pwAlpha")}
                          inputProps={{ step: 0.05, min: 0.1, max: 1 }}
                          fullWidth
                          disabled={configLocked || !config.progressiveWidening}
                        />
                      </Stack>
                      <FormControl fullWidth size="small">
                        <InputLabel>Rollout policy</InputLabel>
                        <Select
                          value={config.rolloutPolicy}
                          label="Rollout policy"
                          onChange={event => syncConfig({ rolloutPolicy: event.target.value })}
                          disabled={configLocked}
                        >
                          <MenuItem value="random">Random</MenuItem>
                          <MenuItem value="heuristic">Heuristic</MenuItem>
                          <MenuItem value="minimax_guided">Minimax-guided</MenuItem>
                        </Select>
                      </FormControl>
                      <TextField
                        label="Guidance depth"
                        type="number"
                        size="small"
                        value={config.guidanceDepth}
                        {...numberFieldHandlers("guidanceDepth")}
                        inputProps={{ step: 1, min: 1, max: 4 }}
                        fullWidth
                        disabled={configLocked || config.rolloutPolicy !== "minimax_guided"}
                      />
                      <TextField
                        label="Rollout cutoff depth"
                        type="number"
                        size="small"
                        value={config.rolloutCutoffDepth}
                        {...numberFieldHandlers("rolloutCutoffDepth")}
                        inputProps={{ step: 1, min: 1, max: 200 }}
                        fullWidth
                        disabled={configLocked}
                      />
                      <FormControl fullWidth size="small">
                        <InputLabel>Leaf evaluation</InputLabel>
                        <Select
                          value={config.leafEvaluation}
                          label="Leaf evaluation"
                          onChange={event => syncConfig({ leafEvaluation: event.target.value })}
                          disabled={configLocked}
                        >
                          <MenuItem value="random_terminal">Random terminal</MenuItem>
                          <MenuItem value="heuristic_eval">Heuristic eval</MenuItem>
                          <MenuItem value="minimax_eval">Minimax eval</MenuItem>
                        </Select>
                      </FormControl>
                    </Stack>
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
