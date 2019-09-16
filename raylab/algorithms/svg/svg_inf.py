"""Learning Continuous Control Policies by Stochastic Value Gradients.

http://papers.nips.cc/paper/5796-learning-continuous-control-policies-by-stochastic-value-gradients
"""
from ray.rllib.agents.trainer import Trainer, with_common_config
from ray.rllib.utils.annotations import override
from ray.rllib.optimizers import PolicyOptimizer
from ray.rllib.evaluation.metrics import get_learner_stats

from raylab.algorithms.svg.svg_inf_policy import SVGInfTorchPolicy
from raylab.utils.replay_buffer import ReplayBuffer


DEFAULT_CONFIG = with_common_config(
    {
        # === Replay buffer ===
        # Size of the replay buffer. Note that if async_updates is set, then
        # each worker will have a replay buffer of this size.
        "buffer_size": 500000,
        # === Optimization ===
        # Name of Pytorch optimizer class for dynamics model and value function
        "off_policy_optimizer": "Adam",
        # Keyword arguments to be passed to the off-policy optimizer
        "off_policy_optimizer_options": {"lr": 1e-3},
        # Name of Pytorch optimizer class for paremetrized policy
        "on_policy_optimizer": "Adam",
        # Keyword arguments to be passed to the on-policy optimizer
        "on_policy_optimizer_options": {"lr": 1e-3},
        # Interpolation factor in polyak averaging for target networks.
        "polyak": 0.995,
    }
)


class SVGInfTrainer(Trainer):
    """Single agent trainer for SVG(inf)."""

    # pylint: disable=attribute-defined-outside-init

    _name = "SVG(inf)"
    _default_config = DEFAULT_CONFIG
    _policy = SVGInfTorchPolicy

    @override(Trainer)
    def _init(self, config, env_creator):
        self._validate_config(config)
        self.workers = self._make_workers(
            env_creator, self._policy, config, num_workers=0
        )
        # Dummy optimizer to log stats
        self.optimizer = PolicyOptimizer(self.workers)
        self.replay = ReplayBuffer(
            config["buffer_size"], extra_keys=[self._policy.ACTION_LOGP]
        )

    @override(Trainer)
    def _train(self):
        worker = self.workers.local_worker()
        policy = worker.get_policy()

        samples = worker.sample()
        self.optimizer.num_steps_sampled += samples.count
        for row in samples.row():
            self.replay.add(row)

        policy.off_policy_learning(True)
        for _ in range(samples.count):
            batch = self.replay.sample(self.config["train_batch_size"])
            off_policy_stats = get_learner_stats(policy.learn_on_batch(batch))
            self.optimizer.num_steps_trained += batch.count

        policy.off_policy_learning(False)
        on_policy_stats = get_learner_stats(policy.learn_on_batch(samples))

        learner_stats = {**off_policy_stats, **on_policy_stats}
        res = self.collect_metrics()
        res.update(
            timesteps_this_iter=samples.count,
            info=dict(learner=learner_stats, **res.get("info", {})),
        )
        return res

    # === New Methods ===

    @staticmethod
    def _validate_config(config):
        assert config["num_workers"] == 0, "No point in using additional workers."
