"""Registry of old modules for PyTorch policies."""
import torch.nn as nn
from gym.spaces import Space

from .ddpg_module import DDPGModule
from .maxent_model_based import MaxEntModelBased
from .model_based_ddpg import ModelBasedDDPG
from .model_based_sac import ModelBasedSAC
from .naf_module import NAFModule
from .nfmbrl import NFMBRL
from .off_policy_nfac import OffPolicyNFAC
from .on_policy_actor_critic import OnPolicyActorCritic
from .on_policy_nfac import OnPolicyNFAC
from .sac_module import SACModule
from .simple_model_based import SimpleModelBased
from .svg_module import SVGModule
from .svg_realnvp_actor import SVGRealNVPActor
from .trpo_tang2018 import TRPOTang2018

MODULES = {
    cls.__name__: cls
    for cls in (
        NAFModule,
        DDPGModule,
        SACModule,
        SimpleModelBased,
        SVGModule,
        MaxEntModelBased,
        ModelBasedDDPG,
        ModelBasedSAC,
        NFMBRL,
        OnPolicyActorCritic,
        OnPolicyNFAC,
        OffPolicyNFAC,
        TRPOTang2018,
        SVGRealNVPActor,
    )
}


def get_module(obs_space: Space, action_space: Space, config: dict) -> nn.Module:
    """Retrieve and construct module of given name.

    Args:
        obs_space: Observation space
        action_space: Action space
        config: Configurations for module construction and initialization
    """
    type_ = config.pop("type")
    return MODULES[type_](obs_space, action_space, config)