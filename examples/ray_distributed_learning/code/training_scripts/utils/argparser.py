import argparse
from ..algorithms import algorithm_names
from ..data import dataset_classes


def get_argparser():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--num-workers",
        "-n",
        type=int,
        default=3,
        help="Sets number of workers for training.",
    )
    parser.add_argument(
        "--epochs", type=int, default=3, help="Set number of epochs for training"
    )

    parser.add_argument("--lr", type=float, default=0.01, help="Set the learning rate")

    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Set the batch size for training and testing",
    )

    parser.add_argument(
        "--model",
        required=True,
        type=str,
        default="convnet",
        help="The model to use for training and testing",
    )

    parser.add_argument(
        "--use-cpu", action="store_true", default=False, help="Disables GPU training"
    )

    parser.add_argument(
        "--dataset",
        type=str,
        default="mnist",
        choices=list(dataset_classes.keys()),
        help="Set Dataset",
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        required=True,
        choices=algorithm_names(),
        help="Set distributed training algorithm",
    )

    return parser
