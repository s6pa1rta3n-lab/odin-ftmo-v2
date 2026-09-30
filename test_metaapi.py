import asyncio
from metaapi_cloud_sdk import MetaApi
import json

async def main():
    with open('/Users/solveetcoagula/Desktop/google_cloud/config_us100.json') as f:
        config = json.load(f)
    token = config['metaapi']['token']
    account_id = config['metaapi']['account_id']

    api = MetaApi(token)
    account = await api.metatrader_account_api.get_account(account_id)
    print("Account state:", account.state)
    
    conn = account.get_streaming_connection()
    await conn.connect()
    print("Waiting to synchronize (30s timeout)...")
    try:
        await asyncio.wait_for(conn.wait_synchronized(), timeout=30.0)
        print("Synchronized!")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await conn.close()

asyncio.run(main())
