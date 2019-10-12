"""Trainer and configuration for SVG(1)."""
from ray.rllib.agents.trainer import with_base_config
from ray.rllib.utils.annotations import override
from ray.rllib.evaluation.metrics import get_learner_stats

from raylab.algorithms.svg import SVG_BASE_CONFIG, SVGBaseTrainer
from raylab.algorithms.svg.svg_one_policy import SVGOneTorchPolicy


DEFAULT_CONFIG = with_base_config(
    SVG_BASE_CONFIG,
    {
        # === Optimization ===
        # PyTorch optimizer to use
        "torch_optimizer": "Adam",
        # Optimizer options for each component.
        # Valid keys include: 'model', 'value', and 'policy'
        "torch_optimizer_options": {
            "model": {"lr": 1e-3},
            "value": {"lr": 1e-3},
            "policy": {"lr": 1e-3},
        },
        # === Exploration ===
        # Whether to sample only the mean action, mostly for evaluation purposes
        "mean_action_only": False,
        # Until this many timesteps have elapsed, the agent's policy will be
        # ignored & it will instead take uniform random actions. Can be used in
        # conjunction with learning_starts (which controls when the first
        # optimization step happens) to decrease dependence of exploration &
        # optimization on initial policy parameters. Note that this will be
        # disabled when the action noise scale is set to 0 (e.g during evaluation).
        "pure_exploration_steps": 1000,
        # === Evaluation ===
        # Extra arguments to pass to evaluation workers.
        # Typical usage is to pass extra args to evaluation env creator
        # and to disable exploration by computing deterministic actions
        "evaluation_config": {"mean_action_only": True, "pure_exploration_steps": 0},
    },
)


class SVGOneTrainer(SVGBaseTrainer):
    """Single agent trainer for SVG(1)."""

    # pylint: disable=attribute-defined-outside-init

    _name = "SVG(1)"
    _default_config = DEFAULT_CONFIG
    _policy = SVGOneTorchPolicy

    @override(SVGBaseTrainer)
    def _train(self):
        worker = self.workers.local_worker()
        policy = worker.get_policy()

        while not self._iteration_done():
            samples = worker.sample()
            self.optimizer.num_steps_sampled += samples.count
            for row in samples.rows():
                self.replay.add(row)

            policy.update_old_policy()
            for _ in range(samples.count):
                batch = self.replay.sample(self.config["train_batch_size"])
                learner_stats = get_learner_stats(policy.learn_on_batch(batch))
                self.optimizer.num_steps_trained += batch.count
            learner_stats.update(policy.update_kl_coeff(samples))

        return self._log_metrics(learner_stats)
