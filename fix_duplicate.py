import asyncio
from metaapi_cloud_sdk import MetaApi
import os
import json

async def fix_duplicate():
    token = os.environ.get("META_API_TOKEN", "your_token_here")  # Wait, how does monitor_griff.py get it?
    # Let me grep it from monitor_griff.py!
