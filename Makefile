# Structure-OCR: start / stop / restart backend + frontend dev servers
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
BACKEND := $(ROOT)/backend
FRONTEND := $(ROOT)/frontend
RUN := $(ROOT)/.run
PID_BACKEND := $(RUN)/backend.pid
PID_FRONTEND := $(RUN)/frontend.pid
LOG_BACKEND := $(RUN)/backend.log
LOG_FRONTEND := $(RUN)/frontend.log

ifeq ($(wildcard $(BACKEND)/venv/bin/python3),)
  PYTHON := python3
else
  PYTHON := $(BACKEND)/venv/bin/python3
endif

.DEFAULT_GOAL := help

.PHONY: help install start stop restart status logs

help:
	@echo "Structure-OCR - process control"
	@echo "  make install   - pip install -e '.[ocr]' + npm install"
	@echo "  make start     - backend :8000 + frontend :5173 (background)"
	@echo "  make stop      - stop both"
	@echo "  make restart   - stop then start"
	@echo "  make status    - show PIDs / ports"
	@echo "  make logs      - tail -f both logs (Ctrl+C exits tail only)"

install:
	@mkdir -p $(RUN)
	@echo "-> backend deps ($(PYTHON))"
	cd $(BACKEND) && $(PYTHON) -m pip install -e ".[ocr]"
	@echo "-> frontend deps"
	cd $(FRONTEND) && npm install

start: $(RUN)
	@if [ -f $(PID_BACKEND) ] && kill -0 $$(cat $(PID_BACKEND)) 2>/dev/null; then \
		echo "backend already running (pid $$(cat $(PID_BACKEND))). Use: make restart"; exit 1; \
	fi
	@if [ -f $(PID_FRONTEND) ] && kill -0 $$(cat $(PID_FRONTEND)) 2>/dev/null; then \
		echo "frontend already running (pid $$(cat $(PID_FRONTEND))). Use: make restart"; exit 1; \
	fi
	@echo "-> starting backend http://127.0.0.1:8000"
	cd $(BACKEND) && nohup $(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 >> $(LOG_BACKEND) 2>&1 & echo $$! > $(PID_BACKEND)
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
	@echo "--- backend (8000) ---"
	@if [ -f $(PID_BACKEND) ] && kill -0 $$(cat $(PID_BACKEND)) 2>/dev/null; then \
		echo "pid $$(cat $(PID_BACKEND))  log $(LOG_BACKEND)"; \
	else \
		echo "not running (stale pid file removed)"; \
		rm -f $(PID_BACKEND); \
	fi
	@echo "--- frontend (5173) ---"
	@if [ -f $(PID_FRONTEND) ] && kill -0 $$(cat $(PID_FRONTEND)) 2>/dev/null; then \
		echo "pid $$(cat $(PID_FRONTEND))  log $(LOG_FRONTEND)"; \
	else \
		echo "not running (stale pid file removed)"; \
		rm -f $(PID_FRONTEND); \
	fi

logs:
	@test -d $(RUN) || mkdir -p $(RUN)
	@touch $(LOG_BACKEND) $(LOG_FRONTEND)
	tail -f $(LOG_BACKEND) $(LOG_FRONTEND)
