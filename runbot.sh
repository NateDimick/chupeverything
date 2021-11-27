#!/bin/bash
cd /home/ubuntu/Projects/chupeverything
date > last_run.txt
source chupbot/bin/activate
python3 chupbot.py
deactivate
