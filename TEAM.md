# mini-redis 팀 협업 계획

---

## 핵심 원칙: "스캐폴딩 먼저, 구현 나중에"

개발 초보 팀이 병렬로 작업할 때 가장 큰 문제는 **"내 코드가 다른 사람 코드에 어떻게 연결되는지 모르는 것"** 입니다.

이를 해결하기 위해 아래 순서를 반드시 따릅니다:

```
1단계 (리더)       모든 파일과 함수 뼈대를 먼저 만든다
                  ↓ (Git push)
2단계 (팀원 전체)  각자 자기 영역의 함수 내부만 채운다
                  ↓ (PR 방식으로 합친다)
3단계 (리더)       통합 테스트 후 연결 오류를 수정한다
```

이렇게 하면 팀원 A가 B의 코드를 기다릴 필요 없이, B가 만든 **인터페이스(함수 시그니처)**만 믿고 병렬로 작업할 수 있습니다.

---

## 팀 역할 구성

| 역할 | 담당 업무 |
|------|---------|
| **리더** | 스캐폴딩 작성, PR 리뷰, 통합 테스트, 배포 |
| **팀원 A** | protocol 영역 (RESP 파서 + 인코더) |
| **팀원 B** | store 영역 (DataStore + ExpiryManager) |
| **팀원 C** | String 명령어 + Generic 명령어 |
| **팀원 D** | Hash 명령어 + List 명령어 |
| **팀원 E** | Set 명령어 + Sorted Set 명령어 |

> 팀 규모에 따라 C+D 또는 D+E를 한 명이 담당해도 됩니다.

---

## Git 워크플로우

### 브랜치 전략

```
main               ← 항상 동작하는 코드만 존재
  └── develop      ← 통합 브랜치 (PR은 여기로)
       ├── feat/protocol        (팀원 A)
       ├── feat/store           (팀원 B)
       ├── feat/string-cmds     (팀원 C)
       ├── feat/hash-list-cmds  (팀원 D)
       └── feat/set-zset-cmds   (팀원 E)
```

### 브랜치 생성 방법

```bash
# develop 브랜치에서 시작
git checkout develop
git pull origin develop
git checkout -b feat/protocol
```

### 커밋 메시지 규칙

```
feat: RESP 파서 구현
fix: bulk string 파싱 오류 수정
test: string 명령어 단위 테스트 추가
docs: PLAN.md 업데이트
```

### PR 규칙

1. 자기 기능이 완성되면 `develop` 브랜치로 PR 요청
2. PR에는 **테스트 통과 여부**를 명시
3. 리더가 리뷰 후 머지

---

## 작업 영역 상세 가이드

### 팀원 A - Protocol 담당

**작업 파일:** `protocol/parser.py`, `protocol/encoder.py`

**하는 일:** 클라이언트가 보내는 바이트 데이터를 Python 리스트로 변환하고, 반대로 Python 객체를 클라이언트가 읽을 수 있는 바이트로 변환합니다.

```python
# 예시: 이런 바이트가 들어오면
b"*3\r\n$3\r\nSET\r\n$3\r\nfoo\r\n$3\r\nbar\r\n"

# 이런 리스트가 나와야 함
["SET", "foo", "bar"]
```

**구현 포인트:**
- `parser.py`: `*` (Array), `$` (Bulk String) 위주로 먼저 구현 (클라이언트 요청은 항상 Array 형태)
- `encoder.py`: `+OK`, `-ERR`, `:숫자`, `$문자열`, `*배열` 5가지 형태 인코딩

**테스트 방법:**
```python
from protocol.parser import parse
result, consumed = parse(b"*2\r\n$3\r\nGET\r\n$3\r\nfoo\r\n")
assert result == ["GET", "foo"]
```

---

### 팀원 B - Store 담당

**작업 파일:** `store/datastore.py`, `store/expiry.py`

