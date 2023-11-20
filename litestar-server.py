import argparse
import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
import os

import litestar.exceptions
from litestar import Litestar, get, post, Controller, MediaType
from litestar.contrib.htmx.request import HTMXRequest
from litestar.contrib.htmx.response import Reswap, HTMXTemplate
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.datastructures import State
from litestar.template import TemplateConfig

import pydantic

logger = logging.getLogger(__name__)

# Generate skeletons for Windows only
try:
    from hue_thief import steal, prepare_config, Touchlink, Target
except ImportError:
    if os.name == "nt":
        @dataclass
        class Target:
            ext_address: str
            transaction_id: int
            signal_strength: int
            channel: int

        class Touchlink:

            def __init__(self, *args, **kwargs):
                pass

            @classmethod
            async def create(cls, device_path, baud_rate):
                return cls()

            async def scan_channel(self, channel, *args, **kwargs):
                await asyncio.sleep(2)
                return [Target("abc", 123, 11, channel)]
                #return set()

            async def identify_bulb(self, *args, **kwargs):
                await asyncio.sleep(2)

            async def send_reset(self, *args, **kwargs):
                await asyncio.sleep(2)

            async def close(self):
                pass

        async def steal(*args, **kwargs):
            await asyncio.sleep(2)
            return set([("abc", 123, 11)])
            #return set()

        async def identify_bulb(*args, **kwargs):
            await asyncio.sleep(2)
            pass

        async def send_reset(*args, **kwargs):
            await asyncio.sleep(2)
            pass

        async def prepare_config(*args, **kwargs):
            return ("dev", "euifake")

    else:
        raise


# Pydantic models for request parameters
# @dataclass
# class IdentifyBulbRequest:
class IdentifyBulbRequest(pydantic.BaseModel):
    address: str
    transaction_id: int
    channel: int

# @dataclass
# class ResetBulbRequest:
class ResetBulbRequest(pydantic.BaseModel):
    address: str
    transaction_id: int
    channel: int


# @dataclass
# class Bulb:
class Bulb(pydantic.BaseModel):
    address: str
    transaction_id: int
    channel: int
    signal_strength: int

    def from_target(target):
        return Bulb(address=target.ext_address, transaction_id=target.transaction_id, channel=target.channel, signal_strength=target.signal_strength)


@dataclass
class BulbsResponse:
    bulbs: list[Bulb]

# Class for handling all bulb routes
class BulbRoutes(Controller):
    method_lock = asyncio.Lock()

    async def bulbs(self, state: State, channel: int | None) -> BulbsResponse:
        channels = [channel] if channel else range(11, 27)
        async with self.method_lock:
            touchlink = await Touchlink.create(state.device_path, state.baud_rate)
            all_bulbs = []
            for c in channels:
                logging.debug(f"Scanning on channel {c}")
                bulbs = await touchlink.scan_channel(c)
                all_bulbs.extend(bulbs)
            # print(f"dev: {type(state.radio_config[0])} - {state.radio_config[0]}, eui64: {type(state.radio_config[1])} - {state.radio_config[1]}")
            print(f"State: {state}")
            await touchlink.close()

            # bulbs = await steal(state.radio_config[0], state.radio_config[1], channel, reset_prompt=False, clean_up=False)
            res = BulbsResponse(bulbs=[Bulb.from_target(bulb) for bulb in all_bulbs])
            return res

    @get("/bulbs")
    async def get_bulbs(self, state: State, channel: int | None) -> BulbsResponse:
        try:
            return await self.bulbs(state, channel)
        except Exception as e:
            raise litestar.exceptions.HTTPException from e

    @get("/bulbs_htmx")
    async def get_bulbs_htmx(self, state: State, channel: int | None) -> Reswap:
        bulbs = await self.bulbs(state, channel)
        template = HTMXTemplate(template_name="bulb_table.html", context={"bulbs": bulbs.bulbs}, re_swap="InnerHTML")#, re_target="bulbs-content")
        return template


    @post("/identify_bulb")
    async def identify_bulb(self, state: State, data: IdentifyBulbRequest) -> None:
        async with self.method_lock:
            touchlink = await Touchlink.create(state.device_path, state.baud_rate)
            result = await touchlink.identify_bulb(data.address, data.transaction_id, data.channel)
            await touchlink.close()
        return litestar.Response(status_code=200, content="Flashing bulb")

    @post("/identify_bulb_htmx")
    async def identify_bulb_htmx(self, state: State, data: IdentifyBulbRequest) -> None:
        async with self.method_lock:
            touchlink = await Touchlink.create(state.device_path, state.baud_rate)
            result = await touchlink.identify_bulb(data.address, data.transaction_id, data.channel)
            # result = await identify_bulb(state.radio_config[0], state.radio_config[1], "fdsfds", data.transaction_id, data.channel)
            await touchlink.close()
        return litestar.Response(status_code=200, content="Flashing bulb")

    @post("/reset_bulb")
    async def post_reset_bulb(self, state: State, data: ResetBulbRequest) -> None:
        async with self.method_lock:
            touchlink = await Touchlink.create(state.device_path, state.baud_rate)
            result = await touchlink.send_reset(data.address, data.transaction_id, data.channel)
            await touchlink.close()
        return litestar.Response(status_code=200, content="Bulb reset")

def make_config(device_path, baudrate):
    async def get_db_connection(app: Litestar) -> tuple:
        print("Preparing config")
        app.state.device_path = device_path
        app.state.baud_rate = baudrate
        # if not getattr(app.state, "radio_config", None):
        #     dev, eui64 = await prepare_config(device_path, baudrate)
        #     app.state.radio_config = (dev, eui64)
        # print(f"dev: {type(app.state.radio_config[0])} - {app.state.radio_config[0]}, eui64: {type(app.state.radio_config[1])} - {app.state.radio_config[1]}")

        app.state.device_path = device_path
        app.state.baud_rate = baudrate
        # return app.state.radio_config

    return get_db_connection


async def close_db_connection(app: Litestar) -> None:
    """Closes the db connection stored in the application State object."""
    if getattr(app.state, "engine", None):
        dev, eui64 = app.state.radio_config

        await dev.mfglibEnd()
        dev.close()


@get("/", media_type=MediaType.HTML)
async def index(state: State)  -> str:
    index = Path(__file__).parent / "index.html"

    return index.read_text().replace("{{ fake-jinja-device }}", state.device_path).replace("{{ fake-jinja-baud-rate }}", str(state.baud_rate))

# Run the LiteStar application
if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description='Factory reset a Hue light bulb.')
    parser.add_argument('device', type=str, help='Device path, e.g., /dev/ttyUSB0')
    parser.add_argument('-b', '--baudrate', type=int, default=57600, help='Baud rate (default: 57600)')
    parser.add_argument('-c', '--channel', type=int, help='Zigbee channel (defaults to scanning 11 up to 26)')
    args = parser.parse_args()

    app = Litestar(debug=True, route_handlers=[BulbRoutes, index],
                   on_startup=[make_config(args.device, args.baudrate)],
                   on_shutdown=[close_db_connection],
                   template_config=TemplateConfig(
                       directory=Path("templates"),
                       engine=JinjaTemplateEngine,
                   ),
                )
    print(f"Running server with {args.device} at {args.baudrate} baudrate")

    uvicorn.run(app, host="0.0.0.0", port=8099)
