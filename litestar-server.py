import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
import os

import litestar.exceptions
from litestar import Litestar, get, post, Controller, MediaType
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import State
from litestar.response import Template
from litestar.template import TemplateConfig

# Generate skeletons for Windows only
try:
    from hue_thief import steal, identify_bulb, send_reset, prepare_config
except ImportError:
    if os.name == "nt":
        def steal(*args, **kwargs):
            return set([("abc", "TRANSID", "11")])

        def identify_bulb(*args, **kwargs):
            pass

        def send_reset(*args, **kwargs):
            pass

        def prepare_config(*args, **kwargs):
            return None, None
    else:
        raise


# Pydantic models for request parameters
@dataclass
class IdentifyBulbRequest:
    address: str
    transaction_id: str
    channel: int

@dataclass
class ResetBulbRequest:
    address: str
    transaction_id: str
    channel: int


@dataclass
class Bulb:
    address: str
    transaction_id: str
    channel: int


@dataclass
class BulbsResponse:
    bulbs: list[Bulb]

# Class for handling all bulb routes
class BulbRoutes(Controller):
    method_lock = asyncio.Lock()
    @get("/bulbs")
    async def get_bulbs(self, state: State, channel: int | None) -> BulbsResponse:
        async with self.method_lock:
            try:
                bulbs = steal(state.radio_config[0], state.radio_config[1], channel, reset_prompt=False, clean_up=False)
                res = BulbsResponse(bulbs=[Bulb(address=bulb[0], transaction_id=bulb[1], channel=bulb[2]) for bulb in bulbs])
                return res
            except Exception as e:
                raise litestar.exceptions.HTTPException from e

    @post("/identify_bulb")
    async def post_identify_bulb(self, state: State, data: IdentifyBulbRequest) -> None:
        async with self.method_lock:
            result = identify_bulb(state.radio_config[0], state.radio_config[1], data.address, data.transaction_id, data.channel)
        return litestar.Response(status_code=200, content="Flashing bulb")

    @post("/reset_bulb")
    async def post_reset_bulb(self, state: State, data: ResetBulbRequest) -> None:
        async with self.method_lock:
            result = send_reset(state.radio_config[0], state.radio_config[1], data.address, data.transaction_id, data.channel)
        return litestar.Response(status_code=200, content="Reset bulb")

def get_db_connection(app: Litestar) -> tuple:
    """Returns the db engine.

    If it doesn't exist, creates it and saves it in on the application state object
    """
    if not getattr(app.state, "radio_config", None):
        app.state.radio_config = prepare_config()
    return app.state.radio_config


async def close_db_connection(app: Litestar) -> None:
    """Closes the db connection stored in the application State object."""
    if getattr(app.state, "engine", None):
        dev, eui64 = app.state.radio_config

        await dev.mfglibEnd()
        dev.close()


@get("/", media_type=MediaType.HTML)
async def index()  -> str:
    index = Path(__file__).parent / "index.html"
    return index.read_text()

# Run the LiteStar application
if __name__ == "__main__":
    import uvicorn

    app = Litestar(debug=True, route_handlers=[BulbRoutes, index],
                   on_startup=[get_db_connection],
                   on_shutdown=[close_db_connection],
                   template_config=TemplateConfig(
                       directory=Path("."),
                       engine=JinjaTemplateEngine,
                   ),
                )

    uvicorn.run(app, host="0.0.0.0", port=8050)
