# mini-redis CLI 테스트 시나리오

> **대상 서버**: `127.0.0.1:6399` (기본 포트 6379 대신 6399 사용)
> **프로토콜**: RESP (REdis Serialization Protocol)
> **테스트 도구**: `nc` (netcat) 또는 `redis-cli -p 6399`

---

## 서버 실행 방법

```bash
# 가상환경 활성화 후
cd mini-redis
python server.py --port 6399

# 또는 기본 포트 6379
python server.py
```

---

## 테스트용 헬퍼 함수

테스트 전 아래 함수를 쉘에 정의해두면 편리합니다.

```bash
send_resp() {
  local args=("$@")
  local count=${#args[@]}
  local payload="*${count}\r\n"
  for arg in "${args[@]}"; do
    local len=${#arg}
    payload+='$'"${len}\r\n${arg}\r\n"
  done
  printf "$payload" | nc -w1 127.0.0.1 6399 2>/dev/null
}
```

또는 `redis-cli`가 설치되어 있다면:

```bash
alias rc='redis-cli -p 6399'
```

---

## 시나리오 1 — PING / 연결 확인

```bash
send_resp PING
# 기대 응답: +PONG

send_resp PING "hello"
# 기대 응답: $5\r\nhello  (bulk string)
```

---

## 시나리오 2 — String 기본 명령어

```bash
# SET / GET
send_resp SET mykey "hello"
# +OK

send_resp GET mykey
# $5\r\nhello

# 존재하지 않는 키
send_resp GET nonexistent
# $-1  (null bulk string)

# MSET / MGET
send_resp MSET k1 v1 k2 v2 k3 v3
# +OK

send_resp MGET k1 k2 k3
# *3 배열: v1, v2, v3
```

---

## 시나리오 3 — String 숫자 연산

```bash
send_resp SET counter 10
send_resp INCR counter       # :11
send_resp INCR counter       # :12
send_resp DECR counter       # :11
send_resp INCRBY counter 5   # :16
send_resp GET counter        # $2\r\n16
```

---

## 시나리오 4 — String APPEND / STRLEN

```bash
send_resp SET strkey "Hello"
send_resp APPEND strkey " World"   # :11 (총 길이)
send_resp STRLEN strkey            # :11
send_resp GET strkey               # $11\r\nHello World
```

---

## 시나리오 5 — Generic: EXISTS / DEL

```bash
send_resp SET mykey "hello"
send_resp EXISTS mykey          # :1 (존재)
send_resp EXISTS nonexistent    # :0 (없음)

# 여러 키 동시 삭제
send_resp MSET k1 a k2 b k3 c
send_resp DEL k1 k2 k3          # :3 (삭제된 수)
send_resp EXISTS k1             # :0
```

---

## 시나리오 6 — Generic: EXPIRE / TTL / PERSIST

```bash
send_resp SET tempkey "temporary"
send_resp EXPIRE tempkey 60    # :1 (설정 성공)
send_resp TTL tempkey          # :59 또는 :60 (남은 초)

# TTL 제거 (영구 키로 변환)
send_resp PERSIST tempkey      # :1 (성공)
send_resp TTL tempkey          # :-1 (만료 없음)

# 존재하지 않는 키에 EXPIRE
send_resp EXPIRE nonexistent 60   # :0 (실패)
send_resp TTL nonexistent         # :-2 (키 없음)
```

---

## 시나리오 7 — TTL 자동 만료 확인

```bash
send_resp SET expkey "bye" EX 5
send_resp TTL expkey       # :4 또는 :3 (남은 초)
send_resp EXISTS expkey    # :1

# 5초 대기 후
sleep 6

send_resp TTL expkey       # :-2 (만료됨)
send_resp EXISTS expkey    # :0
send_resp GET expkey       # $-1 (null)
```

---

## 시나리오 8 — SET EX / PX 옵션

