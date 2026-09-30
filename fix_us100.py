import re

with open('/home/solveetcoagula/odin_ftmo/griff_engine_us100.py', 'r') as f:
    content = f.read()

# Add argparse and load_metaapi_token logic at the bottom
new_bottom = """
import argparse
import json

def load_metaapi_token(config_path="config.json"):
    with open(config_path, "r") as f:
        cfg = json.load(f)
    return cfg.get("metaapi", {}).get("token", "")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--config", default="config.json")
    args = parser.parse_args()
    
    token = load_metaapi_token(args.config)
    engine = US100Engine(token=token, account_id=args.account_id)
    
    def handle_sigint(sig, frame):
        logger.info("Received termination signal.")
        engine.is_running = False
        import sys
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    
    asyncio.run(engine.run_loop())
"""
# Replace bottom
content = re.sub(r'if __name__ == "__main__":.*', new_bottom, content, flags=re.DOTALL)

# Fix US100Engine __init__
old_init = """    def __init__(self, config_path: str = "config_us100.json"):
        self.config_path = config_path
        self.wrapper = MetaApiWrapper()"""
new_init = """    def __init__(self, token, account_id, config_path: str = "config_us100.json"):
        self.config_path = config_path
        self.wrapper = MetaApiWrapper(token, account_id)"""
content = content.replace(old_init, new_init)

with open('/home/solveetcoagula/odin_ftmo/griff_engine_us100.py', 'w') as f:
    f.write(content)
