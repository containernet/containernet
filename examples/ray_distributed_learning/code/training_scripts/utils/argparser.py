import argparse
from ..algorithms import algorithm_names


def get_argparser():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--address", required=False, type=str, default=None, help="the address to use for Ray"
    )
    parser.add_argument(
        "--num-workers",
        "-n",
        type=int,
        default=3,
        help="Sets number of workers for training.",
    )
    parser.add_argument(
        "--iter", type=int, default=30, help="Set number of iterations for training"
    )

    parser.add_argument(
        "--model", required=True, type=str, default="convnet", help="The model to use for training and inference"
    )

    parser.add_argument(
        "--use-gpu", action="store_true", default=False, help="Enables GPU training"
    )

    parser.add_argument(
        "--dataset", type=str, default="mnist", help="Set Dataset"
    )
    parser.add_argument(
        "--algorithm", type=str, choices=algorithm_names(), help="Set distributed training algorithm"
    )

    return parser