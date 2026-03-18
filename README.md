# 🔴 mini-redis

> Redis의 핵심 구조를 Python으로 직접 구현한 교육용 인메모리 데이터베이스

기존 Redis 클라이언트(`redis-cli`, `redis-py`)가 **그대로 접속**할 수 있는 RESP 호환 서버입니다.  
공식 Redis · mini-redis · MongoDB를 같은 시나리오로 벤치마크해 성능 차이를 수치로 비교할 수 있습니다.

---

## 📋 목차

- [프로젝트 구조](#-프로젝트-구조)
- [아키텍처](#-아키텍처)
- [지원 명령어](#-지원-명령어)
- [자료구조 구현](#-자료구조-구현)
- [핵심 기능](#-핵심-기능)
- [빠른 시작](#-빠른-시작)
- [벤치마크](#-벤치마크)
- [환경 변수](#-환경-변수)
- [테스트](#-테스트)

---

## 📁 프로젝트 구조

```
mini-redis/
├── server.py                    # TCP 서버 진입점 (asyncio + uvloop)
│
├── protocol/                    # RESP 프로토콜 계층
│   ├── parser.py                #   요청 파싱 (Array + Bulk String)
│   └── encoder.py               #   응답 인코딩 (Simple String, Error, Integer, Bulk, Array)
│
├── commands/                    # 명령 핸들러 계층
│   ├── dispatcher.py            #   명령 라우팅 테이블
│   ├── string_cmds.py           #   String 명령 (GET, SET, INCR, MSET ...)
│   ├── hash_cmds.py             #   Hash 명령 (HSET, HGET, HGETALL ...)
│   ├── list_cmds.py             #   List 명령 (LPUSH, RPUSH, LPOP ...)
│   ├── set_cmds.py              #   Set 명령 (SADD, SREM, SMEMBERS ...)
│   ├── zset_cmds.py             #   Sorted Set 명령 (ZADD, ZRANGE ...)
│   └── generic_cmds.py          #   범용 명령 (PING, DEL, EXPIRE, TTL ...)
│
├── store/                       # 저장 계층
│   ├── redis_object.py          #   RedisObject 래퍼 (type + encoding + value)
│   ├── datastore.py             #   메인 키스페이스 + 모든 자료형 메서드
│   ├── hash_table.py            #   커스텀 해시 테이블 (MurmurHash3, Chaining, Open Addressing)
│   ├── skiplist.py              #   스킵리스트 기반 Sorted Set
│   ├── expiry.py                #   TTL 관리 (Lazy + Active Expiry)
│   ├── persistence.py           #   영속성 (AOF + RDB)
│   ├── memory.py                #   메모리 사용량 추정 (deep_getsizeof)
│   └── errors.py                #   MemoryLimitError
│
├── benchmark/                   # 벤치마크 봇
│   ├── benchmark.py             #   7개 시나리오 테스트 스크립트
│   ├── Dockerfile               #   벤치마크 컨테이너
│   └── requirements.txt         #   redis-py, pymongo
│
├── tests/                       # 테스트 코드
├── docs/                        # 발표 자료
├── Dockerfile                   # mini-redis 컨테이너
├── docker-compose.yml           # 4개 서비스 오케스트레이션
├── Makefile                     # 원커맨드 실행
└── requirements.txt             # Python 의존성
```

---

## 🏗 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  Client (redis-cli / redis-py / ...)                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ TCP (RESP)
┌────────────────────────▼────────────────────────────────────────┐
│  server.py — asyncio + uvloop  (단일 이벤트 루프)                │
│                                                                  │
│  ┌──────────┐   ┌─────────────┐   ┌──────────────────────────┐  │
│  │ parser.py│──>│dispatcher.py│──>│ *_cmds.py 핸들러          │  │
│  └──────────┘   └─────────────┘   └────────────┬─────────────┘  │
│  ┌──────────┐                                   │                │
│  │encoder.py│<──────────────────────────────────┘                │
│  └──────────┘                                                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                    store 계층                               │  │
│  │  DataStore ← RedisObject(type, encoding, value)            │  │
│  │  ├── String  : bytes  (ENC_RAW / ENC_INT)                  │  │
│  │  ├── Hash    : compact list → ChainedHashTable             │  │
│  │  ├── List    : collections.deque                           │  │
│  │  ├── Set     : Python set                                  │  │
│  │  └── ZSet    : dict + SkipList                             │  │
│  │                                                             │  │
│  │  ExpiryManager      — Lazy + Active Expiry                 │  │
│  │  PersistenceManager — AOF (append) + RDB (snapshot)        │  │
│  │  MemoryTracker      — maxmemory + eviction policy          │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**요청 처리 흐름:**

1. 클라이언트 TCP 연결 → `handle_client()` 코루틴 생성
2. 바이트 스트림을 버퍼에 누적 → `parser.parse()`로 RESP 배열 파싱
3. `dispatcher.dispatch()`가 명령 이름으로 핸들러 함수 탐색
4. 핸들러가 `DataStore`의 메서드를 호출해 데이터 조작
5. 결과를 `encoder.encode()`로 RESP 응답 바이트로 변환
6. `writer.write()` → `writer.drain()`으로 클라이언트에 응답

---

## 📌 지원 명령어

### String (9개)

| 명령 | 설명 | 구현 위치 |
|------|------|-----------|
| `GET key` | 키의 문자열 값 조회 | `string_cmds.py` |
| `SET key value [EX s] [PX ms]` | 문자열 저장 + 선택적 TTL | `string_cmds.py` |
| `MGET key [key ...]` | 여러 키 동시 조회 | `string_cmds.py` |
| `MSET key value [key value ...]` | 여러 키 동시 저장 (롤백 지원) | `string_cmds.py` |
| `INCR key` | 값을 정수로 해석하여 +1 | `string_cmds.py` |
| `DECR key` | 값을 정수로 해석하여 -1 | `string_cmds.py` |
| `INCRBY key increment` | 정수 값을 지정량만큼 증가 | `string_cmds.py` |
| `APPEND key value` | 기존 값 뒤에 이어 붙이기 | `string_cmds.py` |
| `STRLEN key` | 문자열 바이트 길이 반환 | `string_cmds.py` |

**구현 포인트:**
- 내부 저장은 `bytes` 기반. 정수 변환 가능 여부에 따라 `ENC_INT` / `ENC_RAW` 인코딩 구분
- `MSET`은 도중 실패 시 모든 키를 이전 상태로 **롤백** (스냅샷 기반)
- `INCR/DECR`은 `INCRBY`에 위임하는 delegation 패턴

### Hash (10개)

| 명령 | 설명 |
|------|------|
| `HSET key field value [field value ...]` | 필드 설정 (새 필드 수 반환) |
| `HGET key field` | 단일 필드 조회 |
| `HMSET key field value [...]` | 여러 필드 설정 |
| `HMGET key field [field ...]` | 여러 필드 조회 |
| `HGETALL key` | 모든 field-value 쌍 반환 |
| `HDEL key field [field ...]` | 필드 삭제 |
| `HEXISTS key field` | 필드 존재 여부 |
| `HKEYS key` | 모든 필드명 |
| `HVALS key` | 모든 값 |
| `HLEN key` | 필드 수 |

**구현 포인트:**
- 작은 해시 → `compact list` (튜플 리스트, O(n) 탐색이지만 메모리 절약)
- 필드 32개 초과 또는 값 64바이트 초과 시 → `ChainedHashTable`로 자동 승격
- 해시 함수: **MurmurHash3 x86 32-bit** 직접 구현 (seed=0 고정 정책)
- `OpenAddressHashTable` (Double Hashing + Tombstone)도 별도 구현하여 비교 가능

### List (8개)

| 명령 | 설명 |
|------|------|
| `LPUSH key value [value ...]` | 왼쪽에 추가 |
| `RPUSH key value [value ...]` | 오른쪽에 추가 |
| `LPOP key` | 왼쪽에서 꺼내기 |
| `RPOP key` | 오른쪽에서 꺼내기 |
| `LRANGE key start stop` | 범위 조회 (음수 인덱스 지원) |
| `LLEN key` | 리스트 길이 |
| `LINDEX key index` | 특정 인덱스 조회 |
| `LSET key index value` | 특정 인덱스 값 변경 |

**구현 포인트:** `collections.deque` 기반으로 양끝 push/pop O(1)

### Set (8개)

| 명령 | 설명 |
|------|------|
| `SADD key member [member ...]` | 멤버 추가 |
| `SREM key member [member ...]` | 멤버 제거 |
| `SMEMBERS key` | 전체 멤버 (정렬된 결과) |
| `SISMEMBER key member` | 멤버 존재 여부 |
| `SCARD key` | 멤버 수 |
| `SINTER key [key ...]` | 교집합 |
| `SUNION key [key ...]` | 합집합 |
| `SDIFF key [key ...]` | 차집합 |

**구현 포인트:** Python `set` 기반, 집합 연산은 built-in `&`, `|`, `-` 연산자 활용

### Sorted Set (8개)

| 명령 | 설명 |
|------|------|
| `ZADD key score member [score member ...]` | 멤버 추가/업데이트 |
| `ZREM key member [member ...]` | 멤버 제거 |
| `ZSCORE key member` | 점수 조회 |
| `ZRANK key member` | 오름차순 순위 |
| `ZRANGE key start stop [WITHSCORES]` | 오름차순 범위 조회 |
| `ZREVRANGE key start stop [WITHSCORES]` | 내림차순 범위 조회 |
| `ZCARD key` | 멤버 수 |
| `ZRANGEBYSCORE key min max` | 점수 범위 조회 |

**구현 포인트:**
- **SkipList** 직접 구현 (최대 16레벨, P=0.25)
- `dict(member → score)` + `SkipList(score, member)` 이중 인덱스
- `dict`로 O(1) 점수 조회, SkipList로 O(log n) 범위/순위 조회

### Generic (10개)

| 명령 | 설명 |
|------|------|
| `PING [message]` | 연결 확인 |
| `DEL key [key ...]` | 키 삭제 |
| `EXISTS key [key ...]` | 키 존재 확인 |
| `EXPIRE key seconds` | TTL 설정 |
| `TTL key` | 남은 TTL 조회 |
| `PERSIST key` | TTL 제거 |
| `PEXPIREAT key ms-timestamp` | 절대 시각 TTL (영속성 복구용) |
| `TYPE key` | 키의 자료형 반환 |
| `KEYS pattern` | 패턴 매칭 키 목록 |
| `FLUSHALL` | 전체 데이터 삭제 |

---

## 🔧 자료구조 구현

### RedisObject — 통합 값 래퍼

모든 키는 `RedisObject(type, encoding, value)`로 감싸져 저장됩니다.

```python
class RedisObject:
    __slots__ = ("type", "encoding", "value", "refcount")
```

| type | encoding | Python 자료형 |
|------|----------|--------------|
| `string` | `raw` / `int` | `bytes` |
| `hash` | `dict` / `hashtable` | `dict` → `Hash` (compact → ChainedHashTable) |
| `list` | `deque` | `collections.deque` |
| `set` | `hashtable` | `set` |
| `zset` | `skiplist` | `ZSet` (dict + SkipList) |

### Hash Table — MurmurHash3 + 이중 구현

`hash_table.py`에 두 가지 해시 테이블을 구현했습니다:

1. **ChainedHashTable** (Separate Chaining) — 런타임 기본값
   - 버킷 배열 + 연결 리스트
   - Load factor > 0.7 → capacity × 2 확장
   - Load factor < 0.2 → capacity ÷ 2 축소

2. **OpenAddressHashTable** (Double Hashing) — 비교/학습용
   - Tombstone 기반 삭제
   - Double hashing: `step = (hash >> 16) ^ (hash << 1) | 1`
   - Power-of-two capacity로 모듈러 연산 최적화

### SkipList — O(log n) 순위 조회

```
Level 3: [H] ──────────────────────────────> [D] ──> nil
Level 2: [H] ──────────> [B] ──────────────> [D] ──> nil
Level 1: [H] ──> [A] ──> [B] ──> [C] ──────> [D] ──> nil
Level 0: [H] ──> [A] ──> [B] ──> [C] ──> [D]──>nil
```

- 최대 16레벨, 승격 확률 P=0.25
- `span` 배열로 rank 계산 O(log n)
- insert, delete, rank 모두 O(log n)

---

## ⚡ 핵심 기능

### 서버 — 단일 이벤트 루프 (asyncio + uvloop)

Redis 원본과 동일한 **단일 스레드 + I/O 멀티플렉싱** 구조:
- `uvloop`으로 기본 asyncio 대비 2~4배 성능 향상
- 연결별 코루틴이 `await`에서 양보 → 이벤트 루프가 다른 연결 처리

**클라이언트 보호 장치:**

| 보호 항목 | 기본값 | 설명 |
|----------|--------|------|
| Idle timeout | 30s | 유휴 연결 자동 종료 |
| Write drain timeout | 5s | 느린 클라이언트 차단 |
| Max input buffer | 1MB | 과도한 요청 차단 |
| Max output buffer | 256KB | 메모리 보호 |
| Max commands/tick | 128 | 이벤트 루프 독점 방지 |

### TTL 관리 — Lazy + Active 이중 전략

- **Lazy Expiry:** `GET`, `EXISTS` 등 읽기 시 만료 확인 → 즉시 삭제
- **Active Expiry:** 백그라운드 루프가 100ms마다 만료 키 20개 샘플링
  - 샘플에서 만료 비율이 25% 이상이면 같은 주기에 추가 패스 (최대 4회)
  - 전체 스캔 없이 효율적으로 만료 키 정리

### 영속성 — AOF + RDB

| 항목 | AOF | RDB |
|------|-----|-----|
| 기록 방식 | 쓰기 명령을 RESP 형태로 append | 전체 상태를 스냅샷으로 저장 |
| fsync | `always` / `everysec` / `no` | 저장 시점에 한 번 |
| 복구 | 명령 재실행 (replay) | 스냅샷 로드 |
| 우선순위 | ✅ AOF 우선 | AOF 없을 때 RDB |

### 메모리 관리 — maxmemory + Eviction

`deep_getsizeof()`로 Python 객체 크기를 재귀 계측:

| eviction 정책 | 설명 |
|---------------|------|
| `noeviction` | 한도 초과 시 쓰기 거부 (기본값) |
| `allkeys-random` | 무작위 키 삭제 |
| `allkeys-lru` | 가장 오래 접근하지 않은 키 삭제 |
| `volatile-ttl` | TTL이 설정된 키 중 만료 임박한 키 우선 삭제 |

---

## 🚀 빠른 시작

### 로컬 실행

```bash
# 의존성 설치
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 서버 실행
python server.py --host 0.0.0.0 --port 6379

# 다른 터미널에서 접속
./redis-cli -p 6379
> PING
PONG
> SET hello world
OK
> GET hello
"world"
```

### Docker + 벤치마크 (원커맨드)

```bash
make run
```

이 명령 하나로:
1. ✅ OS 감지 (Mac / Windows)
2. ✅ Python venv 생성 + 패키지 설치
3. ✅ 기존 컨테이너 / 포트 정리
4. ✅ Redis + mini-redis + MongoDB + 벤치마크 봇 빌드 & 실행

```bash
make help     # 사용 가능한 명령어 안내
make down     # 컨테이너 종료
make bench    # 벤치마크만 재실행
make clean    # 전체 정리
```

---

## 📊 벤치마크

### 7개 비교 시나리오

| # | 시나리오 | 사용 명령 | 측정 포인트 |
|---|---------|----------|------------|
| 1 | **KV Cache** | GET / SET | 기본 읽기/쓰기 레이턴시 |
| 2 | **Session Store** | HSET / HGETALL | Hash 연산 성능 |
| 3 | **Rate Limiting** | INCR + EXPIRE | 원자적 카운터 속도 |
| 4 | **Message Queue** | LPUSH / RPOP | Producer/Consumer 처리량 |
| 5 | **Leaderboard** | ZADD / ZREVRANGE | Sorted Set 순위 성능 |
| 6 | **Cache vs DB** | Redis + MongoDB | Cache Hit / Miss / 직접 조회 비교 |
| 7 | **Pipeline** | 배치 SET | 개별 요청 vs 파이프라인 RTT 절감 |

### 측정 지표

| 지표 | 설명 |
|------|------|
| Mean (ms) | 평균 레이턴시 |
| P50 (ms) | 중앙값 |
| P95 (ms) | 상위 5% 느린 요청 |
| P99 (ms) | 상위 1% 가장 느린 요청 |
| Throughput (ops/sec) | 초당 처리량 |
| Error rate (%) | 에러/미구현 비율 |

### 결과 파일

벤치마크 실행 후 `benchmark/results/`에 저장:
- `report.json` — 전체 결과 (프로그래밍용)
- `report.csv` — 표 형태 (스프레드시트 분석용)

---

## ⚙ 환경 변수

`.env` 파일 또는 `docker-compose.yml`의 `environment`에서 설정:

### 서버 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MINI_REDIS_HOST` | `127.0.0.1` | 바인드 주소 |
| `MINI_REDIS_PORT` | `6379` | 리스닝 포트 |
| `MINI_REDIS_MAXMEMORY` | `0` (무제한) | 최대 메모리 (예: `128mb`) |
| `MINI_REDIS_MAXMEMORY_POLICY` | `noeviction` | eviction 정책 |
| `MINI_REDIS_APPENDONLY` | `no` | AOF 활성화 |
| `MINI_REDIS_RDB_ENABLED` | `no` | RDB 활성화 |
| `MINI_REDIS_LOG_LEVEL` | `INFO` | 로그 레벨 |

### 벤치마크 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BENCH_ITERATIONS` | `1000` | 시나리오별 반복 횟수 |
| `BENCH_WARMUP` | `100` | 워밍업 반복 횟수 |
| `BENCH_PIPELINE_BATCH` | `100` | 파이프라인 배치 크기 |
| `BENCH_VALUE_SIZE` | `32` | 테스트 값 크기 (바이트) |
| `BENCH_RANDOM_SEED` | (없음) | 재현 가능 테스트용 시드 |

---

## 🧪 테스트

```bash
# 전체 테스트
pytest

# 특정 테스트
pytest tests/test_string_cmds.py -v
pytest tests/test_hash_table.py -v
pytest tests/test_server_integration.py -v
```

---

## 📄 라이선스

교육 목적 프로젝트입니다.
