"""Classifieur de marques : constantes et briques partagées entre l'inférence et l'entraînement.

Importable sans ultralytics ni OCR : le conteneur d'entraînement n'en a pas besoin.
"""

import torch
from torchvision import transforms
from torchvision.models import efficientnet_b0

BRAND_INPUT_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
ARCH = "efficientnet_b0"


def build_brand_model(num_classes: int) -> torch.nn.Module:
    model = efficientnet_b0(weights=None)
    model.classifier[1] = torch.nn.Linear(model.classifier[1].in_features, num_classes)
    return model


def brand_eval_transform() -> transforms.Compose:
    return transforms.Compose(
        [
            transforms.Resize((BRAND_INPUT_SIZE, BRAND_INPUT_SIZE)),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )
