from __future__ import annotations

import importlib

from beanbot.features.registry import FEATURE_EXTENSIONS


def test_every_registered_feature_extension_is_importable() -> None:
    imported = [importlib.import_module(module_name) for module_name in FEATURE_EXTENSIONS]

    assert len(imported) == len(FEATURE_EXTENSIONS)
    assert all(module.__name__.startswith("beanbot.features.") for module in imported)
