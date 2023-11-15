# Import the functions for getting bulbs, identifying a bulb, and resetting a bulb

import asyncio
import argparse

from fastapi import FastAPI, HTTPException, Request, Depends, Body
from pydantic import BaseModel

import hue_thief
from hue_thief import steal, identify_bulb, send_reset, prepare_config

app = FastAPI()

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
@app.get("/bulbs")
async def list_bulbs():
    async with method_lock:
        try:
            bulbs = steal(args.device, args.baud_rate, args.channel, reset_prompt=False, clean_up=False, config=(dev, eui64))  # Pass command-line arguments to the function
            return {"bulbs": bulbs}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Define a route to identify a bulb
@app.post("/identify_bulb")
async def identify_bulb_endpoint(request: Request, data: IdentifyBulbRequest):
    async with method_lock:
        try:
            result = identify_bulb(dev, eui64, data.address, data.transaction_id, data.channel)  # Pass command-line arguments to the function
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

# Define a route to reset a bulb
@app.post("/reset_bulb")
async def reset_bulb(request: Request, data: ResetBulbRequest):
    async with method_lock:
        try:
            result = send_reset(dev, eui64, data.address, data.transaction_id, data.channel)  # Pass command-line arguments to the function
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Command-line argument parsing using argparse inside the main block
    parser = argparse.ArgumentParser(description="FastAPI for controlling bulbs")
    parser.add_argument("--device", type=str, help="Device name or address", required=True)
    parser.add_argument("--baud_rate", type=int, help="Baud rate for the device", required=True)
    parser.add_argument("--channel", type=int, help="Channel for the device")
    args = parser.parse_args()

    dev, eui64 = prepare_config()
    # Run the application with a single worker using uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8050)
