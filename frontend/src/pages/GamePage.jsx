import { Box, Container, Grid, Tabs, Tab } from "@mui/material";
import Header from "../components/UI/Header";
import Footer from "../components/UI/Footer";
import Board from "../components/Board/Board";
import PlayerConfigCard from "../components/Controls/PlayerConfigCard";
import GameSetupCard from "../components/Controls/GameSetupCard";
import EvaluationPanel from "../components/Controls/EvaluationPanel";
import GameOverDialog from "../components/Dialogs/GameOverDialog";
import { useEffect, useState } from "react";
import { useGameContext } from "../context/GameProvider";

const TabPanel = ({ value, index, children }) => {
  if (value !== index) return null;
  return <Box mt={2}>{children}</Box>;
};

const GamePage = () => {
  const [tab, setTab] = useState(0);
  const { store, api } = useGameContext();
  const gameMode = store(state => state.gameMode);
  const evaluationEnabled = gameMode === "aivai";
  const setSystemInfo = store(state => state.setSystemInfo);

  useEffect(() => {
    if (!evaluationEnabled && tab === 1) {
      setTab(0);
    }
  }, [evaluationEnabled, tab]);

  useEffect(() => {
    api.fetchSystemInfo().then(setSystemInfo).catch(() => {});
  }, [api, setSystemInfo]);
  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Header />
      <Grid container spacing={6} mt={1}>
        <Grid item xs={12} lg={6} sx={{ flexBasis: { lg: "46%" }, maxWidth: { lg: "46%" } }}>
          <Box sx={{ width: "115%", maxWidth: "115%", ml: "-15%", mt: 2 }}>
            <Board />
          </Box>
        </Grid>
        <Grid item xs={12} lg={6} sx={{ flexBasis: { lg: "54%" }, maxWidth: { lg: "54%" } }}>
          <Box display="flex" flexDirection="column" gap={3}>
            <Tabs value={tab} onChange={(_, value) => setTab(value)}>
              <Tab label="Play" />
              <Tab label="Evaluate" disabled={!evaluationEnabled} />
            </Tabs>
            <TabPanel value={tab} index={0}>
              <Box display="flex" flexDirection="column" gap={3}>
                <GameSetupCard />
                <Grid container spacing={3}>
                  <Grid item xs={12} md={6}>
                    <PlayerConfigCard color="white" />
                  </Grid>
                  <Grid item xs={12} md={6}>
                    <PlayerConfigCard color="black" />
                  </Grid>
                </Grid>
              </Box>
            </TabPanel>
            <TabPanel value={tab} index={1}>
              <EvaluationPanel />
            </TabPanel>
          </Box>
        </Grid>
      </Grid>
      <Footer />
      <GameOverDialog />
    </Container>
  );
};

export default GamePage;
