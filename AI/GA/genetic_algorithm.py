import numpy as np
import random
import pandas as pd
import pickle
import os

class GA:
    def __init__(
        self,
        population_size=50,
        n_weights=10,
        elite_size=4,
        log_file="ga_log.csv",
        checkpoint_file="ga_checkpoint.pkl",
        misc_dir=None
    ):
        self.population_size = population_size
        self.n_weights = n_weights
        self.elite_size = elite_size

        self.misc_dir = os.path.abspath(misc_dir) if misc_dir else os.path.join(os.path.dirname(__file__), '..', '..', 'results', 'ga')
        os.makedirs(self.misc_dir, exist_ok=True)
        self.log_file = os.path.join(self.misc_dir, log_file)
        self.checkpoint_file = os.path.join(self.misc_dir, checkpoint_file)
        self.population = None
        self.uniform_range = (1e-4, 30.0)  # Wider range for clear bonus exploration

        # To store the adaptive hyperparameters per generation
        self.param_history = []

        # Stagnation detection
        self.best_fitness_history = []
        self.stagnation_counter = 0
        self.stagnation_threshold = 8       # Gens without improvement triggers surge
        self.stagnation_surge_active = False
        self.best_ever_fitness = float('-inf')

    # --- Adaptive parameter schedules ---
    def _ramp(self, start, stop, gen, ramp_gen=30):
        if gen >= ramp_gen:
            return stop
        return start - (start - stop) * (gen / ramp_gen)

    def current_params(self, generation):
        ramp_gens = 38  # Takes 38 generations to ramp to end values

        params = {
            "mutation_rate": self._ramp(0.6, 0.185, generation, ramp_gen=ramp_gens),
            "mutation_scale": self._ramp(0.45, 0.15, generation, ramp_gen=ramp_gens),
            "creep_scale": self._ramp(0.08, 0.03, generation, ramp_gen=ramp_gens),
            "blend_prob": self._ramp(0.85, 0.56, generation, ramp_gen=ramp_gens),
            "uniform_chance": self._ramp(0.35, 0.15, generation, ramp_gen=ramp_gens),
            "creep_chance": self._ramp(0.3, 0.15, generation, ramp_gen=ramp_gens),
        }

        # Mutation surge during stagnation — 3x rate, 2x scale, 2.5x uniform chance
        if self.stagnation_surge_active:
            params["mutation_rate"] = min(params["mutation_rate"] * 3.0, 0.95)
            params["mutation_scale"] = params["mutation_scale"] * 2.0
            params["uniform_chance"] = min(params["uniform_chance"] * 2.5, 0.5)

        return params

    # --- Stagnation Detection ---
    def check_stagnation(self, current_best_fitness):
        """
        Track best fitness and detect stagnation.
        Returns True if mutation surge is active.
        """
        # Minimum improvement to count as progress: 1% of best-so-far (fitness is
        # score-based, so an absolute threshold would be meaningless).
        if self.best_ever_fitness == float('-inf'):
            improvement_threshold = 0.5
        else:
            improvement_threshold = max(0.5, 0.01 * abs(self.best_ever_fitness))

        self.best_fitness_history.append(current_best_fitness)

        if current_best_fitness > self.best_ever_fitness + improvement_threshold:
            self.best_ever_fitness = current_best_fitness
            self.stagnation_counter = 0
            self.stagnation_surge_active = False
        else:
            self.stagnation_counter += 1

        if self.stagnation_counter >= self.stagnation_threshold:
            if not self.stagnation_surge_active:
                print(f"[GA] STAGNATION DETECTED — {self.stagnation_counter} gens without improvement")
                print(f"[GA] Activating mutation surge (3x mutation rate, 2x scale)")
            self.stagnation_surge_active = True
            return True

        return self.stagnation_surge_active

    # --- Population Diversity ---
    def population_diversity(self):
        """Measure population diversity as mean per-gene standard deviation."""
        if not self.population or len(self.population) < 2:
            return 0.0
        pop_array = np.array(self.population)
        return float(np.mean(np.std(pop_array, axis=0)))

    def _random_weights(self):
        return list(np.random.uniform(*self.uniform_range, self.n_weights))

    def initialize_population(self, seed_weights=None):
        """
        Initialize population with optional seed weights from prior runs.

        Args:
            seed_weights: Optional list of weight vectors to include in gen 0.
                        Remaining slots are filled with random weights.
        """
        self.population = []

        if seed_weights:
            for sw in seed_weights[:self.population_size]:
                self.population.append(list(sw))
            print(f"[GA] Seeded {len(seed_weights)} agents from prior knowledge")

        while len(self.population) < self.population_size:
            self.population.append(self._random_weights())

        seeded = len(seed_weights) if seed_weights else 0
        print(f"[GA] Population initialized: {len(self.population)} agents "
            f"({seeded} seeded, {self.population_size - seeded} random)")

    # ------------------------------------------------------------------
    # Fitness (v3)
    # ------------------------------------------------------------------
    # Agents play several seeded games in the headless simulator, each capped
    # at a fixed number of pieces. In that setting almost every reasonable
    # weight vector survives the cap and clears ~0.4 lines/piece (the maximum),
    # so lines cannot rank agents. The game's own score can: it pays far more
    # for multi-line clears (1/2/3/4 lines = 40/100/300/1200), and dying early
    # simply stops the score from growing. No hand-made bonuses or penalties.
    PIECE_TIEBREAK = 1.0    # tiny per-piece credit so agents that score 0 still rank by survival

    @staticmethod
    def game_fitness(score, pieces):
        """Fitness of a single game."""
        return score + GA.PIECE_TIEBREAK * pieces

    def evaluate_agent_fitness(self, scores, pieces):
        """
        Fitness of one agent = mean game fitness over its games.

        Args:
            scores: list of final game scores (one per game)
            pieces: list of pieces placed (one per game)
        """
        values = [self.game_fitness(s, p) for s, p in zip(scores, pieces)]
        return float(np.mean(values))

    def reflect_bounds(self, w, minval=1e-4, maxval=30.0):
        new_w = []
        for v in w:
            if v < minval:
                v = minval + (minval - v)
                if v > maxval:
                    v = maxval
            elif v > maxval:
                v = maxval - (v - maxval)
                if v < minval:
                    v = minval
            v = max(minval, min(v, maxval))
            new_w.append(v)
        return new_w

    def weighted_avg_crossover(self, w1, w2, f1, f2):
        min_f = min(f1, f2)
        adj_f1, adj_f2 = f1, f2
        if min_f < 0:
            adj_f1, adj_f2 = f1 - min_f + 1e-6, f2 - min_f + 1e-6
        elif min_f == 0:
            if f1 == 0 and f2 == 0:
                adj_f1, adj_f2 = 1e-6, 1e-6
        total_adj = adj_f1 + adj_f2
        if total_adj <= 1e-9:
            child = (np.array(w1) + np.array(w2)) / 2
        else:
            child = (np.array(w1) * adj_f1 + np.array(w2) * adj_f2) / total_adj
        return self.reflect_bounds(child.tolist(), *self.uniform_range)

    def blend_uniform_crossover(self, w1, w2, blend_prob):
        child = []
        for g1, g2 in zip(w1, w2):
            if random.random() < blend_prob:
                alpha = random.random()
                gene = alpha * g1 + (1 - alpha) * g2
            else:
                gene = random.choice([g1, g2])
            child.append(gene)
        return self.reflect_bounds(child, *self.uniform_range)

    def gene_mutate(self, w, params):
        new_w = []
        for v in w:
            if random.random() < params["mutation_rate"]:
                r = random.random()
                if r < params["uniform_chance"]:
                    new_w.append(np.random.uniform(*self.uniform_range))
                elif r < params["uniform_chance"] + params["creep_chance"]:
                    new_w.append(v + np.random.uniform(-params["creep_scale"], params["creep_scale"]))
                else:
                    new_w.append(v + np.random.normal(0, params["mutation_scale"]))
            else:
                new_w.append(v)
        return self.reflect_bounds(new_w, *self.uniform_range)

    def mutate(self, w, params):
        return self.gene_mutate(w, params)

    def tournament_select(self, population, fitnesses, k=3):
        contenders_idx = random.sample(range(len(population)), k)
        best_idx = max(contenders_idx, key=lambda i: fitnesses[i])
        return best_idx

    def select_and_breed(self, fitnesses, generation):
        params = self.current_params(generation)
        # LOG the adaptive params for this generation
        self.param_history.append(params.copy())

        sorted_idx = np.argsort(fitnesses)[::-1]
        elite = [self.population[idx] for idx in sorted_idx[:self.elite_size]]
        new_population = elite[:]

        # --- Diversity injection ---
        diversity = self.population_diversity()
        inject_count = 0
        if diversity < 0.5:
            inject_count = max(2, self.population_size // 10)
            print(f"[GA] Low diversity ({diversity:.3f}) — injecting {inject_count} random agents")
            for _ in range(inject_count):
                new_population.append(self._random_weights())

        # Adjust fitness for selection: shift so the worst agent sits just above
        # zero. Fitness is a large score (thousands), and raw proportional
        # selection on values that close together would be almost uniform.
        min_fit = min(fitnesses)
        spread = max(fitnesses) - min_fit
        eps = 0.05 * spread + 1e-6
        adj_fitnesses = [f - min_fit + eps for f in fitnesses]

        total_fit = sum(adj_fitnesses)
        if total_fit == 0:
            probs = [1.0 / len(adj_fitnesses)] * len(adj_fitnesses)
        else:
            probs = [f / total_fit for f in adj_fitnesses]

        # Remaining slots after elite + injected agents
        remaining = self.population_size - len(new_population)
        if remaining <= 0:
            self.population = new_population[:self.population_size]
            return
        roulette_count = remaining // 2
        tournament_count = remaining - roulette_count

        # Roulette crossover — prevent self-crossover
        for _ in range(roulette_count):
            p1_idx = np.random.choice(len(self.population), p=probs)
            p2_idx = p1_idx
            for _attempt in range(10):
                p2_idx = np.random.choice(len(self.population), p=probs)
                if p2_idx != p1_idx:
                    break
            p1 = self.population[p1_idx]
            p2 = self.population[p2_idx]
            child = self.blend_uniform_crossover(p1, p2, params["blend_prob"])
            new_population.append(child)

        # Tournament crossover — prevent self-crossover
        for _ in range(tournament_count):
            i1 = self.tournament_select(self.population, fitnesses, k=3)
            i2 = i1
            for _attempt in range(10):
                i2 = self.tournament_select(self.population, fitnesses, k=3)
                if i2 != i1:
                    break
            w1, w2 = self.population[i1], self.population[i2]
            child = self.weighted_avg_crossover(w1, w2, adj_fitnesses[i1], adj_fitnesses[i2])
            new_population.append(child)

        for i in range(self.elite_size, len(new_population)):
            new_population[i] = self.mutate(new_population[i], params)

        self.population = new_population

    def save_checkpoint(self, generation, history):
        checkpoint = {
            "population": self.population,
            "generation": generation,
            "history": history,
            "param_history": self.param_history,
            "best_ever_fitness": getattr(self, 'best_ever_fitness', float('-inf')),
            "stagnation_counter": getattr(self, 'stagnation_counter', 0),
            "best_fitness_history": getattr(self, 'best_fitness_history', []),
        }
        with open(self.checkpoint_file, "wb") as f:
            pickle.dump(checkpoint, f)
        print(f"Checkpoint saved at generation {generation} to {self.checkpoint_file}")

    def load_checkpoint(self):
        with open(self.checkpoint_file, "rb") as f:
            checkpoint = pickle.load(f)
        self.population = checkpoint["population"]
        self.param_history = checkpoint.get("param_history", [])
        self.best_ever_fitness = checkpoint.get("best_ever_fitness", float('-inf'))
        self.stagnation_counter = checkpoint.get("stagnation_counter", 0)
        self.best_fitness_history = checkpoint.get("best_fitness_history", [])

        # Population size migration — pad or truncate
        while len(self.population) < self.population_size:
            self.population.append(self._random_weights())
        self.population = self.population[:self.population_size]

        generation = checkpoint["generation"]
        history = checkpoint["history"]
        print("=" * 48)
        print(f"Loaded checkpoint at generation: {generation}")
        print(f"  Best ever fitness: {self.best_ever_fitness:.2f}")
        print(f"  Stagnation counter: {self.stagnation_counter}/{self.stagnation_threshold}")
        print(f"  Population size: {len(self.population)}")
        # Print parameters for this generation (if available)
        if self.param_history and len(self.param_history) > generation:
            params = self.param_history[generation]
            print(f"  Adaptive parameters at gen {generation}:")
            for k, v in params.items():
                print(f"    {k}: {v:.4f}")
        else:
            print("  No adaptive parameter history found for this generation.")
        # Print weights for each agent in population
        print(f"  Population weights at gen {generation}:")
        for idx, w in enumerate(self.population):
            print(f"    Agent {idx}: {np.array2string(np.array(w), precision=4, separator=', ')}")
        print("=" * 48)
        return generation, history

    def save_log(self, history):
        # Optionally include param history as columns in CSV
        cols = [
            "Generation",
            "BestAgentID",
            "BestFitness",
            "AvgFitness",
            "WorstFitness",
            "FitnessStd",
            "W1:AggHeight",
            "W2:Holes",
            "W3:Blockades",
            "W4:Bumpiness",
            "W5:AlmostFull",
            "W6:FillsWell",
            "W7:ClearBonus4",
            "W8:ClearBonus3",
            "W9:ClearBonus2",
            "W10:ClearBonus1"
        ]
        df = pd.DataFrame(history)
        # Attach hyperparameters to log file if needed
        if len(self.param_history) == len(df):
            for k in self.param_history[0].keys():
                df[k] = [ph[k] for ph in self.param_history]
        df = df[cols + list(self.param_history[0].keys())] if len(self.param_history) == len(df) else df[cols]
        df.to_csv(self.log_file, index=False)
        print(f"Log saved to {self.log_file}")
