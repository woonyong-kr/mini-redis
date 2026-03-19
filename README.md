# mini-redis

Redis의 핵심 구조를 Python으로 직접 구현한 인메모리 데이터베이스입니다.

기존 Redis 클라이언트(`redis-cli`, `redis-py` 등)가 수정 없이 그대로 접속할 수 있도록 RESP(Redis Serialization Protocol) 프로토콜을 직접 구현했습니다. 공식 Redis, mini-redis, MongoDB를 같은 환경에서 실행하여 성능 차이를 수치로 비교할 수 있는 벤치마크 환경을 함께 제공합니다.

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [주요 기능](#주요-기능)
- [프로젝트 구조](#프로젝트-구조)
- [아키텍처](#아키텍처)
- [요구 사항](#요구-사항)
- [설치 및 실행](#설치-및-실행)
  - [로컬 실행](#로컬-실행)
  - [Docker 단독 실행 (데모)](#docker-단독-실행-데모)
  - [Docker 벤치마크 실행](#docker-벤치마크-실행)
- [Make 명령어 정리](#make-명령어-정리)
- [지원 명령어](#지원-명령어)
  - [Generic 명령어](#generic-명령어)
  - [String 명령어](#string-명령어)
  - [Hash 명령어](#hash-명령어)
  - [List 명령어](#list-명령어)
  - [Set 명령어](#set-명령어)
  - [Sorted Set 명령어](#sorted-set-명령어)
- [자료구조 설계](#자료구조-설계)
- [서버 설계](#서버-설계)
- [TTL 관리](#ttl-관리)
- [영속성](#영속성)
- [메모리 제한과 eviction](#메모리-제한과-eviction)
- [벤치마크](#벤치마크)
- [환경 변수](#환경-변수)
- [테스트](#테스트)
- [문서](#문서)
- [현재 범위 밖인 기능](#현재-범위-밖인-기능)
- [라이선스](#라이선스)

---

## 프로젝트 개요

이 프로젝트는 Redis를 단순히 사용하는 것이 아니라, 핵심 동작 원리를 코드 수준에서 직접 구현하고 이해하는 데 목적을 두고 있습니다.

구현 범위:

- RESP 프로토콜 기반 클라이언트-서버 통신
- asyncio + uvloop 기반 단일 이벤트 루프 TCP 서버
- 5가지 Redis 자료구조 (String, Hash, List, Set, Sorted Set)
- MurmurHash3 해시 함수, Hash Table 2종 (Chaining, Open Addressing), SkipList 직접 구현
- Lazy + Active 이중 TTL 만료 전략
- AOF / RDB 영속성
- maxmemory 제한 및 eviction 정책
- 느린 클라이언트 보호 메커니즘
- 공식 Redis / MongoDB 대비 7개 시나리오 벤치마크

---

## 주요 기능

- 53개 Redis 명령어 지원
- 기존 Redis 클라이언트 호환 (redis-cli, redis-py 등)
- 커스텀 자료구조 직접 구현 (MurmurHash3, ChainedHashTable, OpenAddressHashTable, SkipList)
- TTL 만료: Lazy expiry + Sampled active expiry
- 영속성: AOF (Append Only File) + RDB (Snapshot)
- 메모리 제한: noeviction, allkeys-random, allkeys-lru, volatile-ttl
- 느린 클라이언트 보호: idle timeout, write drain timeout, 버퍼 상한, tick당 명령 수 제한
- Docker 기반 비교 벤치마크 환경 (Redis / mini-redis / MongoDB)
- Mac / Linux / Windows(Git Bash) 동일 명령어 지원 Makefile

---

## 프로젝트 구조

```
mini-redis/
├── server.py                     # TCP 서버 진입점 (asyncio + uvloop)
├── protocol/
│   ├── parser.py                 # RESP 요청 파싱 (Array + Bulk String)
│   └── encoder.py                # RESP 응답 인코딩 (Simple String, Error, Integer, Bulk, Array)
├── commands/
│   ├── dispatcher.py             # 명령 라우팅 테이블
│   ├── string_cmds.py            # GET, SET, INCR, MSET, APPEND, STRLEN ...
│   ├── hash_cmds.py              # HSET, HGET, HGETALL, HDEL, HEXISTS ...
│   ├── list_cmds.py              # LPUSH, RPUSH, LPOP, RPOP, LRANGE ...
│   ├── set_cmds.py               # SADD, SREM, SMEMBERS, SINTER, SUNION ...
│   ├── zset_cmds.py              # ZADD, ZREM, ZSCORE, ZRANGE, ZREVRANGE ...
│   └── generic_cmds.py           # PING, DEL, EXISTS, EXPIRE, TTL, TYPE, KEYS, FLUSHALL ...
├── store/
│   ├── redis_object.py           # RedisObject 래퍼 (type + encoding + value)
│   ├── datastore.py              # 메인 키스페이스 + 모든 자료형 메서드
│   ├── hash_table.py             # MurmurHash3, ChainedHashTable, OpenAddressHashTable
│   ├── skiplist.py               # SkipList + ZSet 구현
│   ├── expiry.py                 # TTL 관리 (Lazy + Active Expiry)
│   ├── persistence.py            # AOF + RDB 영속성
│   ├── memory.py                 # 메모리 사용량 계측 (deep_getsizeof)
│   └── errors.py                 # MemoryLimitError
├── benchmark/
│   ├── benchmark.py              # 7개 시나리오 벤치마크 스크립트
│   ├── Dockerfile                # 벤치마크 컨테이너
│   └── requirements.txt          # redis, pymongo
├── tests/                        # pytest 테스트
├── docs/                         # 발표 자료 / 치트시트 / CLI 시나리오
├── Dockerfile                    # mini-redis 컨테이너
├── docker-compose.yml            # 벤치마크 4개 서비스 (Redis, mini-redis, MongoDB, benchmark)
├── docker-compose.dev.yml        # 데모용 단독 실행
├── Makefile                      # 원커맨드 실행 (Mac / Linux / Windows 지원)
├── .env.example                  # 환경 변수 예시
└── requirements.txt              # Python 의존성 (uvloop, pytest 등)
```

---

## 아키텍처

```
Client (redis-cli / redis-py)
        |
        | TCP (RESP 프로토콜)
        v
+----- server.py (asyncio + uvloop, 단일 이벤트 루프) -----+
|                                                           |
|  parser.py -> dispatcher.py -> *_cmds.py 핸들러           |
|                                       |                   |
|                               DataStore (store 계층)      |
|                                  |          |             |
|                           ExpiryManager  PersistenceManager|
|                                       |                   |
|  encoder.py <-------------------------+                   |
|       |                                                   |
+-------+---------------------------------------------------+
        |
        v
    Client에 응답
```

요청 처리 순서:

1. 클라이언트가 TCP로 접속하면 `handle_client()` 코루틴이 생성됩니다.
2. 바이트 스트림을 버퍼에 누적하고 `parser.parse()`로 RESP 배열을 추출합니다.
3. `dispatcher.dispatch()`가 명령 이름(예: `SET`)으로 핸들러 함수를 찾습니다.
4. 핸들러가 `DataStore`의 메서드를 호출하여 데이터를 읽거나 수정합니다.
5. `PersistenceManager`가 쓰기 명령을 AOF에 기록합니다.
6. 결과를 `encoder.encode()`로 RESP 바이트로 변환하여 클라이언트에 반환합니다.

---

## 요구 사항

- Python 3.10 이상
- Docker (벤치마크 또는 컨테이너 실행 시)
- Docker Compose v2
- Make (Makefile 사용 시)

---

## 설치 및 실행

### 로컬 실행

Python 가상환경을 생성하고 서버를 직접 실행합니다.

```bash
git clone <repository-url> mini-redis
cd mini-redis

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python3 server.py --host 127.0.0.1 --port 6379
```

다른 터미널에서 접속합니다.

```bash
# 프로젝트에 포함된 redis-cli 사용
./redis-cli -p 6379

# 또는 시스템에 설치된 redis-cli 사용
redis-cli -p 6379
```

접속 확인:

```
127.0.0.1:6379> PING
PONG
127.0.0.1:6379> SET hello world
OK
127.0.0.1:6379> GET hello
"world"
```

AOF/RDB 영속성을 활성화하려면 환경 변수를 설정합니다.

```bash
MINI_REDIS_APPENDONLY=yes \
MINI_REDIS_RDB_ENABLED=yes \
MINI_REDIS_RDB_SAVE_INTERVAL_SECONDS=30 \
python3 server.py --host 127.0.0.1 --port 6379
```

### Docker 단독 실행 (데모)

mini-redis만 단독으로 Docker에서 실행합니다. 벤치마크 봇 없이 직접 CLI로 명령어를 테스트할 수 있습니다.

```bash
# 서버 실행 (백그라운드)
make dev

# redis-cli 접속
make cli

# 종료
make dev-down
```

`make cli`는 Docker 네트워크를 통해 컨테이너 내부 6379 포트에 직접 접속합니다.

### Docker 벤치마크 실행

공식 Redis, mini-redis, MongoDB, 벤치마크 봇을 한 번에 실행합니다.

```bash
# 전체 벤치마크 (약 5분 이상)
make run

# 발표용 벤치마크 (1-2분, 반복 횟수 축소)
make run-demo
```

이 명령은 다음을 자동으로 수행합니다.

1. Python 가상환경 확인 및 생성
2. 기존 컨테이너 및 포트 정리 (6379, 6380, 27017)
3. 4개 서비스 빌드 및 실행
4. 벤치마크 완료 후 결과를 `benchmark/results/`에 저장

결과 파일:
- `benchmark/results/report.json` — 전체 결과 (JSON)
- `benchmark/results/report.csv` — 표 형태 (CSV)

---

## Make 명령어 정리

| 명령 | 설명 |
|------|------|
| `make dev` | mini-redis 단독 컨테이너 백그라운드 실행 |
| `make cli` | 실행 중인 mini-redis에 redis-cli 접속 |
| `make dev-down` | 데모 환경 종료 |
| `make run` | 전체 벤치마크 실행 (Redis + mini-redis + MongoDB + benchmark) |
| `make run-demo` | 발표용 축소 벤치마크 (1-2분) |
| `make bench` | 서비스가 떠 있을 때 벤치마크 봇만 재실행 |
| `make cli-official` | 벤치마크 환경의 공식 Redis에 redis-cli 접속 |
| `make down` | 벤치마크 컨테이너 전부 종료 + 포트 정리 |
| `make logs` | 전체 서비스 로그 스트리밍 |
| `make ps` | 컨테이너 상태 확인 |
| `make install` | Python venv 생성 + 패키지 설치 |
| `make clean` | venv + 결과 파일 + Docker 이미지 전부 삭제 |
| `make help` | 사용 가능한 명령어 출력 |

---

## 지원 명령어

총 53개 명령어를 지원합니다.

### Generic 명령어

| 명령 | 사용법 | 설명 | 반환값 |
|------|--------|------|--------|
| PING | `PING [message]` | 서버 연결 확인 | message 없으면 `PONG`, 있으면 message 반환 |
| DEL | `DEL key [key ...]` | 하나 이상의 키 삭제 | 삭제된 키 수 (integer) |
| EXISTS | `EXISTS key [key ...]` | 키 존재 여부 확인 | 존재하는 키 수 (integer) |
| EXPIRE | `EXPIRE key seconds` | 키에 TTL 설정 | 성공 1, 키 없으면 0 |
| TTL | `TTL key` | 키의 남은 TTL 조회 | 남은 초 수. 키 없으면 -2, TTL 없으면 -1 |
| PERSIST | `PERSIST key` | TTL 제거 | 성공 1, 변경 없으면 0 |
| PEXPIREAT | `PEXPIREAT key ms-timestamp` | 절대 시각으로 TTL 설정 (밀리초) | 성공 1, 키 없으면 0 |
| TYPE | `TYPE key` | 키에 저장된 값의 자료형 반환 | string / hash / list / set / zset / none |
| KEYS | `KEYS pattern` | 패턴에 매칭되는 키 목록 조회 | 매칭된 키 배열 |
| FLUSHALL | `FLUSHALL` | 모든 키 삭제 | OK |

### String 명령어

| 명령 | 사용법 | 설명 | 반환값 |
|------|--------|------|--------|
| GET | `GET key` | 문자열 값 조회 | 값 (bulk string) 또는 nil |
| SET | `SET key value [EX seconds] [PX milliseconds]` | 문자열 저장. EX/PX로 TTL 설정 가능 | OK |
| MGET | `MGET key [key ...]` | 여러 키의 값 동시 조회 | 값 배열 (없는 키는 nil) |
| MSET | `MSET key value [key value ...]` | 여러 키에 값 동시 저장 | OK |
| INCR | `INCR key` | 정수 값을 1 증가 | 증가 후 값 (integer) |
| DECR | `DECR key` | 정수 값을 1 감소 | 감소 후 값 (integer) |
| INCRBY | `INCRBY key increment` | 정수 값을 지정량만큼 증가 | 증가 후 값 (integer) |
| APPEND | `APPEND key value` | 기존 값 끝에 이어 붙이기 | 이어 붙인 후 전체 길이 (integer) |
| STRLEN | `STRLEN key` | 문자열의 바이트 길이 조회 | 길이 (integer). 키 없으면 0 |

### Hash 명령어

| 명령 | 사용법 | 설명 | 반환값 |
|------|--------|------|--------|
| HSET | `HSET key field value [field value ...]` | 하나 이상의 필드 설정 | 새로 추가된 필드 수 (integer) |
| HGET | `HGET key field` | 단일 필드 값 조회 | 값 (bulk string) 또는 nil |
| HMSET | `HMSET key field value [field value ...]` | 여러 필드 설정 (HSET과 동일 동작) | OK |
| HMGET | `HMGET key field [field ...]` | 여러 필드 값 조회 | 값 배열 (없는 필드는 nil) |
| HGETALL | `HGETALL key` | 모든 필드-값 쌍 조회 | [field1, value1, field2, value2, ...] 배열 |
| HDEL | `HDEL key field [field ...]` | 하나 이상의 필드 삭제 | 삭제된 필드 수 (integer) |
| HEXISTS | `HEXISTS key field` | 필드 존재 여부 확인 | 존재하면 1, 없으면 0 |
| HKEYS | `HKEYS key` | 모든 필드명 조회 | 필드명 배열 |
| HVALS | `HVALS key` | 모든 값 조회 | 값 배열 |
| HLEN | `HLEN key` | 필드 수 조회 | 필드 수 (integer) |

### List 명령어

| 명령 | 사용법 | 설명 | 반환값 |
|------|--------|------|--------|
| LPUSH | `LPUSH key value [value ...]` | 왼쪽에 하나 이상의 값 추가 | 추가 후 리스트 길이 (integer) |
| RPUSH | `RPUSH key value [value ...]` | 오른쪽에 하나 이상의 값 추가 | 추가 후 리스트 길이 (integer) |
| LPOP | `LPOP key` | 왼쪽에서 값 하나 꺼내기 | 꺼낸 값 (bulk string) 또는 nil |
| RPOP | `RPOP key` | 오른쪽에서 값 하나 꺼내기 | 꺼낸 값 (bulk string) 또는 nil |
| LRANGE | `LRANGE key start stop` | 범위 내 원소 조회. 음수 인덱스 지원 | 원소 배열 |
| LLEN | `LLEN key` | 리스트 길이 조회 | 길이 (integer). 키 없으면 0 |
| LINDEX | `LINDEX key index` | 특정 인덱스의 원소 조회. 음수 인덱스 지원 | 값 (bulk string) 또는 nil |
| LSET | `LSET key index value` | 특정 인덱스의 원소 변경 | OK. 범위 초과 시 에러 |

### Set 명령어

| 명령 | 사용법 | 설명 | 반환값 |
|------|--------|------|--------|
| SADD | `SADD key member [member ...]` | 하나 이상의 멤버 추가 | 새로 추가된 멤버 수 (integer) |
| SREM | `SREM key member [member ...]` | 하나 이상의 멤버 제거 | 제거된 멤버 수 (integer) |
| SMEMBERS | `SMEMBERS key` | 모든 멤버 조회 (정렬된 결과) | 멤버 배열 |
| SISMEMBER | `SISMEMBER key member` | 멤버 존재 여부 확인 | 존재하면 1, 없으면 0 |
| SCARD | `SCARD key` | 멤버 수 조회 | 멤버 수 (integer) |
| SINTER | `SINTER key [key ...]` | 여러 집합의 교집합 | 결과 멤버 배열 |
| SUNION | `SUNION key [key ...]` | 여러 집합의 합집합 | 결과 멤버 배열 |
| SDIFF | `SDIFF key [key ...]` | 첫 번째 집합에서 나머지를 뺀 차집합 | 결과 멤버 배열 |

### Sorted Set 명령어

| 명령 | 사용법 | 설명 | 반환값 |
|------|--------|------|--------|
| ZADD | `ZADD key score member [score member ...]` | 멤버 추가 또는 점수 갱신 | 새로 추가된 멤버 수 (integer) |
| ZREM | `ZREM key member [member ...]` | 멤버 제거 | 제거된 멤버 수 (integer) |
| ZSCORE | `ZSCORE key member` | 멤버의 점수 조회 | 점수 (bulk string) 또는 nil |
| ZRANK | `ZRANK key member` | 오름차순 순위 조회 (0부터 시작) | 순위 (integer) 또는 nil |
| ZRANGE | `ZRANGE key start stop [WITHSCORES]` | 오름차순 범위 조회. WITHSCORES로 점수 포함 | 멤버 배열 (점수 포함 시 교차 배열) |
| ZREVRANGE | `ZREVRANGE key start stop [WITHSCORES]` | 내림차순 범위 조회. WITHSCORES로 점수 포함 | 멤버 배열 |
| ZCARD | `ZCARD key` | 멤버 수 조회 | 멤버 수 (integer) |
| ZRANGEBYSCORE | `ZRANGEBYSCORE key min max` | 점수 범위 내 멤버 조회. `-inf`, `+inf` 지원 | 멤버 배열 |

---

## 자료구조 설계

모든 키는 `RedisObject(type, encoding, value)` 래퍼로 감싸져 DataStore에 저장됩니다.

| 자료형 | 내부 인코딩 | Python 자료형 | 설명 |
|--------|-----------|--------------|------|
| String | `raw` / `int` | `bytes` | 정수 변환 가능 시 `int` 인코딩 적용 |
| Hash | `dict` → `hashtable` | compact list → `ChainedHashTable` | 필드 32개 이하이고 값 64바이트 이하이면 compact list, 초과 시 자동 승격 |
| List | `deque` | `collections.deque` | 양끝 push/pop O(1) |
| Set | `hashtable` | `set` | Python built-in set |
| Sorted Set | `skiplist` | `ZSet` (dict + SkipList) | dict로 O(1) 점수 조회, SkipList로 O(log n) 범위/순위 조회 |

### 커스텀 자료구조

- **MurmurHash3 x86 32-bit** — Hash Table의 해시 함수. seed=0 고정 정책. LRU 캐시 적용.
- **ChainedHashTable** — Separate Chaining 방식. 런타임 Hash의 기본 테이블.
  - Load factor > 0.7 시 capacity 2배 확장
  - Load factor < 0.2 시 capacity 절반 축소
- **OpenAddressHashTable** — Double Hashing + Tombstone 방식. 비교 학습용으로 함께 제공.
- **SkipList** — 최대 16레벨, 승격 확률 P=0.25. `span` 배열로 O(log n) rank 계산.

---

## 서버 설계

단일 스레드 + I/O 멀티플렉싱 구조로 Redis와 동일한 설계를 따릅니다.

- `asyncio + uvloop` 이벤트 루프
- `asyncio.start_server()`로 TCP 소켓 수신
- 연결마다 `handle_client()` 코루틴이 생성되어 독립적으로 실행
- `await` 지점에서 이벤트 루프에 제어권을 반환하여 다른 연결 처리

느린 클라이언트 보호:

| 항목 | 기본값 | 설명 |
|------|--------|------|
| idle timeout | 30초 | 유휴 연결 자동 종료 |
| write drain timeout | 5초 | 응답을 수신하지 않는 클라이언트 차단 |
| max input buffer | 1MB | 과도한 요청 크기 제한 |
| max output buffer | 256KB | 응답 버퍼 메모리 보호 |
| max commands/tick | 128개 | 한 연결이 이벤트 루프를 독점하지 못하도록 제한 |

---

## TTL 관리

두 가지 전략을 함께 사용합니다.

**Lazy Expiry:** 키를 읽거나 확인할 때 (GET, EXISTS 등) 만료 여부를 검사하고, 만료되었으면 즉시 삭제합니다.

**Active Expiry:** 백그라운드 루프가 일정 간격(기본 100ms)으로 TTL 키 중 일부(기본 20개)를 랜덤 샘플링하여 만료된 키를 삭제합니다. 샘플에서 만료 비율이 25% 이상이면 같은 주기에 추가 패스를 수행합니다(최대 4회).

전체 키를 스캔하지 않으므로 오버헤드를 최소화하면서 만료 키가 메모리에 오래 남지 않도록 설계했습니다.

---

## 영속성

### AOF (Append Only File)

쓰기 명령을 RESP 형태로 파일에 append합니다. 서버 재시작 시 AOF를 replay하여 상태를 복구합니다.

fsync 정책:
- `always` — 매 명령마다 fsync
- `everysec` — 1초 간격으로 fsync (기본값)
- `no` — OS에 위임

### RDB (Snapshot)

현재 메모리 상태를 커스텀 바이너리 스냅샷으로 저장합니다. 주기적 저장과 서버 종료 시 저장을 지원합니다.

### 복구 우선순위

1. AOF 파일이 존재하면 AOF 우선 복구
2. AOF가 없고 RDB가 있으면 RDB 로드

---

## 메모리 제한과 eviction

`maxmemory`를 설정하면 쓰기 연산마다 메모리 사용량을 확인합니다.

| 정책 | 동작 |
|------|------|
| `noeviction` | 한도 초과 시 쓰기 거부 (OOM 에러 반환) |
| `allkeys-random` | 무작위 키 1개 삭제 후 재시도 |
| `allkeys-lru` | 가장 오래 접근하지 않은 키 삭제 |
| `volatile-ttl` | TTL이 설정된 키 중 만료가 가장 임박한 키 삭제 |

메모리 사용량은 `deep_getsizeof()`로 Python 객체 그래프를 재귀적으로 계측합니다. Redis의 allocator 기반 추적과는 다르지만 동일한 eviction 로직을 재현합니다.

---

## 벤치마크

공식 Redis, mini-redis, MongoDB를 같은 Docker 네트워크에서 동시에 실행하고 동일한 시나리오로 비교합니다.

### 시나리오

| 번호 | 시나리오 | 사용 명령 | 목적 |
|------|---------|----------|------|
| 1 | KV Cache | SET, GET | 기본 문자열 읽기/쓰기 성능 |
| 2 | Session Store | HSET, HGETALL | 세션 저장 패턴의 Hash 성능 |
| 3 | Rate Limiting | INCR, EXPIRE | 요청 수 제한 패턴 |
| 4 | Message Queue | LPUSH, RPOP | Producer/Consumer 큐 패턴 |
| 5 | Leaderboard | ZADD, ZREVRANGE | Sorted Set 기반 순위표 |
| 6 | Cache vs DB | Redis cache + MongoDB | 캐시 Hit/Miss 비교 |
| 7 | Pipeline | 배치 SET | 개별 요청과 파이프라인 처리량 비교 |

### 측정 지표

| 지표 | 설명 |
|------|------|
| Mean | 평균 레이턴시 (ms) |
| P50 | 중앙값 레이턴시 (ms) |
| P95 | 상위 5% 레이턴시 (ms) |
| P99 | 상위 1% 레이턴시 (ms) |
| Throughput | 초당 처리량 (ops/sec) |
| Error rate | 에러 비율 (%) |

---

## 환경 변수

`.env.example` 파일을 `.env`로 복사한 뒤 값을 조정합니다.

```bash
cp .env.example .env
```

### 서버 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MINI_REDIS_HOST` | `127.0.0.1` | 바인드 주소 |
| `MINI_REDIS_PORT` | `6379` | 리스닝 포트 |
| `MINI_REDIS_READ_CHUNK` | `4096` | 소켓 읽기 버퍼 크기 |
| `MINI_REDIS_MAXMEMORY` | `0` (무제한) | 최대 메모리. 예: `64mb`, `1gb` |
| `MINI_REDIS_MAXMEMORY_POLICY` | `noeviction` | eviction 정책 |
| `MINI_REDIS_APPENDONLY` | `no` | AOF 활성화. `yes` / `no` |
| `MINI_REDIS_AOF_FILE` | `data/appendonly.aof` | AOF 파일 경로 |
| `MINI_REDIS_AOF_FSYNC` | `everysec` | fsync 정책 |
| `MINI_REDIS_RDB_ENABLED` | `no` | RDB 활성화. `yes` / `no` |
| `MINI_REDIS_RDB_FILE` | `data/dump.rdb` | RDB 파일 경로 |
| `MINI_REDIS_RDB_SAVE_INTERVAL_SECONDS` | `0` | RDB 주기 저장 간격 (초). 0이면 비활성 |
| `MINI_REDIS_EXPIRY_LOOP_INTERVAL_MS` | `100` | Active expiry 루프 간격 (ms) |
| `MINI_REDIS_EXPIRY_SAMPLE_SIZE` | `20` | Active expiry 샘플 크기 |
| `MINI_REDIS_EXPIRY_MAX_PASSES` | `4` | Active expiry 최대 패스 수 |
| `MINI_REDIS_CLIENT_IDLE_TIMEOUT_SECONDS` | `30` | 유휴 연결 타임아웃 (초) |
| `MINI_REDIS_WRITE_DRAIN_TIMEOUT_SECONDS` | `5` | 쓰기 드레인 타임아웃 (초) |
| `MINI_REDIS_MAX_INPUT_BUFFER_BYTES` | `1048576` | 최대 입력 버퍼 (바이트) |
| `MINI_REDIS_MAX_OUTPUT_BUFFER_BYTES` | `262144` | 최대 출력 버퍼 (바이트) |
| `MINI_REDIS_MAX_COMMANDS_PER_TICK` | `128` | tick당 최대 명령 수 |
| `MINI_REDIS_LOG_LEVEL` | `INFO` | 로그 레벨 |

### 벤치마크 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `BENCH_ITERATIONS` | `1000` | 시나리오별 반복 횟수 |
| `BENCH_WARMUP` | `100` | 워밍업 반복 횟수 |
| `BENCH_PIPELINE_BATCH` | `100` | 파이프라인 배치 크기 |
| `BENCH_TTL_SECONDS` | `60` | 테스트용 TTL (초) |
| `BENCH_VALUE_SIZE` | `32` | 테스트 값 크기 (바이트) |
| `BENCH_CACHE_KEY_COUNT` | `100` | 캐시 시나리오 키 수 |
| `BENCH_SESSION_COUNT` | `100` | 세션 시나리오 세션 수 |
| `BENCH_RATE_USER_COUNT` | `50` | Rate limiting 사용자 수 |
| `BENCH_QUEUE_COUNT` | `5` | 큐 시나리오 큐 수 |
| `BENCH_LEADERBOARD_PLAYERS` | `500` | 리더보드 플레이어 수 |
| `BENCH_CACHE_HIT_KEYS` | `100` | Cache vs DB 시나리오 키 수 |
| `BENCH_STARTUP_DELAY_SECONDS` | `3` | 서비스 준비 대기 시간 (초) |
| `BENCH_SOCKET_TIMEOUT_SECONDS` | `5` | 소켓 타임아웃 (초) |
| `BENCH_RANDOM_SEED` | (없음) | 재현 가능 테스트용 시드 |

### 포트 설정

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `REDIS_OFFICIAL_HOST_PORT` | `6379` | 공식 Redis 호스트 포트 |
| `MINI_REDIS_HOST_PORT` | `6380` | mini-redis 호스트 포트 |
| `MONGO_HOST_PORT` | `27017` | MongoDB 호스트 포트 |

---

## 테스트

```bash
# 가상환경 활성화 후 전체 테스트
source venv/bin/activate
pytest -q

# 특정 테스트 파일만 실행
pytest tests/test_string_cmds.py -v
pytest tests/test_hash_table.py -v
pytest tests/test_server_integration.py -v
```

테스트 범위:
- RESP 파서/인코더 (`test_protocol.py`)
- String 명령 (`test_string_cmds.py`)
- Generic 명령 (`test_generic_cmds.py`)
- Collection 명령 (`test_collection_cmds.py`)
- Hash 명령 (`test_hash_cmds.py`)
- Hash Table 자료구조 (`test_hash_table.py`)
- DataStore (`test_datastore.py`)
- 영속성 / 메모리 / eviction (`test_persistence_memory.py`)
- 런타임 계약 검증 (`test_runtime_contracts.py`)
- TCP 통합 테스트 (`test_server_integration.py`)

---


## 현재 범위 밖인 기능

다음 기능은 현재 프로젝트에서 의도적으로 제외했습니다.

- Pub/Sub
- Transactions (MULTI / EXEC / WATCH)
- Replication / Cluster / Sentinel
- ACL / AUTH
- Streams
- Lua scripting
- Redis 원본 RDB 포맷 호환
- RESP3 프로토콜

