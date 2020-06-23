"""Losses for Policy-Aware Model Learning."""
from typing import Dict
from typing import Tuple

import torch
import torch.nn as nn
from ray.rllib import SampleBatch
from torch import Tensor

from .abstract import Loss
from .mixins import EnvFunctionsMixin
from .mle import ModelEnsembleMLE
from .utils import clipped_action_value


class SPAML(EnvFunctionsMixin, Loss):
    """Soft Policy-iteration-Aware Model Learning.

    Computes the decision-aware loss for model ensembles used in Model-Aware
    Policy Optimization.

    Args:
        models: The stochastic model ensemble
        actor: The stochastic policy
        critics: The action-value estimators

    Attributes:
        gamma: Discount factor
        alpha: Entropy regularization coefficient
        grad_estimator: Gradient estimator for expecations ('PD' or 'SF')
        lambda_: Kullback Leibler regularization coefficient

    Note:
        `N` denotes the size of the model ensemble, `O` the size of the
        observation, and `A` the size of the action
    """

    batch_keys = (SampleBatch.CUR_OBS, SampleBatch.ACTIONS, SampleBatch.NEXT_OBS)
    gamma: float
    alpha: float
    grad_estimator: str
    lambda_: float

    def __init__(self, models, actor, critics):
        super().__init__()
        modules = nn.ModuleDict()
        modules["models"] = models
        modules["policy"] = actor
        modules["critics"] = critics
        self._modules = modules

        self.gamma = 0.99
        self.alpha = 0.05
        self.grad_estimator = "SF"
        self.lambda_ = 0.05

        self._loss_mle = ModelEnsembleMLE(models)

    @property
    def initialized(self) -> bool:
        """Whether or not the loss setup is complete."""
        return self._env.initialized

    @property
    def ensemble_size(self) -> int:
        """The number of models in the ensemble."""
        return len(self._modules["models"])

    def compile(self):
        self._modules.update(
            {k: torch.jit.script(self._modules[k]) for k in "models critics".split()}
        )
        self._loss_mle.compile()

    def __call__(self, batch: Dict[str, Tensor]) -> Tuple[Tensor, Dict[str, float]]:
        assert self.initialized, (
            "Environment functions missing. "
            "Did you set reward and termination functions?"
        )
        obs = batch[SampleBatch.CUR_OBS]
        obs = self.expand_for_each_model(obs)
        action = self.generate_action(obs)
        value_target = self.zero_step_action_value(obs, action)
        value_pred = self.one_step_action_value_surrogate(obs, action)
        grad_loss = self.action_gradient_loss(action, value_target, value_pred)
        mle_loss = self.maximum_likelihood_loss(batch)

        loss = grad_loss + self.lambda_ * mle_loss
        info = {f"loss(models[{i}])": loss for i, loss in enumerate(loss.tolist())}
        info["loss(daml)"] = grad_loss.mean().item()
        info["loss(mle)"] = mle_loss.mean().item()
        return loss, info

    def expand_for_each_model(self, obs: Tensor) -> Tensor:
        """Expands the observation to match the size of the model ensemble.

        Args:
            obs: The observation tensor of shape `(*, O)`

        Returns:
            The observation tensor expanded to shape `(N, *, O)`
        """
        return obs.expand((self.ensemble_size,) + obs.shape)

    @torch.no_grad()
    def generate_action(self, obs: Tensor) -> Tensor:
        """Given state, sample action with the stochastic policy.

        Generates one action for each of the `N` models in the ensemble, so that
        action gradients and subsequent losses may be calculated for each model.

        Args:
            obs: The current observation tensor of shape `(N, *, O)`

        Returns:
            The action tensor of shape `(N, *, A)` with `requires_grad` enabled
        """
        action, _ = self._modules["policy"].sample(obs)
        return action.requires_grad_(True)

    def zero_step_action_value(self, obs: Tensor, action: Tensor) -> Tensor:
        """Compute action-value directly using approximate critic.

        Calculates :math:`Q^{\\pi}(s, a)` as a target for each model in the
        ensemble. Each value is the minimum among critic predictions.

        Args:
            obs: The observation tensor of shape `(N, *, O)`
            action: The action Tensor of shape `(N, *, A)`

        Returns:
            The action-value tensor of shape `(N, *)`
        """
        return clipped_action_value(obs, action, self._modules["critics"])

    def one_step_action_value_surrogate(self, obs: Tensor, action: Tensor) -> Tensor:
        """Surrogate loss for gradient estimation of action values.

        Computes :math::

            Q^{\\pi}(s, a) =
                \\rewardfn(\\state, \\action)
                + \\gamma
                \\EXV_{
                    \\substack{
                        \\state'\\sim\\model(\\state, \\action)
                        \\ \\xi' \\sim p_{\\xi}
                    }
                } \\bkt*{
                    \\evalat{\\action'=\\detpol(\\state'; \\xi')}{
                    \\Qval(\\state', \action')
                    - \\log \\pitheta(\\action' \\given \\state')
                    }
                }

        Args:
            obs: The observation tensor of shape `(N, *, O)`
            action: The action Tensor of shape `(N, *, A)`

        Returns:
            A tensor of shape `(N, *)` for estimating the gradient of the 1-step
            action-value function.
        """
        next_obs, log_prob = self.transition(obs, action)

        # Next action grads shouldn't propagate
        # Only gradients through the next state, model, and current action
        # should propagate to policy parameters
        self._modules["policy"].requires_grad_(False)
        next_act, logp = self._modules["policy"].rsample(next_obs)
        self._modules["policy"].requires_grad_(True)

        next_qval = clipped_action_value(next_obs, next_act, self._modules["critics"])

        reward = self._env.reward(obs, action, next_obs)
        done = self._env.termination(obs, action, next_obs)

        next_vval = (
            torch.where(done, reward, reward + self.gamma * next_qval)
            - self.alpha * logp
        )

        if self.grad_estimator == "SF":
            surrogate = log_prob * next_vval.detach()
        elif self.grad_estimator == "PD":
            surrogate = next_vval
        return surrogate

    def transition(self, obs: Tensor, action: Tensor) -> Tuple[Tensor, Tensor]:
        """Compute virtual transition and its log density.

        Args:
            obs: The current state tensor of shape `(N, *, O)`
            action: The action tensor of shape `(N, *, A)` sampled from the
                stochastic policy

        Returns:
            A tuple with the next state tensor of shape `(N, *, O)` and its
            log-likelihood tensor of shape `(N, *)` generated from models in the
            ensemble
        """
        models = self._modules["models"]

        if self.grad_estimator == "SF":
            model_outputs = [m.sample(obs[i], action[i]) for i, m in enumerate(models)]
        elif self.grad_estimator == "PD":
            model_outputs = [m.rsample(obs[i], action[i]) for i, m in enumerate(models)]

        next_obs = torch.stack([o for o, _ in model_outputs])
        logp = torch.stack([l for _, l in model_outputs])
        return next_obs, logp

    @staticmethod
    def action_gradient_loss(
        action: Tensor, value_target: Tensor, value_pred: Tensor
    ) -> Tensor:
        """Decision-aware model loss based on action gradients.

        Args:
            action: The action tensor of shape `(N, *, A)`
            value_target: The estimated action-value gradient target tensor of
                shape `(N, *)`
            value_pred: The surrogate loss tensor of shape `(N, *)` for action
                gradient estimation of the 1-step action-value

        Returns:
            The loss tensor of shape `(N,)`
        """
        temporal_diff = value_target - value_pred
        (action_gradient,) = torch.autograd.grad(
            temporal_diff.sum(), action, create_graph=True
        )
        return action_gradient.abs().sum(dim=-1).mean(dim=-1)

    def maximum_likelihood_loss(self, batch: Dict[str, Tensor]) -> Tensor:
        """Model regularization through Maximum Likelihood.

        Args:
            batch: The tensor batch with SampleBatch.CUR_OBS,
                SampleBatch.ACTIONS, and SampleBatch.NEXT_OBS keys

        Returns:
            The loss tensor of shape `(N,)`, where `N` is the number of models
            the ensemble
        """
        loss, _ = self._loss_mle(batch)
        return loss
