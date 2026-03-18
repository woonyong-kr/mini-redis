# mini-redis

Python으로 구현한 Redis-like 인메모리 서버입니다.  
`asyncio + uvloop` 기반 TCP 서버로 동작하며, `redis-cli`와 `redis-py` 같은 외부 클라이언트가 RESP 프로토콜로 바로 사용할 수 있습니다.

이번 과제의 핵심은 "해시 테이블을 활용한 key-value 저장소를 직접 구현하고, 그 설계와 동작을 설명할 수 있어야 한다"는 점입니다.  
이 저장소는 그 요구에 맞춰 **Hash 타입 내부 저장 경로를 Python 내장 `dict`에 맡기지 않고**, 별도의 커스텀 해시 스택으로 구현했습니다.

## 1. 한눈에 보는 프로젝트

- 외부 사용 가능: TCP 서버 + RESP 프로토콜
- 핵심 저장 구조: `DataStore` + `RedisObject`
- Hash 내부 구조: `Hash` -> compact list -> `ChainedHashTable`
- 비교 구현 포함: `OpenAddressHashTable` + Double Hashing + tombstone
- 만료 처리: lazy expiration + active expiration loop
- 검증 완료: `79 passed`

## 2. 요구사항 대응 요약

| 요구사항 | 현재 코드 기준 대응 |
| --- | --- |
| 해시 테이블 기반 key-value 저장소 직접 구현 | `store/hash_table.py`에 커스텀 해시 스택 구현 |
| 외부에서 사용할 수 있어야 함 | `server.py`가 RESP TCP 서버 제공, `redis-cli`/`redis-py` 사용 가능 |
| 설계 원리와 주요 함수 설명 가능해야 함 | README에 해싱, 충돌 처리, resize, promotion, TTL 흐름 정리 |
| 만료된 값 요청 처리 방안 | `DataStore._purge_if_expired()` + `ExpiryManager.active_expiry_loop()` |
| 동시성 문제 고려 | 단일 이벤트 루프 기반으로 공유 메모리 경합을 줄이는 구조 |
| 데이터 무효화 방식 고민 | `DEL`, `HDEL`, `EXPIRE`, `PERSIST`, `FLUSHALL` 제공 |
| 단위 테스트 / 기능 테스트 | `tests/`에 명령, 해시 구조, 프로토콜, 런타임 계약 테스트 포함 |
| 성능 비교 | `benchmark/benchmark.py`, `docker-compose.yml`, `Makefile`로 비교 환경 제공 |

## 3. 현재 구현 범위

### 구현 완료

- String
- Generic 명령: `PING`, `DEL`, `EXISTS`, `EXPIRE`, `TTL`, `PERSIST`, `TYPE`, `KEYS`, `FLUSHALL`
- Hash 명령: `HSET`, `HGET`, `HMSET`, `HMGET`, `HGETALL`, `HDEL`, `HEXISTS`, `HKEYS`, `HVALS`, `HLEN`
- List 명령: `LPUSH`, `RPUSH`, `LPOP`, `RPOP`, `LRANGE`, `LLEN`, `LINDEX`, `LSET`
- Pub/Sub 구독 모드
- RESP 파싱/인코딩
- TTL 관리

### 비교용 또는 부분 구현

- `OpenAddressHashTable`
  - Double Hashing, tombstone, resize 정책 구현
  - 단위 테스트와 in-process benchmark 비교용으로 사용
- Set / Sorted Set
  - 저장소 메서드 뼈대는 일부 존재
  - 명령 핸들러는 아직 미완성

## 4. 아키텍처

```text
redis-cli / redis-py / 외부 클라이언트
                |
                v
      server.py (asyncio TCP 서버)
                |
                v
      protocol/parser.py  -> RESP 요청 파싱
                |
                v
   commands/dispatcher.py -> 명령 핸들러 라우팅
                |
                v
   store/datastore.py + store/expiry.py
                |
                v
        RedisObject / Hash / List ...
```

### 핵심 파일

```text
server.py                # TCP 서버 진입점
commands/dispatcher.py   # 명령 라우팅
commands/hash_cmds.py    # Hash 명령 처리
commands/string_cmds.py  # String 명령 처리
store/datastore.py       # 메인 인메모리 저장소
store/expiry.py          # TTL / 만료 관리
store/hash_table.py      # 커스텀 해시 스택 핵심 구현
tests/                   # 단위 테스트 + 기능 테스트
benchmark/benchmark.py   # Redis/MongoDB 비교 벤치마크
```

