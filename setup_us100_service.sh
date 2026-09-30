sudo bash -c 'cat << "SVC_EOF" > /etc/systemd/system/griff_engine_us100.service
[Unit]
Description=Griff Trading Engine Live (US100 NY Pullback)
After=network.target

[Service]
Type=simple
User=solveetcoagula
WorkingDirectory=/home/solveetcoagula/odin_ftmo
ExecStart=/usr/bin/python3 /home/solveetcoagula/odin_ftmo/griff_engine_us100.py --account-id a60dfd98-8a34-4c1b-9f2c-b40cdcc2c3bf
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SVC_EOF'
sudo systemctl daemon-reload
sudo systemctl enable griff_engine_us100.service
sudo systemctl start griff_engine_us100.service
sudo systemctl status griff_engine_us100.service --no-pager
