import json
from datetime import datetime
from pathlib import Path


class LogManager:
    def __init__(self):
        self.data = {
            "dataset": None,
            "training_time": None,
            "learning_rate": None,
            "training_algorithm": None,
            "gpu_training": False,
            "epochs": False,
            "test_accuracies": [],
            "training_time_epoch": [],
        }

    def update(self, key, value):
        if key == "accuracy":
            self.data["test_accuracies"].append(value)
        if key == "epoch_time":
            self.data["training_time_epoch"].append(value)
        else:
            self.data[key] = value

    def save(self, results_path="results"):
        timestamp = datetime.now().strftime("%Y%m%d-%H%M")
        algorithm = self.data["training_algorithm"]
        use_gpu = self.data["gpu_training"]
        dataset = self.data["dataset"]
        epochs = self.data["epochs"]
        log_file = f"{algorithm}_{'gpu' if use_gpu else 'cpu'}_{dataset}_{epochs}_epochs_{timestamp}.json"

        log_file_path = Path.home() / results_path / log_file

        with open(log_file_path, "w") as f:
            json.dump(self.data, f)


log_manager = LogManager()
