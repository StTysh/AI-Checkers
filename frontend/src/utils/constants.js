export const PLAYER_KINDS = [
  { value: "human", label: "Human" },
  { value: "minimax", label: "Minimax" },
  { value: "mcts", label: "Monte Carlo Tree Search" },
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

const BASE_PLAYER_CONFIG = {
  type: "human",
  depth: 4,
  alphaBeta: true,
  moveOrdering: true,
  iterativeDeepening: false,
  transposition: true,
  killerMoves: true,
  quiescence: true,
  maxQuiescenceDepth: 6,
  aspiration: false,
  aspirationWindow: 50,
  historyHeuristic: false,
  butterflyHeuristic: false,
  nullMove: false,
  nullMoveReduction: 2,
  lmr: false,
  lmrMinDepth: 3,
  lmrMinMoves: 4,
  lmrReduction: 1,
  deterministicOrdering: true,
  endgameTablebase: false,
  endgameMaxPieces: 6,
  endgameMaxPlies: 40,
  timeLimitMs: 1000,
  parallel: false,
  workers: 4,
  iterations: 500,
  rolloutDepth: 80,
  explorationConstant: 1.4,
  randomSeed: null,
  mctsParallel: false,
  mctsWorkers: 4,
  rolloutPolicy: "random",
  guidanceDepth: 2,
  rolloutCutoffDepth: 40,
  leafEvaluation: "random_terminal",
  mctsTransposition: false,
  mctsTranspositionMaxEntries: 200000,
  progressiveWidening: false,
  pwK: 1.5,
  pwAlpha: 0.5,
  progressiveBias: false,
  pbWeight: 0.4,
};

export const DEFAULT_PLAYER_CONFIG = {
  white: { ...BASE_PLAYER_CONFIG },
  black: { ...BASE_PLAYER_CONFIG },
};
