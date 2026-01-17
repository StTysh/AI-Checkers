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

export const DEFAULT_PLAYER_CONFIG = {
  white: {
    type: "human",
    depth: 4,
    alphaBeta: true,
    moveOrdering: true,
    iterativeDeepening: false,
    transposition: true,
    killerMoves: true,
    quiescence: true,
    maxQuiescenceDepth: 6,
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
  },
  black: {
    type: "human",
    depth: 4,
    alphaBeta: true,
    moveOrdering: true,
    iterativeDeepening: false,
    transposition: true,
    killerMoves: true,
    quiescence: true,
    maxQuiescenceDepth: 6,
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
  },
};
