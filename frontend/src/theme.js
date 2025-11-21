import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: { main: "#f9a826" },
    secondary: { main: "#00bcd4" },
    background: {
      default: "#141824",
      paper: "#1c2133",
    },
  },
  shape: { borderRadius: 14 },
  typography: {
    fontFamily: '"Inter", "Roboto", "Segoe UI", sans-serif',
    h6: { fontWeight: 600 },
  },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: "linear-gradient(135deg, rgba(255,255,255,0.04), rgba(0,0,0,0.25))",
          border: "1px solid rgba(255,255,255,0.08)",
        },
      },
    },
  },
});
