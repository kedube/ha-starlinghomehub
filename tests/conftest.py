"""Shared fixtures for the Starling Home Hub tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow loading custom_components.* in every test."""
    yield
