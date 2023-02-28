import argparse

import torch
from torchvision import datasets, transforms
from torchvision.transforms import ToTensor

mnist_transforms = transforms.Compose(
    [transforms.ToTensor(), transforms.Normalize((0.1307,), (0.3081,))])


def get_data_loader(dataset: str, batch_size: int = 64, shuffle_data: bool = True):
    if dataset == "mnist":
        train_dataset = datasets.MNIST("~/data", train=True, download=True, transform=mnist_transforms)
        test_dataset = datasets.MNIST("~/data", train=False, download=True, transform=mnist_transforms)
    else:
        train_dataset = datasets.FashionMNIST(
            root="~/data",
            train=True,
            download=True,
            transform=ToTensor(),
        )
        test_dataset = datasets.FashionMNIST(
            root="~/data",
            train=True,
            download=True,
            transform=ToTensor(),
        )

    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=shuffle_data)
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=shuffle_data)

    return train_loader, test_loader


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=str, required=True, help="Specify dataset to download. Choices: [mnist, fashion_mnist]"
    )

    args, _ = parser.parse_known_args()

    if args.data == "mnist":
        datasets.MNIST(
            "~/data", train=True, download=True, transform=mnist_transforms
        )

        datasets.MNIST("~/data", download=True, train=False, transform=mnist_transforms)

    elif args.data == "fashion_mnist":
        datasets.FashionMNIST(
            root="~/data",
            train=True,
            download=True,
            transform=ToTensor(),
        )
        datasets.FashionMNIST(
            root="~/data",
            train=False,
            download=True,
            transform=ToTensor(),
        )
