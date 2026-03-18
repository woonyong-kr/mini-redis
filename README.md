# mini-redis Hash Stack 설계 문서

## 프로젝트 개요
이 저장소는 Redis-like 동작을 학습하고 구현하기 위한 Python 기반 mini-redis 프로젝트입니다.

이번 문서의 초점은 hash 자료구조 경로를 Python 내장 `dict`에 기대지 않고, 명시적으로 설계된 커스텀 해시 스택으로 구현하는 것입니다.

현재 저장소에는 hash 명령과 저장 계층의 스켈레톤이 존재하며, 이 문서는 구현 설계와 실제 반영 결과를 함께 정리합니다.

## 구현 상태
- `store/hash_table.py`에 `BaseHashTable`, `ChainedHashTable`, `OpenAddressHashTable`, `Hash`를 구현했습니다.
- `store/datastore.py`의 hash 저장 경로는 내장 `dict` 대신 `Hash`를 사용하도록 연결했습니다.
- `commands/hash_cmds.py`에 `HSET/HGET/HMSET/HMGET/HGETALL/HDEL/HEXISTS/HKEYS/HVALS/HLEN`을 구현했습니다.
- 해시 전용 검증은 `tests/test_hash_table.py`, `tests/test_hash_cmds.py`에 추가했습니다.

## 최종 설계 요약
- 해싱은 `store/hash_table.py`의 `murmurhash3_32()`에 있습니다.
- chaining 기반 런타임 hash table과 resize는 `store/hash_table.py`의 `ChainedHashTable`에 있습니다.
- Open Addressing + Double Hashing 구현은 `store/hash_table.py`의 `OpenAddressHashTable`에 비교/회귀 테스트용으로 남아 있습니다.
- compact representation과 promotion은 `store/hash_table.py`의 `Hash`에 있습니다.
- seed 정책은 고정값 `0`입니다.
- 런타임 충돌 처리는 bucket 연결 리스트를 사용하는 separate chaining 입니다.