## 5. 해시 스택 설계

### 5.1 왜 별도 해시 스택이 필요한가

Redis의 Hash는 단순히 "키 안에 또 다른 `dict`를 저장"하는 것으로 끝내면 설계 설명력이 떨어집니다.  
이번 구현에서는 Hash 타입 내부 저장 경로를 직접 제어하기 위해 다음 구조를 사용했습니다.

```text
Hash
├─ 작은 데이터: compact list[(field, value), ...]
└─ 커지면 승격: ChainedHashTable
```

중요한 점은 다음과 같습니다.

- 전역 keyspace인 `DataStore._data`는 Python `dict`를 사용합니다.
- 하지만 Redis Hash 내부의 field-value 저장은 커스텀 `Hash` 구조가 담당합니다.
- 즉, 과제의 핵심인 "Hash 자료구조 경로"는 직접 구현했습니다.

### 5.2 Hash의 두 단계 표현

#### 1) Compact 표현

작은 Hash는 `(field, value)` 튜플 리스트로 저장합니다.

- 장점: 구현이 단순하고 작은 데이터에서 메모리/코드 복잡도가 낮음
- 검색 방식: 선형 탐색
- 기본 유지 조건
  - entry 수 `<= 32`
  - field/value 바이트 길이 최대 `<= 64`

#### 2) Hashtable 승격

임계치를 넘으면 `Hash._promote_to_table()`이 호출되고 `ChainedHashTable`로 승격합니다.

- 기존 compact 데이터를 모두 새 테이블에 재삽입
- 승격 이후 `set/get/delete`는 해시 테이블 경로로 처리
- 외부 명령 관점에서는 동작이 바뀌지 않고 내부 표현만 변경

## 6. 해시 함수와 충돌 처리

### 6.1 해싱

`store/hash_table.py`의 `murmurhash3_32()`를 사용합니다.

- 알고리즘: MurmurHash3 x86 32-bit
- seed 정책: `0` 고정
- 문자열은 UTF-8 바이트로 변환 후 해싱
- 캐시: `_murmurhash3_32_str_cached()`로 반복 해싱 비용 절감

### 6.2 실제 런타임 경로: Separate Chaining

현재 `Hash`가 승격될 때 사용하는 실제 테이블은 `ChainedHashTable`입니다.

- 버킷 인덱스: `hash & (capacity - 1)`
- 충돌 처리: 같은 버킷에 연결 리스트로 연결
- 삭제: 연결 리스트에서 노드를 직접 제거
- 장점:
  - tombstone 불필요
  - 충돌이 많아도 lookup 로직이 단순
  - resize 시 live entry만 재삽입하면 됨

### 6.3 비교용 구현: Open Addressing + Double Hashing

같은 파일에 `OpenAddressHashTable`도 구현되어 있습니다.

- 슬롯 상태: `EMPTY / OCCUPIED / TOMBSTONE`
- probe step: 0이 되지 않도록 odd step 보장
- tombstone-aware lookup / insert / delete
- `tests/test_hash_table.py`와 `benchmark/benchmark.py`에서 비교용으로 사용

즉, 이 프로젝트는 **운영 경로는 chaining**, **학습/비교 경로는 open addressing**을 함께 보여주는 구조입니다.

## 7. Resize 정책

두 해시 테이블 구현 모두 power-of-two capacity를 사용합니다.

- initial capacity: `8`
- grow 조건: `live_count / capacity > 0.7`
- grow target: `capacity * 2`
- shrink 조건: `live_count / capacity < 0.2`
- shrink target: `max(8, capacity // 2)`

### resize가 중요한 이유

- 충돌이 많아지면 lookup/set 비용이 올라감
- 사용량이 줄었는데 너무 큰 배열을 유지하면 메모리 낭비
- resize 시 live entry만 재삽입해 tombstone이나 삭제 흔적을 정리할 수 있음

## 8. 주요 함수 동작 설명

### `Hash.set(field, value)`

1. compact 모드면 먼저 기존 field를 선형 탐색
2. 길이/개수 임계치를 넘는지 검사
3. 임계치 초과 시 hashtable로 승격
4. compact면 리스트 갱신, table 모드면 `table.set()` 위임

### `ChainedHashTable.set(key, value)`

