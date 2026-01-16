import { Box, Container, Grid } from "@mui/material";
import Header from "../components/UI/Header";
import Footer from "../components/UI/Footer";
import Board from "../components/Board/Board";
import PlayerConfigCard from "../components/Controls/PlayerConfigCard";
import GameSetupCard from "../components/Controls/GameSetupCard";
import GameOverDialog from "../components/Dialogs/GameOverDialog";
import ThemeSwitcher from "../components/UI/ThemeSwitcher";

const GamePage = () => {
  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Header />
      <Grid container spacing={3} mt={1}>
        <Grid item xs={12} lg={7}>
          <Board />
        </Grid>
        <Grid item xs={12} lg={5}>
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
            <ThemeSwitcher />
          </Box>
        </Grid>
      </Grid>
      <Footer />
      <GameOverDialog />
    </Container>
  );
};

export default GamePage;
