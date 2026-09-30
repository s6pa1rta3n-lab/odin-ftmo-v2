import asyncio
import json
import logging
import sys
from MetaApiWrapper import MetaApiWrapper

logging.basicConfig(level=logging.INFO)

async def main():
    try:
        with open("config_xau.json", "r") as f:
            conf = json.load(f)
            
        wrapper = MetaApiWrapper(
            token=conf["metaapi_token"],
            account_id="45a2565b-4f53-4bd5-8c58-667b3660430f"
        )
        
        connected = await wrapper.connect()
        if not connected:
            print("Failed to connect")
            return
            
        print("Closing 7.00 lots of position 544310149...")
        res = await wrapper.connection.close_position_partially("544310149", 7.00)
        print(f"Close Response: {json.dumps(res, indent=2)}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
