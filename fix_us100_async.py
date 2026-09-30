with open('/home/solveetcoagula/odin_ftmo/griff_engine_us100.py', 'r') as f:
    content = f.read()

old_block = """    token = load_metaapi_token(args.config)
    engine = US100Engine(token=token, account_id=args.account_id)
    
    def handle_sigint(sig, frame):
        logger.info("Received termination signal.")
        engine.is_running = False
        import sys
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)
    
    asyncio.run(engine.run_loop())"""

new_block = """    token = load_metaapi_token(args.config)
    
    async def main():
        engine = US100Engine(token=token, account_id=args.account_id)
        
        def handle_sigint(sig, frame):
            logger.info("Received termination signal.")
            engine.is_running = False
            import sys
            sys.exit(0)
            
        signal.signal(signal.SIGINT, handle_sigint)
        signal.signal(signal.SIGTERM, handle_sigint)
        
        await engine.run_loop()

    asyncio.run(main())"""

content = content.replace(old_block, new_block)

with open('/home/solveetcoagula/odin_ftmo/griff_engine_us100.py', 'w') as f:
    f.write(content)
