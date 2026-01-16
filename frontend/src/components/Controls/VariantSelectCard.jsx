import {
  Card,
  CardHeader,
  CardContent,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Stack,
  FormControlLabel,
  Switch,
} from "@mui/material";
import { VARIANTS } from "../../utils/constants";
import { useGameContext } from "../../context/GameProvider";

const VariantSelectCard = () => {
  const { store, api } = useGameContext();
  const variant = store(state => state.variant);
  const showHints = store(state => state.showHints);
  const showCoordinates = store(state => state.showCoordinates);
  const manualAiApproval = store(state => state.manualAiApproval);
  const setVariant = store(state => state.setVariant);
  const setShowHints = store(state => state.setShowHints);
  const setShowCoordinates = store(state => state.setShowCoordinates);
  const setManualAiApproval = store(state => state.setManualAiApproval);

  const handleVariantChange = async event => {
    const value = event.target.value;
    setVariant(value);
    await api.changeVariant(value);
  };

  return (
    <Card sx={{ height: "100%" }}>
      <CardHeader title="Game Variant" subheader="Swap rulesets on the fly" />
      <CardContent>
        <FormControl fullWidth size="small">
          <InputLabel>Variant</InputLabel>
          <Select value={variant} label="Variant" onChange={handleVariantChange}>
            {VARIANTS.map(option => (
              <MenuItem key={option.value} value={option.value}>
                {option.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <Stack spacing={1} mt={2}>
          <FormControlLabel
            control={<Switch checked={showHints} onChange={event => setShowHints(event.target.checked)} />}
            label="Show move hints"
          />
          <FormControlLabel
            control={<Switch checked={showCoordinates} onChange={event => setShowCoordinates(event.target.checked)} />}
            label="Show coordinates"
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
            label="Manual AI move approval"
          />
        </Stack>
      </CardContent>
    </Card>
  );
};

export default VariantSelectCard;
