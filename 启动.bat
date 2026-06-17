@echo off
cd /d "%~dp0"
set TF_ENABLE_ONEDNN_OPTS=0
set TF_CPP_MIN_LOG_LEVEL=2
python -m src.main
