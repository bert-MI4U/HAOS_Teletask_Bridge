#!/usr/bin/env bash
echo 'installing gmqtt'
pip3 install gmqtt
echo 'Starting Teletask Bridge...'
python3 main.py