```bash
# EX: 초 단위 TTL
send_resp SET exkey "val" EX 30
send_resp TTL exkey        # :29 또는 :30

# PX: 밀리초 단위 TTL
send_resp SET pxkey "val" PX 10000
send_resp TTL pxkey        # :9 또는 :10
```

---

## 시나리오 9 — TYPE / KEYS

```bash
send_resp FLUSHALL

send_resp SET strtype "string_val"
send_resp TYPE strtype        # +string

send_resp RPUSH listtype a b c
send_resp TYPE listtype       # +list

send_resp SADD settype m1 m2
send_resp TYPE settype        # +set

send_resp HSET hashtype f v
send_resp TYPE hashtype       # +hash

send_resp ZADD zsettype 1.0 member
send_resp TYPE zsettype       # +zset

# KEYS 패턴 검색
send_resp SET user:1 "Alice"
send_resp SET user:2 "Bob"
send_resp SET session:abc "token"

send_resp KEYS "user:*"   # user:1, user:2
send_resp KEYS "*"        # 전체 키
```

---

## 시나리오 10 — Hash 명령어

```bash
# HSET (멀티 필드)
send_resp HSET user:100 name "Alice" age "30" email "alice@example.com"
# :3 (추가된 필드 수)

# HGET
send_resp HGET user:100 name     # $5\r\nAlice
send_resp HGET user:100 missing  # $-1 (null)

# HGETALL
send_resp HGETALL user:100
# *6 배열: name Alice age 30 email alice@example.com

# HEXISTS / HLEN
send_resp HEXISTS user:100 name    # :1
send_resp HEXISTS user:100 ghost   # :0
send_resp HLEN user:100            # :3

# HKEYS / HVALS
send_resp HKEYS user:100   # *3: name, age, email
send_resp HVALS user:100   # *3: Alice, 30, alice@example.com

# HDEL
send_resp HDEL user:100 email    # :1
send_resp HLEN user:100          # :2

# HMSET / HMGET
send_resp HMSET product:1 title "Widget" price "9.99" stock "100"
send_resp HMGET product:1 title price stock missing
# *4: Widget, 9.99, 100, $-1(null)
```

---

## 시나리오 11 — List 명령어

```bash
# RPUSH / LPUSH
send_resp RPUSH mylist a b c d e    # :5
send_resp LPUSH mylist z y x        # :8
send_resp LLEN mylist               # :8

# LRANGE
send_resp LRANGE mylist 0 -1   # 전체: x y z a b c d e
send_resp LRANGE mylist 0 2    # x y z
send_resp LRANGE mylist -3 -1  # c d e

# LPOP / RPOP
send_resp LPOP mylist   # $1\r\nx (왼쪽 pop)
send_resp RPOP mylist   # $1\r\ne (오른쪽 pop)

# LINDEX
send_resp LINDEX mylist 0    # $1\r\ny (0번 인덱스)
send_resp LINDEX mylist -1   # $1\r\nd (마지막)

# LSET
send_resp LSET mylist 1 "CHANGED"   # +OK
send_resp LRANGE mylist 0 -1        # y CHANGED z a b c d
```

---

## 시나리오 12 — Set 명령어

```bash
# SADD (중복 무시)
send_resp SADD colors red green blue red   # :3 (실제 추가된 수)
send_resp SCARD colors                     # :3

# SMEMBERS
send_resp SMEMBERS colors   # *3: blue green red (순서 무작위)

# SISMEMBER
send_resp SISMEMBER colors red     # :1
send_resp SISMEMBER colors yellow  # :0

# SREM
send_resp SREM colors red    # :1
send_resp SMEMBERS colors    # *2: blue green

# 집합 연산
send_resp SADD setA 1 2 3 4 5
send_resp SADD setB 3 4 5 6 7

send_resp SINTER setA setB   # *3: 3 4 5
send_resp SUNION setA setB   # *7: 1 2 3 4 5 6 7
send_resp SDIFF setA setB    # *2: 1 2
```

