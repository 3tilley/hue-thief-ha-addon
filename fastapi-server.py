import asyncio
from litestar import App, Route
from pydantic import BaseModel

from hue_thief import steal, identify_bulb, send_reset, prepare_config

app = App()

# Pydantic models for request parameters
class IdentifyBulbRequest(BaseModel):
    address: str
    transaction_id: str
    channel: int

class ResetBulbRequest(BaseModel):
    address: str
    transaction_id: str
    channel: int

# Class for handling all bulb routes
class BulbRoutes(Route):
    def __init__(self, dev, eui64):
        self.dev = dev
        self.eui64 = eui64
        self.method_lock = asyncio.Lock()

    async def get_bulbs(self, channel: int):
        async with self.method_lock:
            try:
                bulbs = steal(self.dev, self.eui64, channel, reset_prompt=False, clean_up=False)
                return {"bulbs": bulbs}
            except Exception as e:
                return {"error": str(e)}, 500

    async def post_identify_bulb(self, data: IdentifyBulbRequest):
        async with self.method_lock:
            try:
                result = identify_bulb(self.dev, self.eui64, data.address, data.transaction_id, data.channel)
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}, 500

    async def post_reset_bulb(self, data: ResetBulbRequest):
        async with self.method_lock:
            try:
                result = send_reset(self.dev, self.eui64, data.address, data.transaction_id, data.channel)
                return {"result": result}
            except Exception as e:
                return {"error": str(e)}, 500

# Get device configuration
dev, eui64 = prepare_config()

# Register the route class with the app
bulb_routes = BulbRoutes(dev, eui64)
app.register("/bulbs", bulb_routes.get_bulbs, methods=["GET"])
app.register("/identify_bulb", bulb_routes.post_identify_bulb, methods=["POST"])
app.register("/reset_bulb", bulb_routes.post_reset_bulb, methods=["POST"])

# Run the LiteStar application
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
