# Structure-OCR: start / stop / restart backend + frontend dev servers
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend
RUN := $(ROOT)/.run
PID_BACKEND := $(RUN)/backend.pid
PID_FRONTEND := $(RUN)/frontend.pid
LOG_BACKEND := $(RUN)/backend.log
LOG_FRONTEND := $(RUN)/frontend.log

# uv manages the venv at backend/.venv
PYTHON := $(BACKEND)/.venv/bin/python3

# ---------------------------------------------------------------------------
# OCR engine config (override via: make start OCR_ENGINE=paddle)
# Default: cross_validate — runs Apple Vision + RapidOCR in parallel and
# compares results block-by-block for near-100% accuracy on Mac.
# Requires: pip install ".[auto]"
# ---------------------------------------------------------------------------
OCR_ENGINE          ?= cross_validate
OCR_CV_PRIMARY      ?= apple_vision
OCR_CV_SECONDARY    ?= rapidocr
OCR_CV_IOU          ?= 0.35
OCR_CV_TEXT         ?= 0.80

# Backend launch env — merged into the nohup command
BACKEND_ENV := STRUCTURE_OCR_ENGINE=$(OCR_ENGINE) \
               STRUCTURE_OCR_CV_PRIMARY=$(OCR_CV_PRIMARY) \
               STRUCTURE_OCR_CV_SECONDARY=$(OCR_CV_SECONDARY) \
               STRUCTURE_OCR_CV_IOU_THRESHOLD=$(OCR_CV_IOU) \
               STRUCTURE_OCR_CV_TEXT_THRESHOLD=$(OCR_CV_TEXT)

.DEFAULT_GOAL := help

.PHONY: help install install-paddle sync start stop restart status logs

help:
	@echo "Structure-OCR - process control  (uv managed)"
	@echo ""
	@echo "  make install        - uv sync --extra apple-vision --extra dev + RapidOCR pip deps + npm install"
	@echo "  make install-paddle - uv sync --extra ocr --extra dev + npm install"
	@echo "  make sync           - uv sync (refresh lock, no extras)"
	@echo "  make start          - backend :8000 + frontend :5173  [cross_validate mode by default]"
	@echo "  make start OCR_ENGINE=paddle       - use PaddleOCR only"
	@echo "  make start OCR_ENGINE=apple_vision - use Apple Vision only"
	@echo "  make start OCR_ENGINE=rapidocr     - use RapidOCR only"
	@echo "  make start OCR_ENGINE=auto         - auto-select fastest available engine"
	@echo "  make stop      - stop both"
	@echo "  make restart   - stop then start"
	@echo "  make status    - show PIDs / ports / active OCR engine"
	@echo "  make logs      - tail -f both logs (Ctrl+C exits tail only)"

install:
	@mkdir -p $(RUN)
	@echo "-> backend core deps via uv (from lock, with dev tools)"
	cd $(BACKEND) && uv sync --frozen --extra apple-vision --extra dev
	@echo "-> backend: rapidocr + onnxruntime + opencv via pip (Tsinghua mirror)"
	cd $(BACKEND) && .venv/bin/pip install \
	  -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple \
	  --timeout 60 \
	  "onnxruntime>=1.18.0,<1.21" "opencv-python-headless" "rapidocr>=1.4.0"
	@echo "-> frontend deps"
	cd $(FRONTEND) && npm install

install-paddle:
	@mkdir -p $(RUN)
	@echo "-> backend deps via uv: PaddleOCR + dev tools"
	cd $(BACKEND) && UV_HTTP_TIMEOUT=120 uv sync --frozen --extra ocr --extra dev
	@echo "-> frontend deps"
	cd $(FRONTEND) && npm install

sync:
	@echo "-> uv sync (from lockfile, no network)"
	cd $(BACKEND) && uv sync --frozen

start: $(RUN)
	@if [ -f $(PID_BACKEND) ] && kill -0 $$(cat $(PID_BACKEND)) 2>/dev/null; then \
		echo "backend already running (pid $$(cat $(PID_BACKEND))). Use: make restart"; exit 1; \
	fi
	@if [ -f $(PID_FRONTEND) ] && kill -0 $$(cat $(PID_FRONTEND)) 2>/dev/null; then \
		echo "frontend already running (pid $$(cat $(PID_FRONTEND))). Use: make restart"; exit 1; \
	fi
	@echo "-> OCR engine: $(OCR_ENGINE)  [primary=$(OCR_CV_PRIMARY)  secondary=$(OCR_CV_SECONDARY)]"
	@echo "-> starting backend http://127.0.0.1:8000"
	cd $(BACKEND) && nohup env $(BACKEND_ENV) $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 >> $(LOG_BACKEND) 2>&1 & echo $$! > $(PID_BACKEND)
	@echo "-> starting frontend http://127.0.0.1:5173"
	cd $(FRONTEND) && nohup npm run dev >> $(LOG_FRONTEND) 2>&1 & echo $$! > $(PID_FRONTEND)
	@sleep 1
	@$(MAKE) --no-print-directory status

$(RUN):
	mkdir -p $(RUN)

stop:
	@echo "-> stopping frontend"
	@if [ -f $(PID_FRONTEND) ]; then \
		pid=$$(cat $(PID_FRONTEND)); \
		if kill -0 $$pid 2>/dev/null; then kill $$pid 2>/dev/null || true; fi; \
		rm -f $(PID_FRONTEND); \
	fi
	@echo "-> stopping backend"
	@if [ -f $(PID_BACKEND) ]; then \
		pid=$$(cat $(PID_BACKEND)); \
		if kill -0 $$pid 2>/dev/null; then kill $$pid 2>/dev/null || true; fi; \
		rm -f $(PID_BACKEND); \
	fi
	@for p in 8000 5173; do \
		for pid in $$(lsof -ti :$$p 2>/dev/null); do kill $$pid 2>/dev/null || true; done; \
	done

restart: stop
	@sleep 1
	@$(MAKE) --no-print-directory start

status:
	@echo "--- OCR engine ---"
	@echo "  engine=$(OCR_ENGINE)  primary=$(OCR_CV_PRIMARY)  secondary=$(OCR_CV_SECONDARY)"
	@echo "  iou_threshold=$(OCR_CV_IOU)  text_threshold=$(OCR_CV_TEXT)"
	@echo "--- backend (8000) ---"
	@if [ -f $(PID_BACKEND) ] && kill -0 $$(cat $(PID_BACKEND)) 2>/dev/null; then \
		echo "  pid $$(cat $(PID_BACKEND))  log $(LOG_BACKEND)"; \
	else \
		echo "  not running (stale pid file removed)"; \
		rm -f $(PID_BACKEND); \
	fi
	@echo "--- frontend (5173) ---"
	@if [ -f $(PID_FRONTEND) ] && kill -0 $$(cat $(PID_FRONTEND)) 2>/dev/null; then \
		echo "  pid $$(cat $(PID_FRONTEND))  log $(LOG_FRONTEND)"; \
	else \
		echo "  not running (stale pid file removed)"; \
		rm -f $(PID_FRONTEND); \
	fi

logs:
	@test -d $(RUN) || mkdir -p $(RUN)
	@touch $(LOG_BACKEND) $(LOG_FRONTEND)
	tail -f $(LOG_BACKEND) $(LOG_FRONTEND)