---

## 시나리오 13 — Sorted Set 명령어

```bash
# ZADD
send_resp ZADD leaderboard 100 "Alice" 200 "Bob" 150 "Charlie" 50 "Dave"
# :4

# ZCARD / ZSCORE / ZRANK
send_resp ZCARD leaderboard         # :4
send_resp ZSCORE leaderboard Alice  # $3\r\n100
send_resp ZRANK leaderboard Alice   # :1 (0-indexed, Dave=0)
send_resp ZRANK leaderboard Bob     # :3

# ZRANGE (오름차순)
send_resp ZRANGE leaderboard 0 -1
# *4: Dave Alice Charlie Bob

send_resp ZRANGE leaderboard 0 -1 WITHSCORES
# *8: Dave 50 Alice 100 Charlie 150 Bob 200

# ZREVRANGE (내림차순)
send_resp ZREVRANGE leaderboard 0 -1
# *4: Bob Charlie Alice Dave

send_resp ZREVRANGE leaderboard 0 -1 WITHSCORES
# *8: Bob 200 Charlie 150 Alice 100 Dave 50

# ZRANGEBYSCORE
send_resp ZRANGEBYSCORE leaderboard 100 200   # *3: Alice Charlie Bob
send_resp ZRANGEBYSCORE leaderboard -inf +inf  # 전체 (4개)

# ZREM
send_resp ZREM leaderboard Dave    # :1
send_resp ZCARD leaderboard        # :3
```

---

## 시나리오 14 — FLUSHALL

```bash
send_resp MSET k1 v1 k2 v2 k3 v3
send_resp KEYS "*"      # k1 k2 k3 ...

send_resp FLUSHALL      # +OK

send_resp KEYS "*"      # *0 (빈 배열)
```

---

## 시나리오 15 — 에러 처리

```bash
# WRONGTYPE 에러
send_resp SET strkey "hello"
send_resp LPUSH strkey "element"
# -WRONGTYPE Operation against a key holding the wrong kind of value

# 알 수 없는 명령어
send_resp UNKNOWN cmd
# -ERR unknown command 'UNKNOWN'

# 인수 부족
send_resp GET
# -ERR wrong number of arguments for 'get' command

send_resp SET
# -ERR wrong number of arguments for 'set' command

# 정수가 아닌 값으로 INCR
send_resp SET notnum "abc"
send_resp INCR notnum
# -ERR value is not an integer or out of range

# 음수 EXPIRE
send_resp SET key "val"
send_resp EXPIRE key -1
# -ERR invalid expire time (또는 유사 에러)
```

---

## 시나리오 16 — 파이프라이닝

여러 명령을 한 TCP 연결에서 연속으로 전송합니다.

```bash
printf '*3\r\n$3\r\nSET\r\n$4\r\nkey1\r\n$3\r\nfoo\r\n*3\r\n$3\r\nSET\r\n$4\r\nkey2\r\n$3\r\nbar\r\n*2\r\n$3\r\nGET\r\n$4\r\nkey1\r\n*2\r\n$3\r\nGET\r\n$4\r\nkey2\r\n' \
  | nc -w1 127.0.0.1 6399

# 기대 응답:
# +OK
# +OK
# $3\r\nfoo
# $3\r\nbar
```

---

## 시나리오 17 — AOF 영속성 테스트

서버를 AOF 활성화 상태로 실행할 때 테스트합니다.

```bash
# AOF 활성화로 서버 시작
MINI_REDIS_APPENDONLY=true MINI_REDIS_AOF_FILE=data/appendonly.aof \
  python server.py --port 6399

# 데이터 입력
send_resp SET persistent_key "saved_value"
send_resp HSET session:1 user "Alice" token "abc123"
send_resp RPUSH jobqueue task1 task2 task3

# 서버 재시작 (Ctrl+C 후 다시 실행)
# python server.py --port 6399

# 재시작 후 데이터 확인
send_resp GET persistent_key       # $12\r\nsaved_value
send_resp HGETALL session:1        # user Alice token abc123
send_resp LRANGE jobqueue 0 -1     # task1 task2 task3
```

