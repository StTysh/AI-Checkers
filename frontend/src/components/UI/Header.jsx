import { AppBar, Toolbar, Typography, Stack, Button } from "@mui/material";
import SportsEsportsIcon from "@mui/icons-material/SportsEsports";
import CloudSyncIcon from "@mui/icons-material/CloudSync";

const Header = () => (
  <AppBar position="static" color="transparent" elevation={0} sx={{ mb: 2 }}>
    <Toolbar disableGutters sx={{ justifyContent: "space-between" }}>
      <Stack direction="row" spacing={1.5} alignItems="center">
        <SportsEsportsIcon color="primary" />
        <Typography variant="h6">Checkers AI Playground</Typography>
      </Stack>
      <Button variant="contained" startIcon={<CloudSyncIcon />} href="http://localhost:8000/docs" target="_blank">
        Backend Docs
      </Button>
    </Toolbar>
  </AppBar>
);

export default Header;
