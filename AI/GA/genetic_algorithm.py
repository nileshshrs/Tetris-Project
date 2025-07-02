import numpy as np
import random
import pandas as pd
import pickle
import os

class GA:
    def __init__(
        self,
        population_size=10,
        n_weights=10,
        elite_size=2,
        log_file="ga_log.csv",
        checkpoint_file="ga_checkpoint.pkl",
        misc_dir="D:\\Tetris-Project\\miscellaneous"
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

    # --- Adaptive parameter schedules ---
    def _ramp(self, start, stop, gen, ramp_gen=30):
        if gen >= ramp_gen:
            return stop
        return start - (start - stop) * (gen / ramp_gen)

    def current_params(self, generation):
        ramp_gens = 38  # takes 60 generations to ramp to the end values

        return {
            # mutation_rate: Probability that *each gene* will be mutated
            "mutation_rate": self._ramp(0.65, 0.28, generation, ramp_gen=ramp_gens),   # high mutation for longer

            # mutation_scale: Stddev of the gaussian noise for normal mutations
            "mutation_scale": self._ramp(0.55, 0.21, generation, ramp_gen=ramp_gens),

            # creep_scale: Small-range "creep" mutation (add/subtract a small value)
            "creep_scale": self._ramp(0.10, 0.04, generation, ramp_gen=ramp_gens),

            # blend_prob: Probability to use blend crossover instead of direct gene pick
            "blend_prob": self._ramp(0.82, 0.51, generation, ramp_gen=ramp_gens),

            # uniform_chance: Probability to do a full random gene reset (per gene)
            "uniform_chance": self._ramp(0.34, 0.13, generation, ramp_gen=ramp_gens),

            # creep_chance: Probability to do a "creep" small mutation (per gene)
            "creep_chance": self._ramp(0.37, 0.20, generation, ramp_gen=ramp_gens),
        }


    def _random_weights(self):
        return list(np.random.uniform(*self.uniform_range, self.n_weights))

    def evaluate_agent_fitness(self, lines, score, time_sec):
        return 0.4 * lines + 0.03 * score - 0.5 * time_sec

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

    def nudge(self, elite, params):
        w = list(elite)
        nudge_amt = params["creep_scale"]
        for i in range(len(w)):
            w[i] += np.random.uniform(-nudge_amt, nudge_amt)
        return self.reflect_bounds(w, *self.uniform_range)

    # --- Use the original random immigrant logic ---
    def make_random_immigrant(self, elite_weights):
        w = np.array(elite_weights)
        n = len(w)
        random_values = np.random.uniform(0.75, 2, n)
        operations = np.random.choice([1, -1], size=n)
        new_w = w + random_values * operations
        return self.reflect_bounds(new_w, *self.uniform_range)

    def select_and_breed(self, fitnesses, generation):
        params = self.current_params(generation)
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
            i1 = self.tournament_select(self.population, fitnesses, k=4)
            i2 = self.tournament_select(self.population, fitnesses, k=4)
            w1, w2 = self.population[i1], self.population[i2]
            child = self.weighted_avg_crossover(w1, w2, adj_fitnesses[i1], adj_fitnesses[i2])
            new_population.append(child)

        for i in range(self.elite_size, len(new_population)):
            new_population[i] = self.mutate(new_population[i], params)

        # # --- Random immigrant and nudge every 2 generations, replace worst 2 non-elites ---
        # if generation > 0 and generation % 5 == 0:
        #     nonelite_idxs = list(range(self.elite_size, len(new_population)))
        #     if len(nonelite_idxs) >= 2:
        #         nonelite_fitnesses = [fitnesses[sorted_idx[self.elite_size + i]] for i in range(len(nonelite_idxs))]
        #         worst_two_idx = np.argsort(nonelite_fitnesses)[:2]
        #         replace_indices = [nonelite_idxs[i] for i in worst_two_idx]

        #         immigrant_elite = random.choice(elite)
        #         immigrant = self.make_random_immigrant(immigrant_elite)
        #         new_population[replace_indices[0]] = immigrant

        #         nudge_elite = random.choice(elite)
        #         nudged = self.nudge(nudge_elite, params)
        #         new_population[replace_indices[1]] = nudged

        #         print(f"[GA] Injected immigrant at idx {replace_indices[0]}, nudged elite at idx {replace_indices[1]} (gen {generation})")

        self.population = new_population

    def save_checkpoint(self, generation, history):
        checkpoint = {
            "population": self.population,
            "generation": generation,
            "history": history,
        }
        with open(self.checkpoint_file, "wb") as f:
            pickle.dump(checkpoint, f)
        print(f"Checkpoint saved at generation {generation} to {self.checkpoint_file}")

    def load_checkpoint(self):
        with open(self.checkpoint_file, "rb") as f:
            checkpoint = pickle.load(f)
        self.population = checkpoint["population"]
        return checkpoint["generation"], checkpoint["history"]

    def save_log(self, history):
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
        df = df[cols]
        df.to_csv(self.log_file, index=False)
        print(f"Log saved to {self.log_file}")