1. `murmurhash3_32(key)` 계산
2. 버킷 인덱스 계산
3. 같은 key가 있으면 update
4. 없으면 버킷 head에 새 노드 삽입
5. load factor 확인 후 필요 시 resize

### `OpenAddressHashTable._find_slot(key, hash_code)`

1. home index 계산
2. step 계산
3. tombstone을 만나도 탐색 계속
4. insert 시 첫 tombstone 위치를 기억
5. 나중에 같은 key가 없을 때만 tombstone 재사용

### `DataStore.hset(key, field, value)`

1. 해당 key가 없으면 `Hash()` 생성
2. key가 있으면 타입 검사
3. `Hash.set()` 호출
4. 새 필드면 `1`, update면 `0` 반환

## 9. 만료 데이터 처리 방식

만료 처리는 두 단계로 구성됩니다.

### 1) Lazy expiration

조회 시점에 만료 여부를 확인합니다.

- `DataStore.get()`
- `DataStore.exists()`
- `DataStore.get_type()`
- `DataStore.keys()`

이 경로에서 `_purge_if_expired()`가 실행되어, 만료된 키는 요청 순간 바로 삭제됩니다.

### 2) Active expiration loop

백그라운드 루프가 주기적으로 만료 키를 정리합니다.

- 구현 위치: `store/expiry.py`
- 실행 위치: `server.py`의 `active_expiry_loop()`

이 구조 덕분에 "만료된 값을 요청받았을 때 어떻게 처리할 것인가?"에 대해,

- 즉시 접근 시 정리하고
- 접근이 없어도 주기적으로 청소하는

하이브리드 전략을 설명할 수 있습니다.

## 10. 동시성 문제를 줄이기 위한 구조

이 프로젝트는 `asyncio` 단일 이벤트 루프 기반입니다.

- 각 클라이언트 연결은 코루틴으로 처리
- 저장소는 서버 인스턴스 내부에서 공유
- 별도 스레드 락 없이도 대부분의 상태 변경이 이벤트 루프 안에서 순차적으로 실행됨

발표에서 강조할 포인트:

- 멀티스레드 공유 메모리보다 경쟁 조건을 줄이기 쉽다
- 대신 CPU 바운드 작업이 길어지면 전체 응답성이 떨어질 수 있다
- 수평 확장 단계에서는 shard / actor / external persistence 같은 구조가 필요하다

## 11. 데이터 무효화 전략

사용자가 저장 데이터를 무효화하는 경로는 다음과 같습니다.

- 키 단위 삭제: `DEL`
- Hash 내부 field 삭제: `HDEL`
- 시간 기반 무효화: `EXPIRE`
- TTL 해제: `PERSIST`
- 전체 초기화: `FLUSHALL`

Cache 관점에서는 `EXPIRE`와 `DEL`을 조합해 명시적 invalidation과 시간 기반 invalidation을 모두 설명할 수 있습니다.

## 12. 장애 시 데이터 보존 관점

현재 mini-redis는 **메모리 기반** 구현이며 별도 영속성 레이어는 없습니다.

- 장점: 구조가 단순하고 빠름
- 한계: 프로세스 종료 시 데이터 유실 가능

발표에서 Optional 확장 아이디어로 제안할 수 있는 방식:

- AOF(Append Only File)
- 주기적 스냅샷(RDB 유사)
- WAL + snapshot 혼합
- 복제(replication) 또는 외부 DB 백업

## 13. 외부에서 사용하는 방법

### 13.1 로컬 실행

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py --host 0.0.0.0 --port 6379
```

### 13.2 `redis-cli`로 사용

```bash
redis-cli -p 6379
PING
SET hello world
GET hello
HSET session:1 user_id 1 username alice role admin
HGETALL session:1
EXPIRE session:1 10
TTL session:1
```

### 13.3 `redis-py`로 사용

```python
import redis

r = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)

r.set("hello", "world")
print(r.get("hello"))

