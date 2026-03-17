# mini-redis 구현 계획서

> Python으로 Redis와 유사한 인메모리 키-값 저장소를 구현하는 프로젝트입니다.

---

## 1. 프로젝트 목표

- Redis의 핵심 기능 (GET/SET/EXPIRE/TTL, Hash, List, Set, Sorted Set)을 Python으로 재구현
- `asyncio` + `uvloop` 기반의 비동기 단일 스레드 서버
- Redis와 동일한 RESP 프로토콜을 사용하여 기존 Redis 클라이언트(`redis-py` 등) 호환 유지
- 학습 및 실험 목적의 구현 (프로덕션 Redis 교체 목적 아님)

---

## 2. 전체 아키텍처

```
Client (redis-py, redis-cli 등)
         │
         │ TCP 연결 (RESP Protocol)
         ▼
┌─────────────────────────────────────────┐
│          server.py (진입점)              │
│   asyncio.start_server → 클라이언트 연결  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│        protocol/parser.py               │
│   RESP 바이트 스트림 → Python 객체 파싱   │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│        protocol/encoder.py              │
│   Python 객체 → RESP 바이트 스트림 인코딩 │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│        commands/dispatcher.py           │
│   명령어 문자열 → 해당 핸들러 함수 라우팅  │
└──────────────────┬──────────────────────┘
          ┌────────┼────────────────┐
          ▼        ▼                ▼
   string_cmds  hash_cmds    list_cmds ...
   (GET/SET)   (HGET/HSET)  (LPUSH/LRANGE)
          └────────┬────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│          store/datastore.py             │
│   인메모리 딕셔너리 + 타입별 자료구조     │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│          store/expiry.py                │
│   TTL 관리: Lazy Expiry + Active Expiry  │
└─────────────────────────────────────────┘
```

---

## 3. 디렉토리 구조

```
mini-redis/
├── README.md
├── PLAN.md                  # 이 문서
├── TEAM.md                  # 팀 협업 계획
├── requirements.txt         # 의존성 (uvloop, sortedcontainers)
├── server.py                # 서버 진입점
├── protocol/
│   ├── __init__.py
│   ├── parser.py            # RESP 파싱
│   └── encoder.py           # RESP 인코딩
├── commands/
│   ├── __init__.py
│   ├── dispatcher.py        # 명령어 라우팅
│   ├── string_cmds.py       # String 명령어
│   ├── hash_cmds.py         # Hash 명령어
│   ├── list_cmds.py         # List 명령어
│   ├── set_cmds.py          # Set 명령어
│   ├── zset_cmds.py         # Sorted Set 명령어
│   └── generic_cmds.py      # DEL, EXISTS, EXPIRE, TTL, TYPE
├── store/
│   ├── __init__.py
│   ├── datastore.py         # 메인 인메모리 스토어
│   └── expiry.py            # TTL / 만료 관리
└── tests/
    ├── test_protocol.py
    ├── test_string_cmds.py
    ├── test_hash_cmds.py
    ├── test_list_cmds.py
    ├── test_set_cmds.py
    └── test_expiry.py
```

---

## 4. RESP 프로토콜 명세

Redis는 RESP(Redis Serialization Protocol)를 사용합니다. 모든 통신은 이 형식으로 이루어집니다.

| 타입 | 접두사 | 예시 |
|------|--------|------|
| Simple String | `+` | `+OK\r\n` |
| Error | `-` | `-ERR unknown command\r\n` |
| Integer | `:` | `:1000\r\n` |
| Bulk String | `$` | `$6\r\nfoobar\r\n` |
| Null Bulk | `$` | `$-1\r\n` |
| Array | `*` | `*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n` |

**예시 - `SET foo bar` 명령 흐름:**
```
클라이언트 → 서버: *3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n
서버 → 클라이언트: +OK\r\n
```

---

## 5. 데이터 타입별 내부 구조

| Redis 타입 | Python 내부 타입 | 주요 명령어 |
|-----------|----------------|-----------|
| String | `str` / `bytes` | GET, SET, MGET, MSET, INCR, DECR, APPEND |
| Hash | `dict` | HGET, HSET, HDEL, HGETALL, HKEYS, HVALS |
| List | `collections.deque` | LPUSH, RPUSH, LPOP, RPOP, LRANGE, LLEN |
| Set | `set` | SADD, SREM, SMEMBERS, SISMEMBER, SINTER, SUNION |
| Sorted Set | `sortedcontainers.SortedList` | ZADD, ZREM, ZSCORE, ZRANGE, ZRANK |

---

## 6. 구현 단계 (Phase)

### Phase 0 - 스캐폴딩 (리더 담당, 1-2일)

모든 팀원이 작업을 시작하기 전에 리더가 전체 골격 코드를 먼저 완성합니다.
각 모듈의 함수 시그니처와 인터페이스를 추상화된 상태로 정의해두면, 팀원들은 인터페이스를 보고 서로 독립적으로 구현할 수 있습니다.

