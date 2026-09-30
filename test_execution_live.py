import asyncio
import json
from MetaApiWrapper import MetaApiWrapper

async def test_order():
    with open('/home/solveetcoagula/odin_ftmo/config_us100.json', 'r') as f:
        cfg = json.load(f)
    token = cfg['metaapi']['token']
    account_id = cfg['metaapi']['account_id']
    
    wrapper = MetaApiWrapper(token, account_id)
    await wrapper.connect()
    
    print("Placing dummy Buy Limit order for XAUUSD at $1000...")
    try:
        # Place limit order
        res = await wrapper.connection.create_limit_buy_order("XAUUSD", 0.01, 1000.0, options={"comment": "GRIFF_TEST"})
        print(f"Success! Order placed: {res}")
        order_id = res.get('orderId')
        
        # Cancel order
        print(f"Canceling dummy order {order_id}...")
        await wrapper.cancel_order(order_id)
        print("Order successfully canceled. Execution permissions VERIFIED.")
    except Exception as e:
        print(f"Execution failed: {e}")

asyncio.run(test_order())