r.hset("session:1", mapping={
    "user_id": "1",
    "username": "alice",
    "role": "admin",
})
print(r.hgetall("session:1"))
```

### 13.4 Docker 기반 벤치마크 스택

`docker-compose.yml`에서는 다음 포트를 사용합니다.

- redis-official: `localhost:6379`
- mini-redis: `localhost:6380`
- mongodb: `localhost:27017`

즉, Docker 조합에서는 mini-redis 접속 포트가 `6380`입니다.

## 14. 테스트와 검증

### 이번 작업에서 실제 수행한 검증

2026-03-19 기준 아래 명령으로 전체 테스트를 실행했습니다.

```bash
.venv/bin/python -m pytest -q
```

실행 결과:

```text
79 passed in 0.05s
```

### 어떤 테스트가 있는가

- `tests/test_hash_table.py`
  - insert / update / lookup / miss
  - delete / repeated delete
  - collision-heavy case
  - grow / shrink resize
  - tombstone-aware lookup
  - tombstone reuse
  - compact -> hashtable promotion
- `tests/test_hash_cmds.py`
  - `HSET`, `HGET`, `HMSET`, `HMGET`, `HGETALL`, `HDEL`, `HEXISTS`, `HKEYS`, `HVALS`, `HLEN`
  - promotion 이후 명령 동작 유지
  - wrong type 에러 처리
- `tests/test_string_cmds.py`
  - `SET/GET`, `EX`, `PX`, 잘못된 옵션, 숫자 명령, `APPEND`
- `tests/test_generic_cmds.py`
  - `DEL`, `EXISTS`, `EXPIRE`, `TTL`, `PERSIST`, `TYPE`, `KEYS`, `FLUSHALL`
- `tests/test_runtime_contracts.py`
  - 프로토콜 round-trip
  - delete hook
  - Pub/Sub 구독 모드 전환

### 발표에서 꼭 보여줄 검증 포인트

1. Hash는 직접 구현한 구조라는 점
2. 단순 동작 확인이 아니라 충돌, resize, promotion까지 테스트했다는 점
3. TTL/만료와 wrong-type 같은 실제 서비스 에러 경로도 검증했다는 점
4. 전체 회귀 테스트를 한 번에 돌려 `79 passed`를 확인했다는 점

## 15. 벤치마크

이 저장소는 "Redis를 쓸 때와 안 쓸 때의 성능 차이"를 비교하기 위한 벤치마크 하니스를 포함합니다.

### 실행 방법

```bash
make run
```

결과 파일:

- `benchmark/results/report.json`
- `benchmark/results/report.csv`

### 포함된 시나리오

- KV Cache: `GET` / `SET`
- Session Store: Hash 기반 세션 read/update
- Rate Limiting: `INCR + EXPIRE`
- Message Queue: `LPUSH / RPOP`
- Cache vs DB: Redis 캐시 앞단 vs MongoDB 직접 조회
- Pipeline: 개별 요청 vs 파이프라인
- Hash Collision Stress: chaining vs open addressing 비교

참고:

- Benchmark는 미구현 명령이 있는 시나리오는 자동으로 스킵하도록 작성되어 있습니다.
- 해시 충돌 비교는 네트워크를 제외하고 자료구조 자체 비용만 측정합니다.

## 16. 발표 데모 추천 순서

1. `redis-cli`로 `PING`, `SET`, `GET` 시연
2. `HSET` / `HGETALL`로 세션 데이터 저장 시연
3. `EXPIRE` / `TTL`로 만료 처리 시연
4. "Hash는 compact -> hashtable로 승격된다"는 내부 구조 설명
5. 테스트 명령 실행 또는 결과 화면으로 `79 passed` 제시
6. 마지막으로 benchmark 시나리오와 비교 관점 설명

## 17. 기술 스택

- Python
- asyncio
- uvloop
- pytest
- Docker / Docker Compose
- benchmark client
  - `redis`
  - `pymongo`

## 18. 현재 한계와 다음 단계

- Set / Sorted Set 명령 경로는 아직 미완성
- mini-redis 자체 영속성은 아직 없음
- Hash의 실제 운영 경로는 chaining이고, open addressing은 비교용 구현
- 멀티프로세스/분산 환경까지는 고려하지 않은 단일 서버 구조

다음 단계 아이디어:

- AOF 또는 snapshot 기반 영속성 추가
- Set / Sorted Set 완성
- 해시 충돌 통계 시각화
- Hash 승격 정책 튜닝
- benchmark 결과를 그래프로 시각화

---

## 발표용 핵심 메시지

이 프로젝트는 "Redis 비슷한 서버를 만들었다"에서 끝나지 않습니다.  
외부 클라이언트가 실제로 붙을 수 있는 서버를 만들고, Hash 내부 저장 경로를 직접 구현했으며, TTL/무효화/동시성 구조를 설명할 수 있고, 마지막으로 테스트와 벤치마크까지 준비한 구현 중심 결과물입니다.
