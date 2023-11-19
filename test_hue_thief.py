from unittest.mock import MagicMock, patch
import sys

import pytest

try:
    import pure_pcapy
    import bellows
except ModuleNotFoundError:
    pure_pcapy = MagicMock()
    bellows = MagicMock()

sys.modules["pure_pcapy"] = pure_pcapy
sys.modules["bellows"] = bellows
sys.modules["bellows.cli.util"] = MagicMock()
sys.modules["interpanZll"] = MagicMock()


import hue_thief

@pytest.fixture()
def imports(monkeypatch):
    monkeypatch.setitem(sys.modules, "hue_thief.pure_pcapy", pure_pcapy)
    monkeypatch.setitem(sys.modules, "hue_thief.bellows", bellows)

@pytest.mark.asyncio
async def test_touchlink(imports):
    tl = await hue_thief.Touchlink.create("hello", 115200)
    await tl.scan_channel(11)

@pytest.mark.asyncio
async def test_steal(imports):
    await hue_thief.steal("hello", 115200, 11, reset_prompt=False, clean_up=True, config=None)
    
