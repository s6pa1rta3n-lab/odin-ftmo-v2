with open('/tmp/odin_daemon.py', 'r') as f:
    content = f.read()

content = content.replace("if new_sl != self.sl_price:\n                            \n                    if new_sl:", "if new_sl and new_sl != self.sl_price:")

with open('/tmp/odin_daemon.py', 'w') as f:
    f.write(content)
