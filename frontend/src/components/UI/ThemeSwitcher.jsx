import { Card, CardHeader, CardContent, FormControlLabel, Switch, ToggleButtonGroup, ToggleButton } from "@mui/material";
import PaletteIcon from "@mui/icons-material/Palette";
import VolumeUpIcon from "@mui/icons-material/VolumeUp";
import VolumeOffIcon from "@mui/icons-material/VolumeOff";
import { useGameContext } from "../../context/GameProvider";

const ThemeSwitcher = () => {
  const { store } = useGameContext();
  const themePreference = store(state => state.themePreference);
  const soundsEnabled = store(state => state.soundsEnabled);
  const setThemePreference = store(state => state.setThemePreference);
  const setSoundsEnabled = store(state => state.setSoundsEnabled);

  return (
    <Card>
      <CardHeader title="Appearance & Accessibility" subheader="Fine-tune board and feedback" />
      <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <ToggleButtonGroup
          color="primary"
          value={themePreference}
          exclusive
          onChange={(_, val) => val && setThemePreference(val)}
          fullWidth
        >
          <ToggleButton value="classic">
            <PaletteIcon fontSize="small" sx={{ mr: 1 }} />
            Classic
          </ToggleButton>
          <ToggleButton value="glass">Glass</ToggleButton>
          <ToggleButton value="neon">Neon</ToggleButton>
          <ToggleButton value="high-contrast">High contrast</ToggleButton>
        </ToggleButtonGroup>

        <FormControlLabel
          control={
            <Switch
              checked={soundsEnabled}
              onChange={event => setSoundsEnabled(event.target.checked)}
              icon={<VolumeOffIcon sx={{ fontSize: 13 }} />}
              checkedIcon={<VolumeUpIcon sx={{ fontSize: 13 }} />}
              sx={{
                transform: "scale(1.8)",
                marginRight: "17px",
                marginLeft: "14px",
                "& .MuiSwitch-switchBase": {
                  top: "3px", 
                  left: "3.5px",
                },
            }}
            />
          }
          label="Sound effects"
        />
      </CardContent>
    </Card>
  );
};

export default ThemeSwitcher;
