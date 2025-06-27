import numpy as np
import random
import pandas as pd
import pickle
import os

class GA:
    def __init__(
        self,
        population_size=8,
        n_weights=10,
        elite_size=1,
        mutation_rate=0.3,
        mutation_scale=0.35,
        eval_trials=1,
        blend_prob=0.5,
        creep_scale=0.02,
        uniform_chance=0.175,
        creep_chance=0.25,
        uniform_range=(1e-4, 19.9999),  # <-- New safe bounds!
        misc_dir="D:\\Tetris-Project\\miscellaneous",
        log_file="ga_log.csv",
        checkpoint_file="ga_checkpoint.pkl"
    ):
        self.population_size = population_size
        self.n_weights = n_weights
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.mutation_scale = mutation_scale
        self.eval_trials = eval_trials
        self.blend_prob = blend_prob
        self.creep_scale = creep_scale
        self.uniform_chance = uniform_chance
        self.creep_chance = creep_chance
        self.uniform_range = uniform_range

        self.misc_dir = os.path.abspath(misc_dir)
        os.makedirs(self.misc_dir, exist_ok=True)
        self.log_file = os.path.join(self.misc_dir, log_file)
        self.checkpoint_file = os.path.join(self.misc_dir, checkpoint_file)

        self.population = None

    def _random_weights(self):
        return list(np.random.uniform(*self.uniform_range, self.n_weights))

    def evaluate_agent_fitness(self, lines, score, time_sec):
        """Fitness = 0.7*lines + 0.03*score - 0.3*time_sec"""
        return 0.7 * lines + 0.03 * score - 0.3 * time_sec

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
            # After reflection, ensure strictly within (minval, maxval)
            if v <= minval:
                v = minval
            if v >= maxval:
                v = maxval
            new_w.append(v)
        return new_w

    def weighted_avg_crossover(self, w1, w2, f1, f2):
        child = np.array(w1) * f1 + np.array(w2) * f2
        return self.reflect_bounds(child.tolist(), *self.uniform_range)

    def blend_uniform_crossover(self, w1, w2):
        child = []
        for g1, g2 in zip(w1, w2):
            if random.random() < self.blend_prob:
                alpha = random.random()
                gene = alpha * g1 + (1 - alpha) * g2
            else:
                gene = random.choice([g1, g2])
            child.append(gene)
        return self.reflect_bounds(child, *self.uniform_range)

    def gene_mutate(self, w):
        new_w = []
        for v in w:
            if random.random() < self.mutation_rate:
                r = random.random()
                if r < self.uniform_chance:
                    new_w.append(np.random.uniform(*self.uniform_range))
                elif r < self.uniform_chance + self.creep_chance:
                    new_w.append(v + np.random.uniform(-self.creep_scale, self.creep_scale))
                else:
                    new_w.append(v + np.random.normal(0, self.mutation_scale))
            else:
                new_w.append(v)
        return self.reflect_bounds(new_w, *self.uniform_range)

    def nudge(self, w, amount=0.2):
        w = list(w)
        for i in range(len(w)):
            w[i] += np.random.uniform(-amount, amount)
        return self.reflect_bounds(w, *self.uniform_range)

    def mutate(self, w):
        mutated = self.gene_mutate(w)
        return self.nudge(mutated)

    def tournament_select(self, population, fitnesses, k=3):
        contenders_idx = random.sample(range(len(population)), k)
        best_idx = max(contenders_idx, key=lambda i: fitnesses[i])
        return best_idx

    def make_random_immigrant(self, elite_weights):
        w = np.array(elite_weights)
        n = len(w)
        new_w = w.copy()
        random_values = np.random.uniform(0.75, 2, n)
        operations = np.random.choice([1, -1], size=n)
        new_w += random_values * operations
        return self.reflect_bounds(new_w, *self.uniform_range)

    def select_and_breed(self, fitnesses, generation):
        sorted_idx = np.argsort(fitnesses)[::-1]
        elite = [self.population[idx] for idx in sorted_idx[:self.elite_size]]
        new_population = elite[:]

        min_fit = min(fitnesses)
        adj_fitnesses = fitnesses
        if min_fit < 0:
            adj_fitnesses = [f - min_fit for f in fitnesses]

        total_fit = sum(adj_fitnesses)
        if total_fit == 0:
            probs = [1.0 / len(adj_fitnesses)] * len(adj_fitnesses)
        else:
            probs = [f / total_fit for f in adj_fitnesses]

        remaining = self.population_size - self.elite_size
        half = remaining // 2
        extra = remaining % 2

        if extra == 0:
            roulette_count = tournament_count = half
        else:
            if random.random() < 0.5:
                roulette_count, tournament_count = half, half + 1
            else:
                roulette_count, tournament_count = half + 1, half

        print(f"[GA] Roulette selection happening for {roulette_count} offspring.")
        for _ in range(roulette_count):
            p1_idx = np.random.choice(len(self.population), p=probs)
            p2_idx = np.random.choice(len(self.population), p=probs)
            p1 = self.population[p1_idx]
            p2 = self.population[p2_idx]
            child = self.blend_uniform_crossover(p1, p2)
            new_population.append(child)

        print(f"[GA] Tournament selection happening for {tournament_count} offspring.")
        for _ in range(tournament_count):
            i1 = self.tournament_select(self.population, fitnesses, k=3)
            i2 = self.tournament_select(self.population, fitnesses, k=3)
            w1, w2 = self.population[i1], self.population[i2]
            f1, f2 = fitnesses[i1], fitnesses[i2]
            child = self.weighted_avg_crossover(w1, w2, f1, f2)
            new_population.append(child)

        # Mutate all non-elites
        for i in range(self.elite_size, len(new_population)):
            new_population[i] = self.mutate(new_population[i])

        # Replace only a non-elite (never the elite at index 0)
        replaceable_indices = list(range(self.elite_size, len(new_population)))
        replace_idx = random.choice(replaceable_indices)

        if generation % 2 == 0:
            immigrant = self.make_random_immigrant(elite[0])
            print(f"[GA] Injecting 1 random immigrant with weight {immigrant} at index {replace_idx}, replacing previous agent.")
            new_population[replace_idx] = immigrant
        else:
            nudged_elite = self.nudge(elite[0])
            print(f"[GA] Injecting 1 nudged elite with weight {nudged_elite} at index {replace_idx}, replacing previous agent.")
            new_population[replace_idx] = nudged_elite

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
