import copy
import unittest

import torch
import torch.nn.functional as F

from blades.adversaries import NoiseAdversary
from blades.algorithms.fedavg import FedavgConfig
from fllib.datasets.catalog import DatasetCatalog

from .simple_dataset import SimpleDataset


class TestAdaptiveAdversary(unittest.TestCase):
    def setUp(self):
        DatasetCatalog.register_custom_dataset("simple", SimpleDataset)
        model = torch.nn.Linear(2, 2)
        self.alg = (
            FedavgConfig()
            .resources(num_remote_workers=2, num_gpus_per_worker=0)
            .data(
                num_clients=3,
                dataset_config={
                    "custom_dataset": "simple",
                    "num_classes": 2,
                    # "custom_dataset_config": {"num_classes": 2},
                },
            )
            .training(
                global_model=model,
                server_config={"lr": 0.1, "aggregator": {"type": "Mean"}},
            )
            .adversary(
                num_malicious_clients=1,
                adversary_config={"type": NoiseAdversary},
            )
            .build()
        )
        self.global_dataset = DatasetCatalog.get_dataset(
            {
                "custom_dataset": "simple",
                "num_classes": 2,
                # "custom_dataset_config": {"num_classes": 2},
            },
            num_clients=1,
            train_bs=3,
        )

    def test_on_local_round_end(self):
        uid = self.global_dataset.client_ids[0]
        train_loader = self.global_dataset.get_train_loader(uid)

        for _ in range(5):
            data, target = next(train_loader)
            model = copy.deepcopy(self.alg.server.get_global_model())
            opt = torch.optim.SGD(model.parameters(), lr=0.1)
            model.train()
            output = model(data)
            loss = F.cross_entropy(output, target)
            loss.backward()
            opt.step()

            self.alg.training_step()
            updated_model = copy.deepcopy(self.alg.server.get_global_model())

            self.assertFalse(torch.allclose(model.weight, updated_model.weight))


if __name__ == "__main__":
    unittest.main()