**하는 일:** 모든 키-값 데이터를 메모리에 저장하고 관리합니다. TTL(Time To Live) 기반 자동 만료 기능도 담당합니다.

```python
# 예시: 이렇게 쓰임
store = DataStore()
store.set("foo", "bar")
store.get("foo")  # → "bar"

expiry = ExpiryManager(store)
expiry.set_expiry("foo", 10)  # 10초 후 만료
expiry.get_ttl("foo")         # → 9.xx (남은 시간)
```

**구현 포인트:**
- `datastore.py`: 내부적으로 `self._data = {}` 딕셔너리 하나로 관리
- `expiry.py`: 만료 시각을 `{key: expiry_timestamp}` 딕셔너리로 저장
- Lazy Expiry: `get()` 호출 시 만료 여부 체크 → 만료됐으면 None 반환 + 삭제
- Active Expiry: `asyncio` 루프에서 0.1초마다 만료 키 청소

**주의:** DataStore는 Redis 타입(string/hash/list/set/zset)을 구분해서 저장해야 합니다.

---

### 팀원 C - String + Generic 명령어 담당

**작업 파일:** `commands/string_cmds.py`, `commands/generic_cmds.py`

**구현 명령어:**

| 명령어 | 설명 |
|--------|------|
| GET key | 값 조회 |
| SET key value [EX seconds] | 값 저장 (EX 옵션으로 TTL 설정) |
| MGET key [key ...] | 여러 키 한 번에 조회 |
| MSET key value [key value ...] | 여러 키 한 번에 저장 |
| INCR key | 정수값 1 증가 |
| DECR key | 정수값 1 감소 |
| APPEND key value | 문자열 뒤에 이어붙이기 |
| DEL key [key ...] | 키 삭제 |
| EXISTS key | 키 존재 여부 확인 |
| EXPIRE key seconds | TTL 설정 |
| TTL key | 남은 TTL 조회 |
| TYPE key | 값의 타입 조회 |
| PING [message] | 서버 연결 확인 |
| FLUSHALL | 전체 데이터 삭제 |

**구현 예시:**
```python
def cmd_set(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    if len(args) < 2:
        return encode_error("ERR wrong number of arguments for 'set' command")
    key, value = args[0], args[1]
    # EX 옵션 처리
    if len(args) >= 4 and args[2].upper() == "EX":
        expiry.set_expiry(key, float(args[3]))
    store.set(key, value)
    return encode_simple_string("OK")
```

---

### 팀원 D - Hash + List 명령어 담당

**작업 파일:** `commands/hash_cmds.py`, `commands/list_cmds.py`

**구현 명령어:**

**Hash:**

| 명령어 | 설명 |
|--------|------|
| HSET key field value | 해시 필드 설정 |
| HGET key field | 해시 필드 조회 |
| HMSET key f1 v1 [f2 v2 ...] | 여러 필드 한 번에 설정 |
| HGETALL key | 모든 필드와 값 조회 |
| HDEL key field [field ...] | 필드 삭제 |
| HEXISTS key field | 필드 존재 여부 |
| HKEYS key | 모든 필드명 조회 |
| HVALS key | 모든 값 조회 |
| HLEN key | 필드 수 조회 |

**List:**

| 명령어 | 설명 |
|--------|------|
| LPUSH key value [value ...] | 왼쪽에 추가 |
| RPUSH key value [value ...] | 오른쪽에 추가 |
| LPOP key | 왼쪽에서 꺼내기 |
| RPOP key | 오른쪽에서 꺼내기 |
| LRANGE key start stop | 범위 조회 |
| LLEN key | 길이 조회 |
| LINDEX key index | 특정 인덱스 조회 |

---

### 팀원 E - Set + Sorted Set 명령어 담당

**작업 파일:** `commands/set_cmds.py`, `commands/zset_cmds.py`

**구현 명령어:**

**Set:**

