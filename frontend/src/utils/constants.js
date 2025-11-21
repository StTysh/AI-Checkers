export const PLAYER_KINDS = [
  { value: "human", label: "Human" },
  { value: "minimax", label: "Minimax" },
  { value: "mcts", label: "Monte Carlo (coming soon)", disabled: true },
  { value: "genetic", label: "Genetic (coming soon)", disabled: true },
  { value: "reinforcement", label: "Reinforcement (coming soon)", disabled: true },
];

export const GAME_MODES = [
  { value: "pvp", label: "Player vs Player" },
  { value: "pvai", label: "Player vs AI" },
  { value: "aivai", label: "AI vs AI" },
];

export const VARIANTS = [
  { value: "british", label: "British (8×8)" },
  { value: "international", label: "International (10×10)" },
];

export const SIM_SPEEDS = [
  { label: "0.25×", value: 0.25 },
  { label: "0.5×", value: 0.5 },
  { label: "1×", value: 1 },
  { label: "2×", value: 2 },
  { label: "5×", value: 5 },
];

export const DEFAULT_PLAYER_CONFIG = {
  white: {
    type: "human",
    depth: 4,
    alphaBeta: true,
    moveOrdering: true,
    iterativeDeepening: false,
    transposition: false,
    quiescence: false,
  },
  black: {
    type: "human",
    depth: 4,
    alphaBeta: true,
    moveOrdering: true,
    iterativeDeepening: false,
    transposition: false,
    quiescence: false,
  },
};
