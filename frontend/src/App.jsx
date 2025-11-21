import { Box } from "@mui/material";
import { GameProvider } from "./context/GameProvider";
import GamePage from "./pages/GamePage";

const App = () => {
  return (
    <GameProvider>
      <Box sx={{ minHeight: "100vh", background: "radial-gradient(circle at top, #1f2539 0%, #101321 60%)" }}>
        <GamePage />
      </Box>
    </GameProvider>
  );
};

export default App;
