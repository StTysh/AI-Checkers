import { Box, Typography } from "@mui/material";
import dayjs from "dayjs";

const Footer = () => (
  <Box mt={4} textAlign="center" color="text.secondary" fontSize={14}>
    <Typography component="span">© {dayjs().format("YYYY")} Checkers AI Playground · Experiment responsibly.</Typography>
  </Box>
);

export default Footer;
