import os
import json
import math
import random
from typing import List, Dict, Any

class RLAgent:
    """Simple online REINFORCE-style linear policy over extracted features.
    - Uses a single shared weight vector for all actions.
    - Selects among candidate actions (each with its own feature dict).
    - Performs small online updates per timestep and persists weights.
    This is dependency-free and safe to run during matches.
    """

    def __init__(self, feature_keys: List[str], lr: float = 1e-4, baseline_beta: float = 0.01, save_path: str = "rl_weights.json", temp_seed: int = None):
        self.feature_keys = list(feature_keys)
        self.lr = float(lr)
        self.baseline_beta = float(baseline_beta)
        self.save_path = save_path
        self.baseline = 0.0
        self.rng = random.Random(temp_seed)

        # initialize weights from file or zeros (use small random init)
        self.weights: Dict[str, float] = {k: 0.0 for k in self.feature_keys}
        self._maybe_load()

    def _maybe_load(self):
        try:
            if os.path.exists(self.save_path):
                with open(self.save_path, "r") as fh:
                    data = json.load(fh)
                    for k, v in data.items():
                        if k in self.weights:
                            self.weights[k] = float(v)
        except Exception:
            pass

    def save(self):
        try:
            tmp = self.save_path + ".tmp"
            with open(tmp, "w") as fh:
                json.dump(self.weights, fh)
            os.replace(tmp, self.save_path)
        except Exception:
            pass

    def _dot(self, w: Dict[str, float], f: Dict[str, float]) -> float:
        s = 0.0
        for k, val in f.items():
            s += w.get(k, 0.0) * float(val)
        return s

    def _expected_feature(self, candidate_features: List[Dict[str, float]], probs: List[float]) -> Dict[str, float]:
        exp = {}
        for p, f in zip(probs, candidate_features):
            for k, v in f.items():
                exp[k] = exp.get(k, 0.0) + p * float(v)
        return exp

    def select_action(self, candidate_features: List[Dict[str, float]], deterministic: bool = False) -> int:
        scores = [self._dot(self.weights, f) for f in candidate_features]
        # numeric stability
        maxs = max(scores) if scores else 0.0
        exps = [math.exp(s - maxs) for s in scores]
        ssum = sum(exps) + 1e-12
        probs = [e / ssum for e in exps]
        if deterministic:
            return int(max(range(len(probs)), key=lambda i: probs[i]))
        r = self.rng.random()
        cum = 0.0
        for i, p in enumerate(probs):
            cum += p
            if r <= cum:
                return i
        return len(probs) - 1

    def update_step(self, candidate_features: List[Dict[str, float]], action_idx: int, reward: float):
        # single-step REINFORCE with baseline (low-variance online update)
        if not candidate_features or action_idx is None:
            return
        scores = [self._dot(self.weights, f) for f in candidate_features]
        maxs = max(scores)
        exps = [math.exp(s - maxs) for s in scores]
        ssum = sum(exps) + 1e-12
        probs = [e / ssum for e in exps]

        # expected feature under current policy
        exp_feat = self._expected_feature(candidate_features, probs)
        chosen_feat = candidate_features[action_idx]

        # advantage
        adv = reward - self.baseline

        # gradient: (f_a - E_pi[f])
        for k, v in chosen_feat.items():
            gw = (float(v) - exp_feat.get(k, 0.0)) * adv
            self.weights[k] = self.weights.get(k, 0.0) + self.lr * gw

        # Update baseline
        self.baseline = (1.0 - self.baseline_beta) * self.baseline + self.baseline_beta * reward

        # occasional persistence
        if abs(reward) > 0.0:
            self.save()

    def update_episode(self, transitions: List[Dict[str, Any]], gamma: float = 0.99):
        # transitions: list of {candidate_features, action_idx, reward}
        # compute reward-to-go and apply batch updates
        n = len(transitions)
        returns = [0.0] * n
        running = 0.0
        for i in range(n - 1, -1, -1):
            running = transitions[i]["reward"] + gamma * running
            returns[i] = running

        for tr, G in zip(transitions, returns):
            self.update_step(tr["candidate_features"], tr["action_idx"], G)