| 명령어 | 설명 |
|--------|------|
| SADD key member [member ...] | 멤버 추가 |
| SREM key member [member ...] | 멤버 삭제 |
| SMEMBERS key | 전체 멤버 조회 |
| SISMEMBER key member | 멤버 존재 여부 |
| SCARD key | 멤버 수 조회 |
| SINTER key [key ...] | 교집합 |
| SUNION key [key ...] | 합집합 |
| SDIFF key [key ...] | 차집합 |

**Sorted Set:**

| 명령어 | 설명 |
|--------|------|
| ZADD key score member | score와 함께 멤버 추가 |
| ZREM key member | 멤버 삭제 |
| ZSCORE key member | score 조회 |
| ZRANK key member | 순위 조회 (오름차순) |
| ZRANGE key start stop [WITHSCORES] | 범위 조회 |
| ZCARD key | 멤버 수 조회 |

---

## 스캐폴딩 예시 (리더가 만들어 줘야 할 뼈대)

팀원들이 받게 될 뼈대 코드는 아래와 같은 형태입니다. 함수가 이미 존재하고, 내부만 `raise NotImplementedError`로 비어있습니다.

```python
# commands/string_cmds.py - 팀원 C가 받는 뼈대

from typing import List
from store.datastore import DataStore
from store.expiry import ExpiryManager
from protocol.encoder import encode_simple_string, encode_bulk_string, encode_error, encode_integer

def cmd_get(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """GET key - 키에 저장된 값을 반환. 없으면 nil 반환."""
    raise NotImplementedError

def cmd_set(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """SET key value [EX seconds] - 값 저장. EX 옵션으로 만료 시간 설정."""
    raise NotImplementedError

def cmd_incr(store: DataStore, expiry: ExpiryManager, args: List[str]) -> bytes:
    """INCR key - 정수 값 1 증가. 키가 없으면 0에서 시작."""
    raise NotImplementedError

# ... 나머지 함수들도 동일 형태
```

---

## 협업 시 주의사항

**절대 변경하면 안 되는 것:**
- 함수 이름 (dispatcher.py가 함수 이름으로 연결하기 때문)
- 함수 파라미터 순서 `(store, expiry, args)`
- 반환 타입 (`bytes`)

**자유롭게 변경 가능한 것:**
- 함수 내부 구현
- 내부에서 사용하는 변수명
- 에러 메시지 문구

**막히면 어떻게 할까:**
1. PLAN.md의 인터페이스 정의 다시 확인
2. 같은 영역 함수 중 완성된 것 참고
3. 리더에게 질문 (Slack/Discord 등)

---

## 진행 상황 트래킹

| 모듈 | 담당 | 뼈대 | 구현 | 테스트 | PR |
|------|------|------|------|--------|-----|
| protocol/parser.py | 팀원 A | ☐ | ☐ | ☐ | ☐ |
| protocol/encoder.py | 팀원 A | ☐ | ☐ | ☐ | ☐ |
| store/datastore.py | 팀원 B | ☐ | ☐ | ☐ | ☐ |
| store/expiry.py | 팀원 B | ☐ | ☐ | ☐ | ☐ |
| commands/string_cmds.py | 팀원 C | ☐ | ☐ | ☐ | ☐ |
| commands/generic_cmds.py | 팀원 C | ☐ | ☐ | ☐ | ☐ |
| commands/hash_cmds.py | 팀원 D | ☐ | ☐ | ☐ | ☐ |
| commands/list_cmds.py | 팀원 D | ☐ | ☐ | ☐ | ☐ |
| commands/set_cmds.py | 팀원 E | ☐ | ☐ | ☐ | ☐ |
| commands/zset_cmds.py | 팀원 E | ☐ | ☐ | ☐ | ☐ |
| commands/dispatcher.py | 리더 | ☐ | ☐ | ☐ | ☐ |
| server.py | 리더 | ☐ | ☐ | ☐ | ☐ |
