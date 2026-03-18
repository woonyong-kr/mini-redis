# ==============================================================================
#  mini-redis Makefile
#  Mac(zsh) / Windows(Git Bash / WSL) 동일 명령어 지원
#
#  사용법:
#    make run       ← 전부 자동 실행 (venv 설정 + Docker 정리 + 서비스 시작)
#    make down      ← 실행 중인 컨테이너 전부 종료
#    make logs      ← 전체 로그 스트리밍
#    make ps        ← 컨테이너 상태 확인
#    make clean     ← venv + 결과 파일 모두 삭제
#    make help      ← 이 도움말 출력
# ==============================================================================

-include .env
export

# ── OS 감지 ──────────────────────────────────────────────────────────────────
ifeq ($(OS),Windows_NT)
    DETECTED_OS  := Windows
    PYTHON       := python
    VENV_BIN     := venv\Scripts
    VENV_PYTHON  := venv\Scripts\python.exe
    VENV_PIP     := venv\Scripts\pip.exe
    RM_VENV      := if exist venv rmdir /S /Q venv
    RM_RESULTS   := if exist benchmark\results rmdir /S /Q benchmark\results
    MKDIR_RESULTS:= if not exist benchmark\results mkdir benchmark\results
    DEVNULL      := NUL
else
    DETECTED_OS  := $(shell uname -s)
    PYTHON       := python3
    VENV_BIN     := venv/bin
    VENV_PYTHON  := venv/bin/python
    VENV_PIP     := venv/bin/pip
    RM_VENV      := rm -rf venv
    RM_RESULTS   := rm -rf benchmark/results/*
    MKDIR_RESULTS:= mkdir -p benchmark/results
    DEVNULL      := /dev/null
endif

COMPOSE         := docker compose
PROJECT_COMPOSE := docker-compose.yml
REDIS_OFFICIAL_HOST_PORT ?= 6379
MINI_REDIS_HOST_PORT    ?= 6380
MONGO_HOST_PORT         ?= 27017

.PHONY: run bench down setup-venv install clean logs ps help
.DEFAULT_GOAL  := help

# ══════════════════════════════════════════════════════════════════════════════
#  run ← 모든 것을 한 번에 실행하는 핵심 명령어
#
#  실행 순서:
#    1. OS 출력
#    2. Python venv 확인 / 없으면 생성 + 패키지 설치
#    3. 실행 중인 컨테이너 전부 내리기
#    4. results 디렉토리 준비
#    5. 3개 서비스(Redis, mini-redis, MongoDB) + 벤치마크 봇 빌드 & 실행
# ══════════════════════════════════════════════════════════════════════════════
run: setup-venv down _results-dir
	@echo ""
	@echo "══════════════════════════════════════════"
	@echo "  ▶  Docker 빌드 & 전체 서비스 실행"
	@echo "══════════════════════════════════════════"
	$(COMPOSE) -f $(PROJECT_COMPOSE) up --build --abort-on-container-exit --exit-code-from benchmark
	@echo ""
	@echo "✔  벤치마크 완료 — 결과 확인:"
	@echo "   benchmark/results/report.json"
	@echo "   benchmark/results/report.csv"

# ── 벤치마크만 재실행 (이미 서비스가 올라와 있을 때) ────────────────────────
bench:
	@echo "▶ 벤치마크 봇만 재실행..."
	$(COMPOSE) -f $(PROJECT_COMPOSE) run --rm benchmark

# ══════════════════════════════════════════════════════════════════════════════
#  setup-venv — Python 가상환경 확인 / 생성 / 패키지 설치
# ══════════════════════════════════════════════════════════════════════════════
setup-venv:
	@echo ""
	@echo "── [1/4] 환경 감지 ──────────────────────────"
	@echo "   OS     : $(DETECTED_OS)"
	@echo "   Python : $(shell $(PYTHON) --version 2>&1)"
	@echo ""
	@echo "── [2/4] Python 가상환경 확인 ───────────────"
	@if [ ! -f "$(VENV_PYTHON)" ]; then \
		echo "   venv 없음 → 생성 중..."; \
		$(PYTHON) -m venv venv; \
		echo "   ✔ venv 생성 완료"; \
	else \
		echo "   ✔ venv 이미 존재 ($(VENV_PYTHON))"; \
	fi
	@echo ""
	@echo "── [3/4] 패키지 설치 (venv) ─────────────────"
	$(VENV_PIP) install --quiet --upgrade pip
	$(VENV_PIP) install --quiet -r requirements.txt
	@echo "   ✔ 패키지 설치 완료"

# ── 패키지만 재설치 ──────────────────────────────────────────────────────────
install: setup-venv

# ══════════════════════════════════════════════════════════════════════════════
#  down — 실행 중인 컨테이너 전부 종료 + 포트 강제 해제
#
#  1단계: 현재 프로젝트 docker compose down
#  2단계: 프로젝트 외 컨테이너 중 포트 6379/6380/27017 점유 중인 것도 강제 종료
#  3단계: (Mac) 로컬 프로세스 중 해당 포트 사용 중인 것 kill
# ══════════════════════════════════════════════════════════════════════════════
down:
	@echo ""
	@echo "── [4/4] 기존 컨테이너 / 포트 정리 ──────────"
	@$(COMPOSE) -f $(PROJECT_COMPOSE) down --remove-orphans 2>$(DEVNULL) || true
ifeq ($(DETECTED_OS),Windows)
	@echo "   Docker 포트 점유 컨테이너 정리 (Windows)..."
	@for /f %%i in ('docker ps -q --filter publish=$(REDIS_OFFICIAL_HOST_PORT)') do docker stop %%i 2>NUL || true
	@for /f %%i in ('docker ps -q --filter publish=$(MINI_REDIS_HOST_PORT)') do docker stop %%i 2>NUL || true
	@for /f %%i in ('docker ps -q --filter publish=$(MONGO_HOST_PORT)') do docker stop %%i 2>NUL || true
else
	@echo "   Docker 포트 점유 컨테이너 정리 (Mac/Linux)..."
	@docker ps -q --filter publish=$(REDIS_OFFICIAL_HOST_PORT) | xargs -r docker stop 2>$(DEVNULL) || true
	@docker ps -q --filter publish=$(MINI_REDIS_HOST_PORT)    | xargs -r docker stop 2>$(DEVNULL) || true
	@docker ps -q --filter publish=$(MONGO_HOST_PORT)         | xargs -r docker stop 2>$(DEVNULL) || true
	@echo "   로컬 프로세스 포트 정리..."
	@lsof -ti:$(REDIS_OFFICIAL_HOST_PORT) | xargs -r kill -9 2>$(DEVNULL) || true
	@lsof -ti:$(MINI_REDIS_HOST_PORT)    | xargs -r kill -9 2>$(DEVNULL) || true
	@lsof -ti:$(MONGO_HOST_PORT)         | xargs -r kill -9 2>$(DEVNULL) || true
endif
	@echo "   ✔ 포트 정리 완료 ($(REDIS_OFFICIAL_HOST_PORT) / $(MINI_REDIS_HOST_PORT) / $(MONGO_HOST_PORT))"

# ── results 디렉토리 보장 ────────────────────────────────────────────────────
_results-dir:
	@$(MKDIR_RESULTS)

# ══════════════════════════════════════════════════════════════════════════════
#  clean — venv / 결과 파일 / Docker 이미지 전부 삭제
# ══════════════════════════════════════════════════════════════════════════════
clean: down
	@echo "▶ 정리 중..."
	$(RM_VENV)
	$(RM_RESULTS)
	$(COMPOSE) -f $(PROJECT_COMPOSE) down --rmi local --volumes 2>$(DEVNULL) || true
	@echo "✔ 완료"

# ── 유틸리티 ─────────────────────────────────────────────────────────────────

logs:
	$(COMPOSE) -f $(PROJECT_COMPOSE) logs -f

ps:
	$(COMPOSE) -f $(PROJECT_COMPOSE) ps

# ══════════════════════════════════════════════════════════════════════════════
#  help
# ══════════════════════════════════════════════════════════════════════════════
help:
	@echo ""
	@echo "  mini-redis Benchmark — 사용 가능한 명령어"
	@echo "  ─────────────────────────────────────────"
	@echo "  make run     전부 자동: venv → Docker 정리 → 서비스 기동 → 벤치마크"
	@echo "  make bench   서비스가 떠 있을 때 벤치마크만 재실행"
	@echo "  make down    실행 중인 컨테이너 전부 종료"
	@echo "  make logs    전체 로그 스트리밍"
	@echo "  make ps      컨테이너 상태 확인"
	@echo "  make clean   venv + 결과 파일 + Docker 이미지 전부 삭제"
	@echo "  make help    이 도움말 출력"
	@echo ""
	@echo "  감지된 OS : $(DETECTED_OS)"
	@echo ""
