import { useEffect, useMemo, useRef, useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  Stack,
  Box,
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
  Accordion,
  AccordionSummary,
  AccordionDetails,
  ToggleButton,
  ToggleButtonGroup,
  Chip,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { VARIANTS } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const PRESET_STORAGE_KEY = "checkers_eval_presets_v1";

const DEFAULTS = {
  games: 10,
  startPolicy: "alternate",
  randomSeed: "",
  randomizeOpening: false,
  randomizePlies: 2,
  resetAfterRun: false,
  experimentName: "",
  notes: "",
  drawPolicy: "half",
  fairnessLock: false,
  sweepMode: false,
  sweepParam: "timeLimitMs",
  sweepValues: "1000,2000,5000,10000,20000",
  sweepSide: "white",
};

const SWEEP_PARAMS = [
  { value: "timeLimitMs", label: "Minimax: time limit (ms)", type: "number" },
  { value: "depth", label: "Minimax: max depth", type: "number" },
  { value: "workers", label: "Minimax: workers", type: "number" },
  { value: "transposition", label: "Minimax: TT on/off", type: "boolean" },
  { value: "quiescence", label: "Minimax: quiescence on/off", type: "boolean" },
  { value: "moveOrdering", label: "Minimax: move ordering on/off", type: "boolean" },
  { value: "iterations", label: "MCTS: iterations", type: "number" },
  { value: "rolloutDepth", label: "MCTS: rollout depth", type: "number" },
  { value: "mctsWorkers", label: "MCTS: workers", type: "number" },
  { value: "rolloutPolicy", label: "MCTS: rollout policy", type: "enum", options: ["random", "heuristic", "minimax_guided"] },
  { value: "leafEvaluation", label: "MCTS: leaf evaluation", type: "enum", options: ["random_terminal", "heuristic_eval", "minimax_eval"] },
];

const createPresetId = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `preset-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const EvaluationPanel = () => {
  const { store, api } = useGameContext();
  const playerConfig = store(state => state.playerConfig);

  const [variant, setVariant] = useState(store.getState().variant);
  const [games, setGames] = useState(DEFAULTS.games);
  const [startPolicy, setStartPolicy] = useState(DEFAULTS.startPolicy);
  const [randomSeed, setRandomSeed] = useState(DEFAULTS.randomSeed);
  const [randomizeOpening, setRandomizeOpening] = useState(DEFAULTS.randomizeOpening);
  const [randomizePlies, setRandomizePlies] = useState(DEFAULTS.randomizePlies);
  const [resetAfterRun, setResetAfterRun] = useState(DEFAULTS.resetAfterRun);
  const [experimentName, setExperimentName] = useState(DEFAULTS.experimentName);
  const [notes, setNotes] = useState(DEFAULTS.notes);
  const [drawPolicy, setDrawPolicy] = useState(DEFAULTS.drawPolicy);
  const [fairnessLock, setFairnessLock] = useState(DEFAULTS.fairnessLock);
  const [sweepMode, setSweepMode] = useState(DEFAULTS.sweepMode);
  const [sweepParam, setSweepParam] = useState(DEFAULTS.sweepParam);
  const [sweepValues, setSweepValues] = useState(DEFAULTS.sweepValues);
  const [sweepSide, setSweepSide] = useState(DEFAULTS.sweepSide);
  const [presetName, setPresetName] = useState("");
  const [presets, setPresets] = useState([]);
  const [selectedPreset, setSelectedPreset] = useState("");
  const [showAllDiff, setShowAllDiff] = useState(false);
  const [copied, setCopied] = useState(false);
  const [sweepRunning, setSweepRunning] = useState(false);
  const [sweepStopRequested, setSweepStopRequested] = useState(false);
  const [sweepResults, setSweepResults] = useState([]);
  const [sweepStatus, setSweepStatus] = useState(null);

  const [evaluationId, setEvaluationId] = useState(null);
  const [status, setStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const pollRef = useRef(null);

  const [snapshotConfig, setSnapshotConfig] = useState(() => ({
    white: playerConfig.white,
    black: playerConfig.black,
  }));

  const numberSetter = setter => event => setter(Number(event.target.value));

  useEffect(() => {
    const stored = localStorage.getItem(PRESET_STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setPresets(parsed);
        }
      } catch {
        // ignore invalid
      }
    }
  }, []);

  const persistPresets = next => {
    setPresets(next);
    localStorage.setItem(PRESET_STORAGE_KEY, JSON.stringify(next));
  };

  const resetToDefaults = () => {
    setGames(DEFAULTS.games);
    setStartPolicy(DEFAULTS.startPolicy);
    setRandomSeed(DEFAULTS.randomSeed);
    setRandomizeOpening(DEFAULTS.randomizeOpening);
    setRandomizePlies(DEFAULTS.randomizePlies);
    setResetAfterRun(DEFAULTS.resetAfterRun);
    setExperimentName(DEFAULTS.experimentName);
    setNotes(DEFAULTS.notes);
    setDrawPolicy(DEFAULTS.drawPolicy);
    setFairnessLock(DEFAULTS.fairnessLock);
    setSweepMode(DEFAULTS.sweepMode);
    setSweepParam(DEFAULTS.sweepParam);
    setSweepValues(DEFAULTS.sweepValues);
    setSweepSide(DEFAULTS.sweepSide);
  };

  const describeConfig = config => {
    if (config.type === "minimax") {
      return `Minimax d=${config.depth}, id=${config.iterativeDeepening ? "on" : "off"}, t=${config.timeLimitMs}ms, p=${config.parallel ? config.workers : 1}`;
    }
    if (config.type === "mcts") {
      return `MCTS iter=${config.iterations}, depth=${config.rolloutDepth}, policy=${config.rolloutPolicy}`;
    }
    return "Human";
  };

  const buildConfigRows = useMemo(() => {
    const white = snapshotConfig.white;
    const black = snapshotConfig.black;
    const fields = [];
    const pushField = (key, label) => fields.push({ key, label });
    pushField("type", "Algorithm");
    if (white.type === "minimax" || black.type === "minimax") {
      pushField("depth", "Depth");
      pushField("timeLimitMs", "Time limit (ms)");
      pushField("parallel", "Parallel");
      pushField("workers", "Workers");
      pushField("alphaBeta", "Alpha–Beta");
      pushField("transposition", "Transposition");
      pushField("moveOrdering", "Move ordering");
      pushField("killerMoves", "Killer moves");
      pushField("quiescence", "Quiescence");
      pushField("maxQuiescenceDepth", "Max quiescence depth");
      pushField("iterativeDeepening", "Iterative deepening");
      pushField("aspiration", "Aspiration windows");
      pushField("nullMove", "Null‑move pruning");
      pushField("lmr", "Late move reductions");
      pushField("endgameTablebase", "Endgame tablebase");
    }
    if (white.type === "mcts" || black.type === "mcts") {
      pushField("iterations", "Iterations");
      pushField("rolloutDepth", "Rollout depth");
      pushField("explorationConstant", "Exploration constant");
      pushField("mctsParallel", "Parallel");
      pushField("mctsWorkers", "Workers");
      pushField("rolloutPolicy", "Rollout policy");
      pushField("leafEvaluation", "Leaf evaluation");
      pushField("guidanceDepth", "Guidance depth");
      pushField("rolloutCutoffDepth", "Rollout cutoff depth");
      pushField("mctsTransposition", "Transposition");
      pushField("progressiveWidening", "Progressive widening");
    }
    return fields;
  }, [snapshotConfig]);

  const formatValue = value => {
    if (value === undefined || value === null) return "–";
    if (typeof value === "boolean") return value ? "on" : "off";
    return String(value);
  };

  const diffRows = useMemo(() => {
    const white = snapshotConfig.white;
    const black = snapshotConfig.black;
    return buildConfigRows
      .map(row => ({
        label: row.label,
        white: formatValue(white[row.key]),
        black: formatValue(black[row.key]),
      }))
      .filter(row => showAllDiff || row.white !== row.black);
  }, [buildConfigRows, snapshotConfig, showAllDiff]);

  const applyFairnessLock = configs => {
    const next = {
      white: { ...configs.white },
      black: { ...configs.black },
    };
    if (next.white.type === "minimax" && next.black.type === "minimax") {
      const minDepth = Math.min(next.white.depth ?? 1, next.black.depth ?? 1);
      const minTime = Math.min(next.white.timeLimitMs ?? 1, next.black.timeLimitMs ?? 1);
      next.white.depth = minDepth;
      next.black.depth = minDepth;
      next.white.timeLimitMs = minTime;
      next.black.timeLimitMs = minTime;
      if (next.white.parallel && next.black.parallel) {
        const minWorkers = Math.min(next.white.workers ?? 1, next.black.workers ?? 1);
        next.white.workers = minWorkers;
        next.black.workers = minWorkers;
      } else {
        next.white.parallel = false;
        next.black.parallel = false;
        next.white.workers = 1;
        next.black.workers = 1;
      }
    }
    if (next.white.type === "mcts" && next.black.type === "mcts") {
      const minIterations = Math.min(next.white.iterations ?? 1, next.black.iterations ?? 1);
      const minDepth = Math.min(next.white.rolloutDepth ?? 1, next.black.rolloutDepth ?? 1);
      next.white.iterations = minIterations;
      next.black.iterations = minIterations;
      next.white.rolloutDepth = minDepth;
      next.black.rolloutDepth = minDepth;
      if (next.white.mctsParallel && next.black.mctsParallel) {
        const minWorkers = Math.min(next.white.mctsWorkers ?? 1, next.black.mctsWorkers ?? 1);
        next.white.mctsWorkers = minWorkers;
        next.black.mctsWorkers = minWorkers;
      } else {
        next.white.mctsParallel = false;
        next.black.mctsParallel = false;
        next.white.mctsWorkers = 1;
        next.black.mctsWorkers = 1;
      }
    }
    return next;
  };

  const getEffectiveSnapshot = () => {
    if (!fairnessLock || sweepMode) {
      return {
        white: { ...snapshotConfig.white },
        black: { ...snapshotConfig.black },
      };
    }
    return applyFairnessLock(snapshotConfig);
  };

  const drawScoreValue = drawPolicy === "zero" ? 0 : drawPolicy === "ignore" ? null : 0.5;

  const scoreStats = useMemo(() => {
    if (!status) return null;
    const whiteWins = status.score?.whiteWins ?? 0;
    const blackWins = status.score?.blackWins ?? 0;
    const draws = status.score?.draws ?? 0;
    const total = whiteWins + blackWins + draws;
    const nEff = drawPolicy === "ignore" ? whiteWins + blackWins : total;
    if (nEff === 0) {
      return {
        whiteWins,
        blackWins,
        draws,
        total,
        nEff: 0,
        pWhite: null,
        pBlack: null,
      };
    }
    const drawScore = drawScoreValue ?? 0;
    const pWhite = (whiteWins + drawScore * draws) / nEff;
    const pBlack = (blackWins + drawScore * draws) / nEff;
    return {
      whiteWins,
      blackWins,
      draws,
      total,
      nEff,
      pWhite,
      pBlack,
    };
  }, [status, drawPolicy, drawScoreValue]);

  const wilsonInterval = (successes, n, z = 1.96) => {
    if (!n || n <= 0) return null;
    const phat = successes / n;
    const z2 = z * z;
    const denom = 1 + z2 / n;
    const center = phat + z2 / (2 * n);
    const margin = z * Math.sqrt((phat * (1 - phat) + z2 / (4 * n)) / n);
    return {
      low: (center - margin) / denom,
      high: (center + margin) / denom,
    };
  };

  const eloEstimate = p => {
    if (p === null || p <= 0 || p >= 1) return null;
    return 400 * Math.log10(p / (1 - p));
  };

  const confidence = useMemo(() => {
    if (!scoreStats || scoreStats.nEff === 0) return null;
    const drawScore = drawScoreValue ?? 0;
    const whiteSuccess = scoreStats.whiteWins + drawScore * scoreStats.draws;
    const blackSuccess = scoreStats.blackWins + drawScore * scoreStats.draws;
    return {
      white: wilsonInterval(whiteSuccess, scoreStats.nEff),
      black: wilsonInterval(blackSuccess, scoreStats.nEff),
    };
  }, [scoreStats, drawScoreValue]);

  const elo = useMemo(() => {
    if (!scoreStats || scoreStats.nEff === 0) return null;
    return eloEstimate(scoreStats.pWhite);
  }, [scoreStats]);

  const parseSweepValues = () => {
    const param = SWEEP_PARAMS.find(item => item.value === sweepParam);
    if (!param) return [];
    const tokens = sweepValues.split(",").map(val => val.trim()).filter(Boolean);
    if (param.type === "number") {
      return tokens.map(val => Number(val)).filter(val => !Number.isNaN(val));
    }
    if (param.type === "boolean") {
      return tokens.map(val => {
        const lower = val.toLowerCase();
        if (["true", "1", "on", "yes"].includes(lower)) return true;
        if (["false", "0", "off", "no"].includes(lower)) return false;
        return null;
      }).filter(val => val !== null);
    }
    if (param.type === "enum") {
      return tokens.filter(val => param.options.includes(val));
    }
    return [];
  };

  const applySweepValue = (configs, value) => {
    const next = {
      white: { ...configs.white },
      black: { ...configs.black },
    };
    const target = sweepSide === "white" ? next.white : next.black;
    target[sweepParam] = value;
    return next;
  };

  const startEvaluation = async (configOverride, options = { setRunningState: true }) => {
    const effective = configOverride ?? getEffectiveSnapshot();
    const payload = {
      games,
      variant,
      startPolicy,
      randomSeed: randomSeed === "" ? null : Number(randomSeed),
      randomizeOpening,
      randomizePlies,
      resetConfigsAfterRun: resetAfterRun,
      experimentName: experimentName || null,
      notes: notes || null,
      drawPolicy,
      white: effective.white,
      black: effective.black,
    };
    const response = await api.startEvaluation(payload);
    setEvaluationId(response.evaluationId);
    setStatus(response);
    if (options.setRunningState !== false) {
      setRunning(true);
    }
    return response.evaluationId;
  };

  const stopEvaluation = async () => {
    if (!evaluationId) return;
    await api.stopEvaluation(evaluationId);
    setRunning(false);
  };

  const runSweep = async () => {
    if (sweepRunning) return;
    const values = parseSweepValues();
    if (!values.length) return;
    setSweepRunning(true);
    setSweepStopRequested(false);
    setSweepResults([]);
    for (const value of values) {
      if (sweepStopRequested) break;
      const base = {
        white: { ...snapshotConfig.white },
        black: { ...snapshotConfig.black },
      };
      const config = applySweepValue(base, value);
      setSweepStatus({ value, running: true });
      const evalId = await startEvaluation(config, { setRunningState: false });
      let finished = false;
      while (!finished) {
        await new Promise(resolve => setTimeout(resolve, 900));
        const data = await api.getEvaluationStatus(evalId);
        setStatus(data);
        if (!data.running) {
          finished = true;
          setRunning(false);
          setSweepResults(prev => [
            ...prev,
            {
              value,
              score: data.score,
              summary: data.summary,
              totalGames: data.totalGames,
            },
          ]);
        }
        if (sweepStopRequested && data.running) {
          await api.stopEvaluation(evalId);
        }
      }
    }
    setSweepStatus(null);
    setSweepRunning(false);
  };

  const stopSweep = async () => {
    setSweepStopRequested(true);
    if (evaluationId) {
      await api.stopEvaluation(evaluationId);
    }
  };

  const downloadSweepCsv = () => {
    const header = ["value", "whiteWins", "blackWins", "draws", "winRateWhite", "winRateBlack", "avgMoves", "avgDuration", "avgMoveTimeWhite", "avgMoveTimeBlack"];
    const rows = sweepResults.map(row => [
      row.value,
      row.score?.whiteWins ?? 0,
      row.score?.blackWins ?? 0,
      row.score?.draws ?? 0,
      row.summary?.winRateWhite ?? 0,
      row.summary?.winRateBlack ?? 0,
      row.summary?.avgMoves ?? 0,
      row.summary?.avgDuration ?? 0,
      row.summary?.avgMoveTimeWhite ?? 0,
      row.summary?.avgMoveTimeBlack ?? 0,
    ]);
    const csv = [header.join(","), ...rows.map(r => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "sweep_results.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const copySummary = async () => {
    if (!status || !scoreStats) return;
    const effective = getEffectiveSnapshot();
    const lines = [
      `Experiment: ${experimentName || "(unnamed)"}`,
      `Variant: ${variant}`,
      `Games: ${status.totalGames}`,
      `White: ${describeConfig(effective.white)}`,
      `Black: ${describeConfig(effective.black)}`,
      `W/D/L: ${scoreStats.whiteWins}/${scoreStats.draws}/${scoreStats.blackWins}`,
      `Win rates: W ${(scoreStats.pWhite ?? 0).toFixed(3)}, B ${(scoreStats.pBlack ?? 0).toFixed(3)} (draw policy: ${drawPolicy})`,
      `Avg moves: ${status.summary?.avgMoves?.toFixed(2) ?? "0"}, Avg duration: ${status.summary?.avgDuration?.toFixed(2) ?? "0"}s`,
      `Avg move time W: ${status.summary?.avgMoveTimeWhite?.toFixed(3) ?? "0"}s, B: ${status.summary?.avgMoveTimeBlack?.toFixed(3) ?? "0"}s`,
    ];
    if (notes) lines.push(`Notes: ${notes}`);
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const savePreset = () => {
    if (!presetName.trim()) return;
    const entry = {
      id: createPresetId(),
      name: presetName.trim(),
      data: {
        variant,
        games,
        startPolicy,
        randomSeed,
        randomizeOpening,
        randomizePlies,
        resetAfterRun,
        experimentName,
        notes,
        drawPolicy,
        fairnessLock,
        sweepMode,
        sweepParam,
        sweepValues,
        sweepSide,
        snapshotConfig,
      },
    };
    persistPresets([...presets, entry]);
    setPresetName("");
    setSelectedPreset(entry.id);
  };

  const loadPreset = () => {
    const preset = presets.find(item => item.id === selectedPreset);
    if (!preset) return;
    const data = preset.data;
    setVariant(data.variant ?? variant);
    setGames(data.games ?? DEFAULTS.games);
    setStartPolicy(data.startPolicy ?? DEFAULTS.startPolicy);
    setRandomSeed(data.randomSeed ?? DEFAULTS.randomSeed);
    setRandomizeOpening(data.randomizeOpening ?? DEFAULTS.randomizeOpening);
    setRandomizePlies(data.randomizePlies ?? DEFAULTS.randomizePlies);
    setResetAfterRun(data.resetAfterRun ?? DEFAULTS.resetAfterRun);
    setExperimentName(data.experimentName ?? DEFAULTS.experimentName);
    setNotes(data.notes ?? DEFAULTS.notes);
    setDrawPolicy(data.drawPolicy ?? DEFAULTS.drawPolicy);
    setFairnessLock(data.fairnessLock ?? DEFAULTS.fairnessLock);
    setSweepMode(data.sweepMode ?? DEFAULTS.sweepMode);
    setSweepParam(data.sweepParam ?? DEFAULTS.sweepParam);
    setSweepValues(data.sweepValues ?? DEFAULTS.sweepValues);
    setSweepSide(data.sweepSide ?? DEFAULTS.sweepSide);
    if (data.snapshotConfig) {
      setSnapshotConfig(data.snapshotConfig);
    }
  };

  const deletePreset = () => {
    if (!selectedPreset) return;
    persistPresets(presets.filter(item => item.id !== selectedPreset));
    setSelectedPreset("");
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

  const hasResults = Boolean(status?.results?.length);
  const effectiveSnapshot = getEffectiveSnapshot();

  return (
    <Stack spacing={2}>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "2fr 1fr" },
          gap: 2,
          alignItems: "stretch",
        }}
      >
        <Card sx={{ height: "100%" }}>
          <CardHeader title="Experiment Setup" />
          <CardContent sx={{ pt: 1.5, overflowX: "hidden" }}>
            <Stack spacing={2} sx={{ width: "100%", minWidth: 0 }}>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
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
                <FormControl fullWidth size="small">
                  <InputLabel>Starting player</InputLabel>
                  <Select value={startPolicy} label="Starting player" onChange={event => setStartPolicy(event.target.value)}>
                    <MenuItem value="alternate">Alternate start</MenuItem>
                    <MenuItem value="white">Always White starts</MenuItem>
                    <MenuItem value="black">Always Black starts</MenuItem>
                  </Select>
                </FormControl>
                <TextField
                  label="Number of games"
                  type="number"
                  size="small"
                  value={games}
                  onChange={numberSetter(setGames)}
                  inputProps={{ min: 1, max: 500, step: 1 }}
                  fullWidth
                />
                <TextField
                  label="Experiment name"
                  type="text"
                  size="small"
                  value={experimentName}
                  onChange={event => setExperimentName(event.target.value)}
                  fullWidth
                />
              </Box>
              <TextField
                label="Notes"
                multiline
                minRows={2}
                value={notes}
                onChange={event => setNotes(event.target.value)}
                fullWidth
                sx={{
                  width: "100%",
                  minWidth: 0,
                  "& .MuiInputBase-root": { width: "100%", boxSizing: "border-box" },
                  "& textarea": { resize: "vertical", boxSizing: "border-box" },
                }}
              />
              <Accordion elevation={0} disableGutters>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">Advanced Options</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                    <TextField
                      label="Random seed (optional)"
                      type="number"
                      size="small"
                      value={randomSeed}
                      onChange={event => setRandomSeed(event.target.value)}
                      fullWidth
                    />
                    <TextField
                      label="Opening plies"
                      type="number"
                      size="small"
                      value={randomizePlies}
                      onChange={numberSetter(setRandomizePlies)}
                      inputProps={{ min: 0, max: 12, step: 1 }}
                      disabled={!randomizeOpening}
                      fullWidth
                    />
                    <FormControlLabel
                      control={<Switch checked={randomizeOpening} onChange={event => setRandomizeOpening(event.target.checked)} />}
                      label="Randomize opening moves"
                    />
                    <FormControlLabel
                      control={<Switch checked={resetAfterRun} onChange={event => setResetAfterRun(event.target.checked)} />}
                      label="Reset configs after run"
                    />
                  </Box>
                </AccordionDetails>
              </Accordion>
              <Stack spacing={1.5}>
                <Typography variant="subtitle2">Experiment Profile / Preset</Typography>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "2fr 1fr" }, gap: 2 }}>
                  <FormControl fullWidth size="small">
                    <InputLabel>Preset</InputLabel>
                    <Select value={selectedPreset} label="Preset" onChange={event => setSelectedPreset(event.target.value)}>
                      <MenuItem value="">(none)</MenuItem>
                      {presets.map(preset => (
                        <MenuItem key={preset.id} value={preset.id}>{preset.name}</MenuItem>
                      ))}
                    </Select>
                  </FormControl>
                  <TextField
                    label="New preset name"
                    size="small"
                    value={presetName}
                    onChange={event => setPresetName(event.target.value)}
                    fullWidth
                  />
                </Box>
                <ButtonGroup size="small">
                  <Button onClick={savePreset}>Save preset</Button>
                  <Button onClick={loadPreset} disabled={!selectedPreset}>Load preset</Button>
                  <Button onClick={resetToDefaults}>Reset to defaults</Button>
                  <Button onClick={deletePreset} disabled={!selectedPreset}>Delete preset</Button>
                </ButtonGroup>
              </Stack>
              <Stack spacing={2}>
                <Typography variant="subtitle2">Mode</Typography>
                <ToggleButtonGroup
                  exclusive
                  value={sweepMode ? "sweep" : "single"}
                  onChange={(_, val) => setSweepMode(val === "sweep")}
                  size="small"
                  sx={{ mb: 1 }}
                >
                  <ToggleButton value="single">Single Run</ToggleButton>
                  <ToggleButton value="sweep">Sweep Mode</ToggleButton>
                </ToggleButtonGroup>
                {sweepMode && (
                  <Box sx={{ mt: 2.5, display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Parameter</InputLabel>
                      <Select value={sweepParam} label="Parameter" onChange={event => setSweepParam(event.target.value)}>
                        {SWEEP_PARAMS.map(param => (
                          <MenuItem key={param.value} value={param.value}>{param.label}</MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                    <FormControl fullWidth size="small">
                      <InputLabel>Sweep side</InputLabel>
                      <Select value={sweepSide} label="Sweep side" onChange={event => setSweepSide(event.target.value)}>
                        <MenuItem value="white">White</MenuItem>
                        <MenuItem value="black">Black</MenuItem>
                      </Select>
                    </FormControl>
                    <TextField
                      label="Values (comma-separated)"
                      size="small"
                      value={sweepValues}
                      onChange={event => setSweepValues(event.target.value)}
                      fullWidth
                    />
                    <FormControl fullWidth size="small">
                      <InputLabel>Draw score</InputLabel>
                      <Select value={drawPolicy} label="Draw score" onChange={event => setDrawPolicy(event.target.value)}>
                        <MenuItem value="zero">0 (loss)</MenuItem>
                        <MenuItem value="half">0.5 (half)</MenuItem>
                        <MenuItem value="ignore">Ignore draws</MenuItem>
                      </Select>
                    </FormControl>
                  </Box>
                )}
                {!sweepMode && (
                  <FormControl fullWidth size="small" sx={{ mt: 2.5 }}>
                    <InputLabel>Draw score</InputLabel>
                    <Select value={drawPolicy} label="Draw score" onChange={event => setDrawPolicy(event.target.value)}>
                      <MenuItem value="zero">0 (loss)</MenuItem>
                      <MenuItem value="half">0.5 (half)</MenuItem>
                      <MenuItem value="ignore">Ignore draws</MenuItem>
                    </Select>
                  </FormControl>
                )}
                <FormControlLabel
                  control={
                    <Switch
                      checked={fairnessLock}
                      onChange={event => setFairnessLock(event.target.checked)}
                      disabled={sweepMode}
                    />
                  }
                  label="Lock fairness settings"
                />
                <Typography variant="body2" color="text.secondary">
                  {sweepMode
                    ? "Fairness lock is disabled in sweep mode."
                    : "Both players will use equal compute budgets."}
                </Typography>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
        <Card sx={{ height: "100%" }}>
          <CardHeader title="Run Evaluation" />
          <CardContent sx={{ pt: 1.5 }}>
            <Stack spacing={1.5}>
              <Typography variant="body2">White: {describeConfig(effectiveSnapshot.white)}</Typography>
              <Typography variant="body2">Black: {describeConfig(effectiveSnapshot.black)}</Typography>
              <Button
                size="small"
                variant="outlined"
                onClick={() => setSnapshotConfig({ white: playerConfig.white, black: playerConfig.black })}
              >
                Use current player settings
              </Button>
              <Divider sx={{ my: 0.5 }} />
              <Stack spacing={1}>
                <Typography variant="subtitle2">AI Config Diff</Typography>
                <FormControlLabel
                  control={<Switch checked={showAllDiff} onChange={event => setShowAllDiff(event.target.checked)} />}
                  label="Show all"
                />
                <Stack spacing={0.5}>
                  {diffRows.length === 0 && (
                    <Typography variant="body2" color="text.secondary">No differences.</Typography>
                  )}
                  {diffRows.map(row => (
                    <Box key={row.label} sx={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1 }}>
                      <Typography variant="body2" color="text.secondary">{row.label}</Typography>
                      <Typography variant="body2">{row.white}</Typography>
                      <Typography variant="body2">{row.black}</Typography>
                    </Box>
                  ))}
                </Stack>
              </Stack>
              <Divider sx={{ my: 0.5 }} />
              <ButtonGroup fullWidth>
                <Button
                  variant="contained"
                  onClick={() => (sweepMode ? runSweep() : startEvaluation())}
                  disabled={running || sweepRunning}
                >
                  {sweepMode ? "Run sweep" : "Run evaluation"}
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => (sweepMode ? stopSweep() : stopEvaluation())}
                  disabled={sweepMode ? !sweepRunning : !running}
                >
                  {sweepMode ? "Stop sweep" : "Stop"}
                </Button>
              </ButtonGroup>
              {(running || sweepRunning) && <LinearProgress />}
              {status && (
                <Typography variant="body2" color="text.secondary">
                  {status.completedGames} / {status.totalGames} games completed
                </Typography>
              )}
              {sweepStatus && (
                <Typography variant="body2" color="text.secondary">
                  Sweep value {String(sweepStatus.value)} {sweepStatus.running ? "running" : "completed"}
                </Typography>
              )}
              {scoreStats && (
                <Stack spacing={1}>
                  <Typography variant="body2">Run state: {status?.running ? "Running" : "Completed"}</Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap">
                    <Chip label={`White ${scoreStats.whiteWins}`} size="small" />
                    <Chip label={`Black ${scoreStats.blackWins}`} size="small" />
                    <Chip label={`Draws ${scoreStats.draws}`} size="small" />
                    {scoreStats.pWhite !== null && (
                      <Chip label={`W% ${(scoreStats.pWhite * 100).toFixed(1)}`} size="small" />
                    )}
                    {scoreStats.pBlack !== null && (
                      <Chip label={`B% ${(scoreStats.pBlack * 100).toFixed(1)}`} size="small" />
                    )}
                  </Stack>
                </Stack>
              )}
            </Stack>
          </CardContent>
        </Card>
      </Box>

      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "2fr 1fr" },
          gap: 2,
          alignItems: "stretch",
        }}
      >
        <Card>
          <CardHeader title="Results" />
          <CardContent sx={{ pt: 1.5 }}>
            {!status && <Typography variant="body2" color="text.secondary">No results yet.</Typography>}
            {status && (
              <Stack spacing={2}>
                <Stack direction="row" spacing={1} flexWrap="wrap">
                  <Chip label={`White wins: ${scoreStats.whiteWins}`} size="small" />
                  <Chip label={`Black wins: ${scoreStats.blackWins}`} size="small" />
                  <Chip label={`Draws: ${scoreStats.draws}`} size="small" />
                  {scoreStats.pWhite !== null && (
                    <Chip label={`W% ${(scoreStats.pWhite * 100).toFixed(1)}`} size="small" />
                  )}
                  {scoreStats.pBlack !== null && (
                    <Chip label={`B% ${(scoreStats.pBlack * 100).toFixed(1)}`} size="small" />
                  )}
                  {scoreStats.pWhite !== null && (
                    <Chip label={`Draw% ${((scoreStats.draws / (scoreStats.total || 1)) * 100).toFixed(1)}`} size="small" />
                  )}
                </Stack>
                <Typography variant="body2">
                  Avg moves: {status.summary?.avgMoves?.toFixed(2) ?? "0"} | Avg duration: {status.summary?.avgDuration?.toFixed(2) ?? "0"}s
                  {` | Avg move time W: ${status.summary?.avgMoveTimeWhite?.toFixed(3) ?? "0"}s, B: ${
                    status.summary?.avgMoveTimeBlack?.toFixed(3) ?? "0"
                  }s`}
                </Typography>
                {confidence?.white && confidence?.black && (
                  <Typography variant="body2" color="text.secondary">
                    95% CI — White: [{(confidence.white.low * 100).toFixed(1)}%, {(confidence.white.high * 100).toFixed(1)}%]
                    {` | Black: [${(confidence.black.low * 100).toFixed(1)}%, ${(confidence.black.high * 100).toFixed(1)}%]`}
                  </Typography>
                )}
                {elo !== null && (
                  <Typography variant="body2" color="text.secondary">
                    Estimated Elo advantage (White vs Black): {elo.toFixed(1)} (approx.)
                  </Typography>
                )}
                <Button size="small" variant="outlined" onClick={copySummary}>
                  {copied ? "Copied" : "Copy summary"}
                </Button>
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
          <Box sx={{ display: "flex", justifyContent: "space-between", px: 2, pb: 2 }}>
            <Box>
              {sweepMode && sweepResults.length > 0 && (
                <Button size="small" variant="outlined" onClick={downloadSweepCsv}>
                  Export sweep CSV
                </Button>
              )}
            </Box>
            <ButtonGroup>
              <Button onClick={() => downloadResults("csv")} disabled={!hasResults}>
                Download CSV
              </Button>
              <Button onClick={() => downloadResults("json")} disabled={!hasResults}>
                Download JSON
              </Button>
            </ButtonGroup>
          </Box>
        </Card>
        <Box sx={{ display: { xs: "none", md: "block" } }}>
          {sweepMode && (
            <Card>
              <CardHeader title="Sweep Summary" />
              <CardContent>
                {sweepResults.length === 0 && (
                  <Typography variant="body2" color="text.secondary">No sweep results yet.</Typography>
                )}
                {sweepResults.length > 0 && (
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Value</TableCell>
                        <TableCell>W</TableCell>
                        <TableCell>D</TableCell>
                        <TableCell>L</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {sweepResults.map(row => (
                        <TableRow key={String(row.value)}>
                          <TableCell>{String(row.value)}</TableCell>
                          <TableCell>{row.score?.whiteWins ?? 0}</TableCell>
                          <TableCell>{row.score?.draws ?? 0}</TableCell>
                          <TableCell>{row.score?.blackWins ?? 0}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}
        </Box>
      </Box>
    </Stack>
  );
};

export default EvaluationPanel;