## 테스트 실행 예시
가상 환경 기준:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pytest tests/test_hash_table.py tests/test_hash_cmds.py -v
```

## 무엇을 구현할 예정인가
다음 네 계층을 구현 대상으로 둡니다.

1. `BaseHashTable`
2. `ChainedHashTable`
3. `OpenAddressHashTable`
4. `Hash`

각 계층의 역할은 다음과 같습니다.

- `BaseHashTable`
  - 공통 인터페이스를 정의합니다.
- `ChainedHashTable`
  - 런타임 hash 저장 경로를 담당합니다.
  - bucket 배열, 연결 리스트 기반 충돌 처리, 삭제, 리사이즈를 가집니다.
- `OpenAddressHashTable`
  - Open Addressing 비교 구현입니다.
  - 배열 기반 슬롯, 해싱, 프로빙, tombstone, 리사이즈를 가집니다.
- `Hash`
  - 상위 자료구조입니다.
  - 작은 데이터에서는 compact representation을 사용하고, 커지면 hashtable로 승격합니다.

## 무엇을 사용했는가
이번 hash stack 설계는 아래 요소를 사용합니다.

- MurmurHash3
- Separate Chaining
- Open Addressing with Double Hashing (비교용)
- compact representation + promotion

추가 의존성은 기본적으로 사용하지 않습니다.

## 왜 이것을 선택했는가

### MurmurHash3
- 비교적 단순하게 프로젝트 내부에 직접 구현할 수 있습니다.
- 빠르고 분산이 좋아 커스텀 해시 테이블 실험에 적합합니다.
- seed 정책을 명시하면 테스트와 재현성이 좋아집니다.

### Separate Chaining
- 충돌이 발생해도 probe 길이가 아니라 bucket 내부 연결 리스트 길이만 증가합니다.
- 삭제 시 tombstone이 필요 없어서 논리와 구현이 단순합니다.
- 충돌이 특정 bucket에 집중되어도 전체 배열 재배치 없이 내용을 유지할 수 있습니다.

### Open Addressing with Double Hashing
- 비교 기준이 되는 구현으로 유지합니다.
- 충돌이 적고 캐시 친화적인 상황에서 장점이 있어 성능 비교에 유용합니다.
- tombstone과 probe 비용이 실제 충돌 패턴에서 어떤 차이를 만드는지 관찰할 수 있습니다.

### Compact representation + promotion
- 작은 hash는 단순 선형 탐색 구조가 더 읽기 쉽고 구현 비용이 낮습니다.
- 데이터가 커졌을 때만 hashtable로 승격하면 작은 데이터와 큰 데이터 양쪽에서 균형 잡힌 설계를 만들 수 있습니다.
- Redis-like 자료구조의 “작을 때는 compact, 커지면 승격” 흐름을 학습하기 좋습니다.

## 핵심 정책

### 해싱
- 알고리즘: MurmurHash3
- seed: `0`

### 충돌 해결
- 런타임 방식: Separate Chaining
- bucket index는 `hash & (capacity - 1)`로 계산합니다.
- 같은 bucket으로 들어온 엔트리는 연결 리스트로 저장합니다.
- 비교용 구현으로 `OpenAddressHashTable`도 유지합니다.

### 삭제
- 런타임 chaining 경로는 연결 리스트에서 노드를 직접 제거합니다.
- 비교용 Open Addressing 구현은 tombstone 전략을 그대로 유지합니다.

### 리사이즈
- initial capacity = `8`
- grow when `live_count / capacity > 0.7`
- grow target = `capacity * 2`
- shrink when `live_count / capacity < 0.2`
- shrink target = `max(8, capacity // 2)`

정의:
- `live_count`: 현재 살아 있는 엔트리 수

리사이즈 시에는 live entry만 새 bucket 배열에 재삽입합니다.
비교용 Open Addressing 구현은 `used`와 tombstone 정리 정책을 별도로 유지합니다.

### Compact mode와 promotion
- 기본 compact 유지 조건:
  - entry count `<= 32`
  - `max(field length, value length) <= 64 bytes`
- compact 표현은 `(field, value)` 쌍의 명시적 리스트 기반을 기본안으로 사용합니다.
- 임계치를 넘으면 `ChainedHashTable`로 promotion 합니다.
- promotion 후에도 논리적 내용은 유지되어야 합니다.

## 저장소 내 예상 반영 위치
현재 저장소 기준으로 예상되는 반영 위치는 다음과 같습니다.

- `store/hash_table.py`
  - hash 코어 구현
- `store/datastore.py`
  - hash 저장 경로 연결
- `commands/hash_cmds.py`
  - hash 명령 구현
- `tests/test_hash_table.py`
  - 해시 테이블 단위 테스트
- `tests/test_hash_cmds.py`
  - 명령/스토어 통합 테스트

이 범위를 넘는 광범위한 마이그레이션은 기본 계획에 포함하지 않습니다.

## 현재 상태와 목표 상태

### 현재 상태
- hash 저장 경로는 커스텀 `Hash` / `ChainedHashTable`로 연결되어 있습니다.
- hash 명령 경로는 동작 가능한 상태이며, Redis-like 응답 형태를 반환합니다.
- 해시 전용 테스트가 추가되어 chaining 충돌 처리, resize, promotion을 검증합니다.

### 목표 상태
- hash 저장 경로가 커스텀 `Hash` / `ChainedHashTable`로 동작합니다.
- 해싱, chaining, 리사이즈, promotion 정책이 코드와 테스트에서 확인 가능합니다.
- hash 관련 명령이 일관된 Redis-like 동작을 제공합니다.

## 테스트 및 검증 계획
구현 시 아래 시나리오를 테스트 대상으로 둡니다.

- insert
- update existing key
- lookup hit / miss
- delete
- collision chain integrity
- collision-heavy cases
- grow resize
- shrink resize
- compact-to-hashtable promotion
- behavior preservation after promotion
- repeated delete / reinsert edge cases
- open addressing reference regression

## 제한사항
- 대상 hash-table 동작에 Python 내장 `dict`를 사용하지 않습니다.
- built-in `dict`를 전역적으로 대체하지 않습니다.
- dependency는 기본적으로 추가하지 않습니다.
- public API를 바꾸는 방향은 사전 승인 없이는 진행하지 않습니다.

## 후속 아이디어
아래 항목은 구현 이후 검토할 수 있는 후속 주제입니다.

- hash 내부 통계 정보 노출 여부 검토
- bucket 길이와 충돌 패턴 관찰용 디버그 도구 추가
- compact threshold 튜닝 실험
- hash 외 자료구조에도 유사한 설계 원칙을 적용할지 검토
