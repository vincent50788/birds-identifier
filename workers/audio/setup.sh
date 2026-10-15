#!/usr/bin/env bash
# Bootstrap an Ubuntu EC2 instance for the audio worker.
set -e
sudo apt update -y
sudo apt install -y python3-pip python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
