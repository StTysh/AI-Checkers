import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  Stack,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  TextField,
  FormControlLabel,
  Switch,
  Button,
  ButtonGroup,
  Typography,
  LinearProgress,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
  Divider,
} from "@mui/material";
import { VARIANTS } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const EvaluationPanel = () => {
  const { store, api } = useGameContext();
  const playerConfig = store(state => state.playerConfig);

  const [variant, setVariant] = useState(store.getState().variant);
  const [games, setGames] = useState(10);
  const [startPolicy, setStartPolicy] = useState("alternate");
  const [randomSeed, setRandomSeed] = useState("");
  const [randomizeOpening, setRandomizeOpening] = useState(false);
  const [randomizePlies, setRandomizePlies] = useState(2);
  const [resetAfterRun, setResetAfterRun] = useState(false);

  const [evaluationId, setEvaluationId] = useState(null);
  const [status, setStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef(null);

  const [snapshotConfig, setSnapshotConfig] = useState(() => ({
    white: playerConfig.white,
    black: playerConfig.black,
  }));

  const numberSetter = setter => event => setter(Number(event.target.value));

  const describeConfig = config => {
    if (config.type === "minimax") {
      return `Minimax d=${config.depth}, id=${config.iterativeDeepening ? "on" : "off"}, t=${config.timeLimitMs}ms, p=${config.parallel ? config.workers : 1}`;
    }
    if (config.type === "mcts") {
      return `MCTS iter=${config.iterations}, depth=${config.rolloutDepth}, policy=${config.rolloutPolicy}`;
    }
    return "Human";
  };

  const startEvaluation = async () => {
    const payload = {
      games,
      variant,
      startPolicy,
      randomSeed: randomSeed === "" ? null : Number(randomSeed),
      randomizeOpening,
      randomizePlies,
      resetConfigsAfterRun: resetAfterRun,
      white: snapshotConfig.white,
      black: snapshotConfig.black,
    };
    const response = await api.startEvaluation(payload);
    setEvaluationId(response.evaluationId);
    setStatus(response);
    setRunning(true);
  };

  const stopEvaluation = async () => {
    if (!evaluationId) return;
    await api.stopEvaluation(evaluationId);
    setRunning(false);
  };

  useEffect(() => {
    if (!running || !evaluationId) return;
    pollRef.current = window.setInterval(async () => {
      const data = await api.getEvaluationStatus(evaluationId);
      setStatus(prev => {
        if (!prev) return data;
        const changed =
          prev.running !== data.running ||
          prev.completedGames !== data.completedGames ||
          prev.totalGames !== data.totalGames ||
          prev.score?.whiteWins !== data.score?.whiteWins ||
          prev.score?.blackWins !== data.score?.blackWins ||
          prev.score?.draws !== data.score?.draws ||
          (prev.results?.length ?? 0) !== (data.results?.length ?? 0);
        return changed ? data : prev;
      });
      if (!data.running) {
        setRunning(false);
      }
    }, 1000);

    return () => window.clearInterval(pollRef.current);
  }, [api, evaluationId, running]);

  const downloadResults = async format => {
    if (!evaluationId) return;
    const data = await api.getEvaluationResults(evaluationId, format);
    const blob = new Blob([format === "json" ? JSON.stringify(data, null, 2) : data], {
      type: format === "json" ? "application/json" : "text/csv",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `evaluation_${evaluationId}.${format}`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Stack spacing={2}>
      <Card>
        <CardHeader title="Experiment Setup" />
        <CardContent>
          <Stack spacing={2}>
            <FormControl fullWidth size="small">
              <InputLabel>Variant</InputLabel>
              <Select value={variant} label="Variant" onChange={event => setVariant(event.target.value)}>
                {VARIANTS.map(option => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="Number of games"
              type="number"
              size="small"
              value={games}
              onChange={numberSetter(setGames)}
              inputProps={{ min: 1, max: 500, step: 1 }}
            />
            <FormControl fullWidth size="small">
              <InputLabel>Starting player</InputLabel>
              <Select value={startPolicy} label="Starting player" onChange={event => setStartPolicy(event.target.value)}>
                <MenuItem value="alternate">Alternate start</MenuItem>
                <MenuItem value="white">Always White starts</MenuItem>
                <MenuItem value="black">Always Black starts</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Random seed (optional)"
              type="number"
              size="small"
              value={randomSeed}
              onChange={event => setRandomSeed(event.target.value)}
            />
            <FormControlLabel
              control={<Switch checked={randomizeOpening} onChange={event => setRandomizeOpening(event.target.checked)} />}
              label="Randomize opening moves"
            />
            <TextField
              label="Opening plies"
              type="number"
              size="small"
              value={randomizePlies}
              onChange={numberSetter(setRandomizePlies)}
              inputProps={{ min: 0, max: 12, step: 1 }}
              disabled={!randomizeOpening}
            />
            <FormControlLabel
              control={<Switch checked={resetAfterRun} onChange={event => setResetAfterRun(event.target.checked)} />}
              label="Reset configs after run"
            />
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="AI Configuration Snapshot" />
        <CardContent>
          <Stack spacing={1}>
            <Typography variant="body2">White: {describeConfig(snapshotConfig.white)}</Typography>
            <Typography variant="body2">Black: {describeConfig(snapshotConfig.black)}</Typography>
            <Divider />
            <Button
              size="small"
              variant="outlined"
              onClick={() => setSnapshotConfig({ white: playerConfig.white, black: playerConfig.black })}
            >
              Use current player settings
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Run Controls" />
        <CardContent>
          <Stack spacing={2}>
            <ButtonGroup fullWidth>
              <Button variant="contained" onClick={startEvaluation} disabled={running}>
                Run evaluation
              </Button>
              <Button variant="outlined" onClick={stopEvaluation} disabled={!running}>
                Stop
              </Button>
            </ButtonGroup>
            {running && <LinearProgress />}
            {status && (
              <Typography variant="body2" color="text.secondary">
                {status.completedGames} / {status.totalGames} games completed
              </Typography>
            )}
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Results" />
        <CardContent>
          {!status && <Typography variant="body2" color="text.secondary">No results yet.</Typography>}
          {status && (
            <Stack spacing={2}>
              <Stack direction="row" spacing={2}>
                <Typography variant="body2">White wins: {status.score?.whiteWins ?? 0}</Typography>
                <Typography variant="body2">Black wins: {status.score?.blackWins ?? 0}</Typography>
                <Typography variant="body2">Draws: {status.score?.draws ?? 0}</Typography>
              </Stack>
              <Typography variant="body2">
                Avg moves: {status.summary?.avgMoves?.toFixed(2) ?? "0"} | Avg duration: {status.summary?.avgDuration?.toFixed(2) ?? "0"}s
                {` | Avg move time W: ${status.summary?.avgMoveTimeWhite?.toFixed(3) ?? "0"}s, B: ${
                  status.summary?.avgMoveTimeBlack?.toFixed(3) ?? "0"
                }s`}
              </Typography>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Winner</TableCell>
                    <TableCell>Moves</TableCell>
                    <TableCell>Duration (s)</TableCell>
                    <TableCell>Avg move time (W/B)</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {status.results?.map(result => (
                    <TableRow key={result.index}>
                      <TableCell>{result.index}</TableCell>
                      <TableCell>{result.winner ?? "draw"}</TableCell>
                      <TableCell>{result.moveCount}</TableCell>
                      <TableCell>{result.durationSeconds?.toFixed(2)}</TableCell>
                      <TableCell>
                        {result.avgMoveTimeWhite?.toFixed(3)} / {result.avgMoveTimeBlack?.toFixed(3)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Stack>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Export" />
        <CardContent>
          <ButtonGroup fullWidth>
            <Button onClick={() => downloadResults("csv")} disabled={!evaluationId}>
              Download CSV
            </Button>
            <Button onClick={() => downloadResults("json")} disabled={!evaluationId}>
              Download JSON
            </Button>
          </ButtonGroup>
        </CardContent>
      </Card>
    </Stack>
  );
};

export default EvaluationPanel;
