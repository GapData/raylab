"""Trainer and configuration for ACKTR."""
from raylab.algorithms import with_common_config
from raylab.algorithms.trpo.trpo import TRPOTrainer
from .acktr_policy import ACKTRTorchPolicy

DEFAULT_CONFIG = with_common_config(
    {
        # Number of actions to sample per state for Fisher matrix approximation
        "logp_samples": 10,
        # For GAE(\gamma, \lambda)
        "lambda": 0.97,
        # Whether to use Generalized Advantage Estimation
        "use_gae": True,
        # Value function loss weight
        "vf_loss_coeff": 1.0,
        # Arguments for KFACOptimizer
        "kfac": {
            "eps": 1e-3,
            "sua": False,
            "pi": True,
            "update_freq": 1,
            "alpha": 0.95,
            "kl_clip": 1e-2,
            "eta": 1.0,
            "lr": 1.0,
        },
        # Whether to use a line search to calculate policy update.
        # Effectively turns ACKTR into Natural PG when turned off.
        "line_search": True,
        "line_search_options": {
            "accept_ratio": 0.1,
            "backtrack_ratio": 0.8,
            "max_backtracks": 15,
            "atol": 1e-7,
        },
        # === Network ===
        # Size and activation of the fully connected networks computing the logits
        # for the policy and value function. No layers means the component is
        # linear in states or actions.
        "module": {"type": "OnPolicyActorCritic", "torch_script": False},
        # === Exploration Settings ===
        # Default exploration behavior, iff `explore`=None is passed into
        # compute_action(s).
        # Set to False for no exploration behavior (e.g., for evaluation).
        "explore": True,
        # Provide a dict specifying the Exploration object's config.
        "exploration_config": {
            # The Exploration class to use. In the simplest case, this is the name
            # (str) of any class present in the `rllib.utils.exploration` package.
            # You can also provide the python class directly or the full location
            # of your class (e.g. "ray.rllib.utils.exploration.epsilon_greedy.
            # EpsilonGreedy").
            "type": "raylab.utils.exploration.StochasticActor",
        },
        # === Evaluation ===
        # Extra arguments to pass to evaluation workers.
        # Typical usage is to pass extra args to evaluation env creator
        # and to disable exploration by computing deterministic actions
        "evaluation_config": {"explore": True},
    }
)


class ACKTRTrainer(TRPOTrainer):
    """Single agent trainer for ACKTR."""

    _name = "ACKTR"
    _default_config = DEFAULT_CONFIG
    _policy = ACKTRTorchPolicy

    @staticmethod
    def _validate_config(config):
        assert (
            config["module"].get("torch_script", False) is False
        ), "KFAC incompatible with TorchScript."
