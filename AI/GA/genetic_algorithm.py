import numpy as np
import random
import pandas as pd
import pickle
import os

class GA:
    def __init__(
        self,
        evaluate_agent_fn=None,
        population_size=8,
        n_weights=10,
        elite_size=2,
        mutation_rate=0.15,
        mutation_scale=0.2,
        blend_prob=0.5,
        eval_trials=1,
        creep_scale=0.02,
        uniform_chance=0.03,
        creep_chance=0.10,
        uniform_range=(-5,20),
        misc_dir="D:\Tetris-Project\miscellaneous",
        log_file="ga_log.csv",
        checkpoint_file="ga_checkpoint.pkl"
    ):
        self.evaluate_agent_fn = evaluate_agent_fn
        self.population_size = population_size
        self.n_weights = n_weights
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.mutation_scale = mutation_scale
        self.blend_prob = blend_prob
        self.eval_trials = eval_trials
        self.creep_scale = creep_scale
        self.uniform_chance = uniform_chance
        self.creep_chance = creep_chance
        self.uniform_range = uniform_range

        # File paths (create directory if missing)
        self.misc_dir = os.path.abspath(misc_dir)
        os.makedirs(self.misc_dir, exist_ok=True)
        self.log_file = os.path.join(self.misc_dir, log_file)
        self.checkpoint_file = os.path.join(self.misc_dir, checkpoint_file)

        self.population = None

    def _random_weights(self):
        # Use the uniform_range parameter
        return np.random.uniform(*self.uniform_range, self.n_weights).tolist()

    def evaluate_population(self):
        fitnesses = []
        for w in self.population:
            scores = [self.evaluate_agent_fn(w) for _ in range(self.eval_trials)]
            fitnesses.append(np.mean(scores))
        return fitnesses

    def select_and_breed(self, fitnesses):
        sorted_idx = np.argsort(fitnesses)[::-1]
        elite = [self.population[idx] for idx in sorted_idx[:self.elite_size]]
        new_population = elite[:]
        total_fit = sum(fitnesses)
        if total_fit == 0:
            probs = [1.0 / len(fitnesses)] * len(fitnesses)
        else:
            probs = [f / total_fit for f in fitnesses]
        while len(new_population) < self.population_size:
            parent1 = self.population[np.random.choice(range(self.population_size), p=probs)]
            parent2 = self.population[np.random.choice(range(self.population_size), p=probs)]
            child = self.blend_uniform_crossover(parent1, parent2)
            child = self.mutate(child)
            new_population.append(child)
        self.population = new_population

    def blend_uniform_crossover(self, w1, w2):
        child = []
        for g1, g2 in zip(w1, w2):
            if random.random() < self.blend_prob:
                alpha = random.random()
                gene = alpha * g1 + (1 - alpha) * g2
            else:
                gene = random.choice([g1, g2])
            child.append(gene)
        return child

    def mutate(self, w):
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
        return new_w

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

    def run(self, generations=30, verbose=True):
        history = []
        best_weights = None

        if os.path.exists(self.checkpoint_file):
            print(f"Checkpoint found! Loading from {self.checkpoint_file}")
            last_gen, history = self.load_checkpoint()
            start_gen = last_gen + 1
            print(f"Resuming from generation {start_gen}")
        else:
            self.population = [self._random_weights() for _ in range(self.population_size)]
            start_gen = 0
            history = []

        for gen in range(start_gen, generations):
            fitnesses = self.evaluate_population()
            avg_fit = np.mean(fitnesses)
            best_fit = np.max(fitnesses)
            best_idx = np.argmax(fitnesses)
            worst_fit = np.min(fitnesses)
            var_fit = np.var(fitnesses)
            best_weights = self.population[best_idx]

            history.append({
                "Generation": gen,
                "BestFitness": best_fit,
                "AvgFitness": avg_fit,
                "WorstFitness": worst_fit,
                "FitnessVariance": var_fit,
                "BestWeights": best_weights
            })

            if verbose:
                print(
                    f"Gen {gen+1}: "
                    f"Avg fitness {avg_fit:.2f}, "
                    f"Best fitness {best_fit:.2f}, "
                    f"Worst fitness {worst_fit:.2f}, "
                    f"Variance {var_fit:.2f}"
                )

            self.save_checkpoint(gen, history)
            self.select_and_breed(fitnesses)

        # Write log to CSV
        cols = [
            "Generation",
            "BestFitness",
            "AvgFitness",
            "WorstFitness",
            "FitnessVariance",
            "BestWeights"
        ]
        df = pd.DataFrame(history)
        df.to_csv(self.log_file, index=False, columns=cols)
        print(f"Log saved to {self.log_file}")
        print(f"Checkpoints saved to {self.checkpoint_file}")

        return best_weights, [h["BestFitness"] for h in history]