**결과물:** 모든 파일이 존재하고, 함수 정의(`def`)와 `raise NotImplementedError` 또는 `pass`로 채워진 상태

---

### Phase 1 - 핵심 기반 구현 (병렬 작업 가능)

| 모듈 | 내용 | 담당 |
|------|------|------|
| `protocol/parser.py` | RESP 파싱 로직 구현 | 팀원 A |
| `protocol/encoder.py` | RESP 인코딩 로직 구현 | 팀원 A |
| `store/datastore.py` | 인메모리 스토어 클래스 구현 | 팀원 B |
| `store/expiry.py` | TTL 관리 로직 구현 | 팀원 B |

---

### Phase 2 - 명령어 구현 (병렬 작업 가능)

| 모듈 | 내용 | 담당 |
|------|------|------|
| `commands/string_cmds.py` | GET, SET, INCR 등 | 팀원 C |
| `commands/hash_cmds.py` | HGET, HSET 등 | 팀원 D |
| `commands/list_cmds.py` | LPUSH, LRANGE 등 | 팀원 D |
| `commands/set_cmds.py` | SADD, SMEMBERS 등 | 팀원 E |
| `commands/zset_cmds.py` | ZADD, ZRANGE 등 | 팀원 E |
| `commands/generic_cmds.py` | DEL, EXPIRE, TTL 등 | 팀원 C |

---

### Phase 3 - 통합 및 서버 연결

| 작업 | 내용 |
|------|------|
| `commands/dispatcher.py` 완성 | 모든 명령어 핸들러 등록 |
| `server.py` 완성 | asyncio 서버와 파서/인코더 연결 |
| 통합 테스트 | `redis-cli`로 실제 명령어 테스트 |

---

### Phase 4 - 안정화 및 선택 구현

| 작업 | 우선순위 |
|------|---------|
| 에러 핸들링 강화 | 높음 |
| 단위 테스트 작성 | 높음 |
| AOF 영속성 (선택) | 낮음 |
| RDB 스냅샷 (선택) | 낮음 |

---

## 7. 핵심 인터페이스 정의

각 팀원은 아래 인터페이스를 기준으로 구현합니다. **함수 시그니처를 변경하지 마세요.**

### DataStore (store/datastore.py)

```python
class DataStore:
    def get(self, key: str) -> Optional[Any]: ...
    def set(self, key: str, value: Any) -> None: ...
    def delete(self, key: str) -> int: ...
    def exists(self, key: str) -> bool: ...
    def get_type(self, key: str) -> str: ...  # "string", "hash", "list", "set", "zset", "none"
    def keys(self, pattern: str = "*") -> List[str]: ...
```

### ExpiryManager (store/expiry.py)

```python
class ExpiryManager:
    def set_expiry(self, key: str, seconds: float) -> None: ...
    def get_ttl(self, key: str) -> float: ...   # -1: 없음, -2: 키 없음
    def is_expired(self, key: str) -> bool: ...
    def remove_expiry(self, key: str) -> None: ...
    async def active_expiry_loop(self) -> None: ...  # 백그라운드 태스크
```

### RESP Parser (protocol/parser.py)

```python
def parse(data: bytes) -> Tuple[Optional[List], int]:
    """
    Returns: (parsed_command, bytes_consumed)
    parsed_command: ["SET", "foo", "bar"] 형태의 리스트
    bytes_consumed: 파싱에 사용된 바이트 수
    """
    ...
```

### RESP Encoder (protocol/encoder.py)

```python
def encode_simple_string(s: str) -> bytes: ...
def encode_error(msg: str) -> bytes: ...
def encode_integer(n: int) -> bytes: ...
def encode_bulk_string(s: Optional[str]) -> bytes: ...
def encode_array(items: List) -> bytes: ...
```

### Command Handler 시그니처 (commands/*.py)

```python
# 모든 명령어 핸들러는 동일한 시그니처를 가집니다
def cmd_get(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes: ...
def cmd_set(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes: ...
```

---

## 8. 의존성

```
# requirements.txt
uvloop>=0.17.0           # asyncio 이벤트 루프 가속
sortedcontainers>=2.4.0  # Sorted Set 구현용
pytest>=7.0.0            # 테스트
pytest-asyncio>=0.21.0   # 비동기 테스트
```

---

## 9. 완성 기준 체크리스트

- [ ] `redis-cli ping` → `PONG`
- [ ] `redis-cli set foo bar` → `OK`, `get foo` → `bar`
- [ ] `redis-cli set counter 0`, `incr counter` → `1`
- [ ] `redis-cli expire foo 10`, `ttl foo` → `10` 이하
- [ ] `redis-cli hset user name alice`, `hget user name` → `alice`
- [ ] `redis-cli lpush mylist a b c`, `lrange mylist 0 -1` → `["c", "b", "a"]`
- [ ] `redis-cli sadd myset x y z`, `smembers myset` → `{"x", "y", "z"}`
- [ ] `redis-cli zadd scores 100 alice 200 bob`, `zrange scores 0 -1` → `["alice", "bob"]`
