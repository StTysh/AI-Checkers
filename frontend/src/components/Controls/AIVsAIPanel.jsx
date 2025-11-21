import {
  Card,
  CardHeader,
  CardContent,
  Button,
  Stack,
  Slider,
  Typography,
  Divider,
} from "@mui/material";
import PlayCircleIcon from "@mui/icons-material/PlayCircle";
import PauseCircleIcon from "@mui/icons-material/PauseCircle";
import { SIM_SPEEDS } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const AIVsAIPanel = () => {
  const { store } = useGameContext();
  const gameMode = store(state => state.gameMode);
  const simulation = store(state => state.simulation);
  const toggleSimulation = store(state => state.toggleSimulation);
  const setSimulationSpeed = store(state => state.setSimulationSpeed);

  if (gameMode !== "aivai") return null;

  return (
    <Card>
      <CardHeader title="AI vs AI Lab" subheader="Benchmark bots, pause/resume, adjust pace" />
      <CardContent>
        <Stack spacing={2}>
          <Button
            variant="contained"
            startIcon={simulation.running ? <PauseCircleIcon /> : <PlayCircleIcon />}
            onClick={() => toggleSimulation()}
          >
            {simulation.running ? "Pause simulation" : "Start simulation"}
          </Button>
          <Divider />
          <Typography variant="subtitle2">Simulation speed</Typography>
          <Slider
            value={simulation.speed}
            min={0.25}
            max={5}
            step={null}
            marks={SIM_SPEEDS.map(speed => ({ value: speed.value, label: speed.label }))}
            onChange={(_, val) => setSimulationSpeed(val)}
          />
          <Stack spacing={0.5}>
            <Typography variant="body2" color="text.secondary">
              Moves played: {simulation.stats.moves}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Average time per move: {simulation.stats.avgTimeMs} ms
            </Typography>
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default AIVsAIPanel;
