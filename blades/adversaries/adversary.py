import copy
from typing import Any, Dict, Type, List
import torch
from ray.rllib.utils.from_config import from_config
from fllib.algorithms import Algorithm
from fllib.constants import CLIENT_UPDATE


class Adversary:
    def __init__(
        self, clients: List, global_config: Dict = None, malicious_client_cls=None
    ):
        self.clients = clients
        self.global_config = global_config

    def get_benign_updates(self, algorithm) -> torch.Tensor:
        updates = []
        for result in algorithm.local_results:
            psudo_grad = result.get(CLIENT_UPDATE, None)
            client = algorithm.client_manager.get_client_by_id(result["id"])
            if psudo_grad is not None and not client.is_malicious:
                updates.append(psudo_grad)

        if not updates:
            raise ValueError(
                "No benign updates found. To use this adversary,"
                "you must have at least one benign client."
            )
        return torch.vstack(updates)

    def on_algorithm_start(self, algorithm: Algorithm):
        for client in self.clients:
            client.to_malicious(local_training=False)

    def on_local_round_end(self, algorithm):
        pass


class AdversaryConfig:
    def __init__(self, adversary_cls=Adversary, config=None) -> None:
        self.adversary_class: Type["Adversary"] = adversary_cls
        self.global_config: Dict[str, Any] = config

    def to_dict(self) -> dict:
        """Converts all settings into a legacy config dict for backward
        compatibility.

        Returns:
            A complete AlgorithmConfigDict, usable in backward-compatible Tune/RLlib
            use cases, e.g. w/ `tune.Tuner().fit()`.
        """
        config = copy.deepcopy(vars(self))

        return config

    def build(self, clients: List) -> "Adversary":
        """Builds the Adversary instance."""
        config_dict = self.to_dict()
        cls = config_dict.pop("adversary_class")
        return from_config(cls, config_dict, clients=clients)

    def update_from_dict(
        self,
        config_dict: Dict,
    ) -> "AdversaryConfig":
        """Modifies this AlgorithmConfig via the provided python config dict.

        Warns if `config_dict` contains deprecated keys.
        Silently sets even properties of `self` that do NOT exist. This way, this method
        may be used to configure custom Policies which do not have their own specific
        AlgorithmConfig classes, e.g.
        `ray.rllib.examples.policy.random_policy::RandomPolicy`.

        Args:
            config_dict: The old-style python config dict (PartialAlgorithmConfigDict)
                to use for overriding some properties defined in there.

        Returns:
            This updated AlgorithmConfig object.
        """

        # Modify our properties one by one.
        for key, value in config_dict.items():
            setattr(self, key, value)
        return self
