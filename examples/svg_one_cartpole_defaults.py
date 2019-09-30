"""Tune experiment configuration for SVG(1) on CartPoleSwingUp.

This can be run from the command line by executing
`python scripts/tune_experiment.py 'SVG(1)' --local-dir <experiment dir>
    --config examples/svg_one_cartpole_defaults.py --stop timesteps_total 100000`
"""
from ray import tune  # pylint: disable=unused-import


def get_config():  # pylint: disable=missing-docstring
    return {
        # === Environment ===
        "env": "CartPoleSwingUp",
        "env_config": {"max_episode_steps": 250, "time_aware": True},
        # === Replay Buffer ===
        "buffer_size": int(1e5),
        # === Optimization ===
        # Name of Pytorch optimizer class for paremetrized policy
        "torch_optimizer": "Adam",
        # Keyword arguments to be passed to the on-policy optimizer
        "torch_optimizer_options": {
            "model": {"lr": 1e-3},
            "value": {"lr": 1e-3},
            "policy": {"lr": tune.grid_search([3e-4])},
        },
        # Clip gradient norms by this value
        "max_grad_norm": 40.0,
        # === Regularization ===
        "kl_schedule": {"initial_coeff": tune.grid_search([0.0])},
        # === Network ===
        # Size and activation of the fully connected networks computing the logits
        # for the policy, value function and model. No layers means the component is
        # linear in states and/or actions.
        "module": {
            "policy": {"layers": [100, 100], "input_dependent_scale": False},
            "value": {"layers": [200, 100]},
            "model": {"layers": [20, 20], "delay_action": True},
        },
        # === RolloutWorker ===
        "sample_batch_size": 1,
        "batch_mode": "complete_episodes",
        # === Trainer ===
        "train_batch_size": 100,
        # === Debugging ===
        # Set the ray.rllib.* log level for the agent process and its workers.
        # Should be one of DEBUG, INFO, WARN, or ERROR. The DEBUG level will also
        # periodically print out summaries of relevant internal dataflow (this is
        # also printed out once at startup at the INFO level).
        "log_level": "WARN",
    }