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
  return (
    <Box mt={2} sx={{ minWidth: 0, overflowX: "hidden" }}>
      {children}
    </Box>
  );
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
    <Container maxWidth="xl" sx={{ py: { xs: 2, md: 4 } }}>
      <Header />
      <Grid
        container
        columnSpacing={{ xs: 3, md: 6 }}
        rowSpacing={{ xs: 3, md: 6 }}
        mt={{ xs: 0, md: 1 }}
        alignItems="flex-start"
      >
        <Grid item xs={12} lg={5} sx={{ minWidth: 0 }}>
          <Box
            sx={{
              mt: { xs: 0, lg: 2 },
              mx: "auto",
              width: "100%",
              maxWidth: {
                xs: "min(100%, 560px)",
                sm: "min(100%, 620px)",
                md: "min(100%, 680px)",
                lg: "min(100%, calc(100vh - 240px))",
              },
            }}
          >
            <Board />
          </Box>
        </Grid>
        <Grid
          item
          xs={12}
          lg={7}
          sx={{
            minWidth: 0,
            overflowX: "hidden",
          }}
        >
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
