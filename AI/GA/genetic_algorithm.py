import numpy as np
import random
import pandas as pd
import pickle
import os
import math

class GA:
    def __init__(
        self,
        population_size=10,
        n_weights=10,
        elite_size=2,
        log_file="ga_log.csv",
        checkpoint_file="ga_checkpoint.pkl",
        misc_dir="D:\\Tetris-Project\\results\\ga"
    ):
        self.population_size = population_size
        self.n_weights = n_weights
        self.elite_size = elite_size

        self.misc_dir = os.path.abspath(misc_dir)
        os.makedirs(self.misc_dir, exist_ok=True)
        self.log_file = os.path.join(self.misc_dir, log_file)
        self.checkpoint_file = os.path.join(self.misc_dir, checkpoint_file)
        self.population = None
        self.uniform_range = (1e-4, 19.9999)

        # To store the adaptive hyperparameters per generation
        self.param_history = []

    # --- Adaptive parameter schedules ---
    def _ramp(self, start, stop, gen, ramp_gen=30):
        if gen >= ramp_gen:
            return stop
        return start - (start - stop) * (gen / ramp_gen)

    def current_params(self, generation):
        ramp_gens = 38  # takes 60 generations to ramp to the end values

        return {
            "mutation_rate": self._ramp(0.6, 0.185, generation, ramp_gen=ramp_gens),     # up from 0.475, 0.12
            "mutation_scale": self._ramp(0.45, 0.15, generation, ramp_gen=ramp_gens),    # up from 0.35, 0.09
            "creep_scale": self._ramp(0.08, 0.03, generation, ramp_gen=ramp_gens),     # up from 0.06, 0.02
            "blend_prob": self._ramp(0.85, 0.56, generation, ramp_gen=ramp_gens),        # up from 0.72, 0.48
            "uniform_chance": self._ramp(0.35, 0.15, generation, ramp_gen=ramp_gens),    # up from 0.22, 0.08
            "creep_chance": self._ramp(0.3, 0.15, generation, ramp_gen=ramp_gens),      # up from 0.25, 0.10
        }
   

    def _random_weights(self):
        return list(np.random.uniform(*self.uniform_range, self.n_weights))


    def evaluate_agent_fitness(self, lines, score, time_sec, num_tetris, max_time=360):
        # Reward for clearing lines
        line_score = 1 * lines
        # Extra reward for tetrises
        tetris_score = 4.5 * num_tetris
        # Score as a small reward (optional, tune as needed)
        score_bonus = 0.015 * score
        # Survival reward: encourages agents to survive longer
        survival_reward = 0.09 * time_sec  # Tweak multiplier to balance with your other terms

        # Early death penalty: Only punishes for dying before 90% of max_time
        min_survival = 0.9 * max_time
        if time_sec < min_survival:
            death_penalty = math.log((min_survival - time_sec) + 1) * 8
        else:
            death_penalty = 0

        # Final fitness calculation
        fitness = (
            line_score +
            tetris_score +
            score_bonus +
            survival_reward -
            death_penalty
        )
        return fitness


    def reflect_bounds(self, w, minval=1e-4, maxval=19.9999):
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
        # --- LOG the adaptive params for this generation
        self.param_history.append(params.copy())

        sorted_idx = np.argsort(fitnesses)[::-1]
        elite = [self.population[idx] for idx in sorted_idx[:self.elite_size]]
        new_population = elite[:]

        min_fit = min(fitnesses)
        adj_fitnesses = fitnesses
        if min_fit < 0:
            adj_fitnesses = [f - min_fit + 1e-6 for f in fitnesses]
        elif min_fit == 0 and all(f == 0 for f in fitnesses):
            adj_fitnesses = [f + 1e-6 for f in fitnesses]

        total_fit = sum(adj_fitnesses)
        if total_fit == 0:
            probs = [1.0 / len(adj_fitnesses)] * len(adj_fitnesses)
        else:
            probs = [f / total_fit for f in adj_fitnesses]

        remaining = self.population_size - self.elite_size
        roulette_count = remaining // 2
        tournament_count = remaining - roulette_count

        for _ in range(roulette_count):
            p1_idx = np.random.choice(len(self.population), p=probs)
            p2_idx = np.random.choice(len(self.population), p=probs)
            p1 = self.population[p1_idx]
            p2 = self.population[p2_idx]
            child = self.blend_uniform_crossover(p1, p2, params["blend_prob"])
            new_population.append(child)

        for _ in range(tournament_count):
            i1 = self.tournament_select(self.population, fitnesses, k=3)
            i2 = self.tournament_select(self.population, fitnesses, k=3)
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
            "param_history": self.param_history,  # --- Save param history!
        }
        with open(self.checkpoint_file, "wb") as f:
            pickle.dump(checkpoint, f)
        print(f"Checkpoint saved at generation {generation} to {self.checkpoint_file}")

    def load_checkpoint(self):
        with open(self.checkpoint_file, "rb") as f:
            checkpoint = pickle.load(f)
        self.population = checkpoint["population"]
        self.param_history = checkpoint.get("param_history", [])
        generation = checkpoint["generation"]
        history = checkpoint["history"]
        print("=" * 48)
        print(f"Loaded checkpoint at generation: {generation}")
        # Print parameters for this generation (if available)
        if self.param_history and len(self.param_history) > generation:
            params = self.param_history[generation]
            print(f"Adaptive parameters at gen {generation}:")
            for k, v in params.items():
                print(f"  {k}: {v:.4f}")
        else:
            print("No adaptive parameter history found for this generation.")
        # Print weights for each agent in population
        print(f"Population weights at gen {generation}:")
        for idx, w in enumerate(self.population):
            print(f"  Agent {idx}: {np.array2string(np.array(w), precision=4, separator=', ')}")
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