---

## 시나리오 18 — 메모리 제한 (noeviction)

```bash
# 메모리 제한 설정으로 서버 시작
MINI_REDIS_MAXMEMORY=1kb MINI_REDIS_MAXMEMORY_POLICY=noeviction \
  python server.py --port 6399

# 데이터를 계속 추가하면 OOM 에러 발생
send_resp SET key1 "$(python3 -c "print('x'*500)")"
send_resp SET key2 "$(python3 -c "print('x'*500)")"
send_resp SET key3 "data"
# -OOM command not allowed when used memory > 'maxmemory'
```

---

## 전체 회귀 테스트 스크립트

```bash
#!/usr/bin/env bash
# test_all.sh — mini-redis 전체 CLI 테스트

HOST=127.0.0.1
PORT=6399
PASS=0
FAIL=0

send_resp() {
  local args=("$@")
  local count=${#args[@]}
  local payload="*${count}\r\n"
  for arg in "${args[@]}"; do
    local len=${#arg}
    payload+='$'"${len}\r\n${arg}\r\n"
  done
  printf "$payload" | nc -w1 $HOST $PORT 2>/dev/null
}

assert() {
  local desc="$1"
  local actual="$2"
  local expected="$3"
  if [[ "$actual" == *"$expected"* ]]; then
    echo "  ✅ PASS: $desc"
    ((PASS++))
  else
    echo "  ❌ FAIL: $desc"
    echo "     expected: $expected"
    echo "     actual:   $actual"
    ((FAIL++))
  fi
}

echo "=== mini-redis 회귀 테스트 ==="
echo ""

send_resp FLUSHALL > /dev/null

echo "[1] 기본 연결"
assert "PING" "$(send_resp PING)" "PONG"

echo "[2] String"
send_resp SET foo bar > /dev/null
assert "GET foo" "$(send_resp GET foo)" "bar"
assert "INCR counter" "$(send_resp INCR counter)" ":1"
assert "STRLEN foo" "$(send_resp STRLEN foo)" ":3"

echo "[3] Hash"
send_resp HSET h f1 v1 f2 v2 > /dev/null
assert "HGET h f1" "$(send_resp HGET h f1)" "v1"
assert "HLEN h" "$(send_resp HLEN h)" ":2"

echo "[4] List"
send_resp RPUSH mylist a b c > /dev/null
assert "LLEN mylist" "$(send_resp LLEN mylist)" ":3"
assert "LPOP mylist" "$(send_resp LPOP mylist)" "a"

echo "[5] Set"
send_resp SADD myset x y z > /dev/null
assert "SCARD myset" "$(send_resp SCARD myset)" ":3"
assert "SISMEMBER myset x" "$(send_resp SISMEMBER myset x)" ":1"

echo "[6] ZSet"
send_resp ZADD zs 1.0 a 2.0 b 3.0 c > /dev/null
assert "ZCARD zs" "$(send_resp ZCARD zs)" ":3"
assert "ZSCORE zs b" "$(send_resp ZSCORE zs b)" "2"

echo "[7] TTL"
send_resp SET tk "val" EX 30 > /dev/null
assert "TTL tk > 0" "$(send_resp TTL tk)" ":2"

echo "[8] 에러 처리"
assert "WRONGTYPE" "$(send_resp GET mylist)" "WRONGTYPE"
assert "Unknown cmd" "$(send_resp BADCMD)" "unknown command"

echo ""
echo "=== 결과: PASS=$PASS, FAIL=$FAIL ==="
```

위 스크립트를 저장 후 실행:

```bash
chmod +x test_all.sh
./test_all.sh
```
