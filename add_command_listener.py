import re

with open("griff_engine_live.py", "r") as f:
    code = f.read()

# I will add this to `async def step(self) -> Dict[str, Any]:`
step_find = """    async def step(self) -> Dict[str, Any]:
        \"\"\"Execute a single strategy evaluation cycle.

        Returns:
            Dict containing current engine state and timestamps.
        \"\"\"
"""
step_replace = """    async def step(self) -> Dict[str, Any]:
        \"\"\"Execute a single strategy evaluation cycle.

        Returns:
            Dict containing current engine state and timestamps.
        \"\"\"
        import os, json
        if os.path.exists("commands.json"):
            try:
                with open("commands.json", "r") as cmd_f:
                    cmds = json.load(cmd_f)
                for cmd in cmds:
                    action = cmd.get("action")
                    ticket = cmd.get("ticket")
                    if action == "close" and ticket:
                        logger.info("Command received: closing position %s", ticket)
                        await self.wrapper.connection.close_position(ticket)
                    elif action == "cancel" and ticket:
                        logger.info("Command received: canceling order %s", ticket)
                        await self.wrapper.connection.cancel_order(ticket)
                os.remove("commands.json")
            except Exception as e:
                logger.error("Failed to execute command: %s", e)
"""
code = code.replace(step_find, step_replace)

with open("griff_engine_live.py", "w") as f:
    f.write(code)

