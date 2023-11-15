import asyncio
from lits import App
from pydantic import BaseModel

from hue_thief import steal, identify_bulb, send_reset, prepare_config

app = App()

# Get device configuration
dev, eui64 = prepare_config()

# Use asyncio to lock access to methods to ensure non-concurrent execution
method_lock = asyncio.Lock()

# Pydantic models for request parameters
class IdentifyBulbRequest(BaseModel):
    address: str
    transaction_id: str
    channel: int

class ResetBulbRequest(BaseModel):
    address: str
    transaction_id: str
    channel: int

# Define a route to get a list of bulbs
@app.route("/bulbs", methods=["GET"])
async def list_bulbs(channel: int):
    async with method_lock:
        try:
            bulbs = steal(dev, eui64, channel, reset_prompt=False, clean_up=False)
            return {"bulbs": bulbs}
        except Exception as e:
            return {"error": str(e)}, 500

# Define a route to identify a bulb
@app.route("/identify_bulb", methods=["POST"])
async def identify_bulb_endpoint(data: IdentifyBulbRequest):
    async with method_lock:
        try:
            result = identify_bulb(dev, eui64, data.address, data.transaction_id, data.channel)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}, 500

# Define a route to reset a bulb
@app.route("/reset_bulb", methods=["POST"])
async def reset_bulb(data: ResetBulbRequest):
    async with method_lock:
        try:
            result = send_reset(dev, eui64, data.address, data.transaction_id, data.channel)
            return {"result": result}
        except Exception as e:
            return {"error": str(e)}, 500

# Run the LiteStar application
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050)
