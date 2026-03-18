"""
mini-redis 벤치마크 봇
======================

3개의 서비스(Redis Official, mini-redis, MongoDB)를 대상으로
다양한 시나리오를 실행하고 성능 지표를 측정합니다.

측정 지표:
  - 평균 레이턴시 (mean latency)
  - P50 / P95 / P99 레이턴시 (백분위수)
  - 처리량 (throughput, ops/sec)
  - 에러율 (error rate)

시나리오:
  1. KV Cache      - 단순 문자열 GET/SET
  2. Session Store - Hash 기반 세션 관리
  3. Rate Limiting - INCR + TTL 패턴
  4. Message Queue - List 기반 큐 (LPUSH/RPOP)
  5. Leaderboard   - Sorted Set 순위표
  6. Cache vs DB   - Redis 캐시 앞단 vs MongoDB 직접 조회
  7. Pub/Sub       - 발행-구독 메시지 전달 (실제 Redis만)
  8. Pipeline      - 파이프라인 vs 개별 요청 비교

결과:
  - 콘솔 테이블 출력
  - results/report.json 저장
  - results/report.csv  저장
"""

import os
import time
import json
import csv
import random
import string
import statistics
import threading
from dataclasses import dataclass, field
from typing import List, Optional

import redis
from pymongo import MongoClient


# ─────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────

def _env_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default

    value = int(raw)
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _env_float(name: str, default: float, *, min_value: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default

    value = float(raw)
    if value < min_value:
        raise ValueError(f"{name} must be >= {min_value}, got {value}")
    return value


def _env_optional_int(name: str) -> Optional[int]:
    raw = os.getenv(name)
    if raw in (None, ""):
        return None
    return int(raw)


@dataclass(frozen=True)
class BenchmarkConfig:
    redis_official_host: str
    redis_official_port: int
    mini_redis_host: str
    mini_redis_port: int
    mongo_host: str
    mongo_port: int
    iterations: int
    warmup_iterations: int
    pipeline_batch: int
    ttl_seconds: int
    value_size: int
    cache_key_count: int
    session_count: int
    rate_user_count: int
    queue_count: int
    leaderboard_players: int
    cache_hit_keys: int
    pubsub_iterations: int
    startup_delay_seconds: float
    socket_timeout_seconds: float
    random_seed: Optional[int]

    @classmethod
    def from_env(cls) -> "BenchmarkConfig":
        return cls(
            redis_official_host=os.getenv("REDIS_OFFICIAL_HOST", "localhost"),
            redis_official_port=_env_int("REDIS_OFFICIAL_PORT", 6379),
            mini_redis_host=os.getenv("MINI_REDIS_HOST", "localhost"),
            mini_redis_port=_env_int("MINI_REDIS_PORT", 6380),
            mongo_host=os.getenv("MONGO_HOST", "localhost"),
            mongo_port=_env_int("MONGO_PORT", 27017),
            iterations=_env_int("BENCH_ITERATIONS", 1000),
            warmup_iterations=_env_int("BENCH_WARMUP", 100, min_value=0),
            pipeline_batch=_env_int("BENCH_PIPELINE_BATCH", 100),
            ttl_seconds=_env_int("BENCH_TTL_SECONDS", 60),
            value_size=_env_int("BENCH_VALUE_SIZE", 32),
            cache_key_count=_env_int("BENCH_CACHE_KEY_COUNT", 100),
            session_count=_env_int("BENCH_SESSION_COUNT", 100),
            rate_user_count=_env_int("BENCH_RATE_USER_COUNT", 50),
            queue_count=_env_int("BENCH_QUEUE_COUNT", 5),
            leaderboard_players=_env_int("BENCH_LEADERBOARD_PLAYERS", 500),
            cache_hit_keys=_env_int("BENCH_CACHE_HIT_KEYS", 100),
            pubsub_iterations=_env_int("BENCH_PUBSUB_ITERATIONS", 200),
            startup_delay_seconds=_env_float("BENCH_STARTUP_DELAY_SECONDS", 3.0),
            socket_timeout_seconds=_env_float("BENCH_SOCKET_TIMEOUT_SECONDS", 5.0),
            random_seed=_env_optional_int("BENCH_RANDOM_SEED"),
        )


CONFIG = BenchmarkConfig.from_env()

if CONFIG.random_seed is not None:
    random.seed(CONFIG.random_seed)


# ─────────────────────────────────────────────────────────────────
# 결과 자료구조
# ─────────────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    service: str          # "redis-official" | "mini-redis" | "mongodb"
    scenario: str         # 시나리오 이름
    iterations: int       # 실제 실행 횟수
    errors: int           # 오류 발생 횟수
    operations_per_iteration: int = 1
    latencies_ms: List[float] = field(default_factory=list, repr=False)

    @property
    def error_rate(self) -> float:
        return self.errors / self.iterations if self.iterations else 0

    @property
    def successes(self) -> int:
        return max(self.iterations - self.errors, 0)

    @property
    def mean_ms(self) -> float:
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p50_ms(self) -> float:
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0

    @property
    def p95_ms(self) -> float:
        s = sorted(self.latencies_ms)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s) - 1)] if s else 0

    @property
    def p99_ms(self) -> float:
        s = sorted(self.latencies_ms)
        idx = int(len(s) * 0.99)
        return s[min(idx, len(s) - 1)] if s else 0

    @property
    def throughput_ops(self) -> float:
        """초당 처리량 (ops/sec)"""
        total_sec = sum(self.latencies_ms) / 1000
        if total_sec <= 0:
            return 0
        return (self.successes * self.operations_per_iteration) / total_sec

    def to_dict(self) -> dict:
        return {
            "service": self.service,
            "scenario": self.scenario,
            "iterations": self.iterations,
            "errors": self.errors,
            "error_rate_%": round(self.error_rate * 100, 2),
            "mean_ms": round(self.mean_ms, 4),
            "p50_ms": round(self.p50_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "throughput_ops_sec": round(self.throughput_ops, 1),
        }


def run_scenario(
    service_name: str,
    scenario_name: str,
    func,
    iterations: Optional[int] = None,
    warmup_iterations: Optional[int] = None,
    operations_per_iteration: int = 1,
) -> ScenarioResult:
    """
    func을 iterations번 실행하며 레이턴시를 측정합니다.
    func의 시그니처: func() → None (또는 아무 값)
    """
    actual_iterations = iterations if iterations is not None else CONFIG.iterations
    actual_warmup = (
        CONFIG.warmup_iterations if warmup_iterations is None else warmup_iterations
    )

    for _ in range(actual_warmup):
        try:
            func()
        except Exception:
            pass

    result = ScenarioResult(
        service=service_name,
        scenario=scenario_name,
        iterations=actual_iterations,
        errors=0,
        operations_per_iteration=operations_per_iteration,
    )

    for _ in range(actual_iterations):
        start = time.perf_counter()
        try:
            func()
        except Exception:
            result.errors += 1
        elapsed_ms = (time.perf_counter() - start) * 1000
        result.latencies_ms.append(elapsed_ms)

    return result


# ─────────────────────────────────────────────────────────────────
# 헬퍼
# ─────────────────────────────────────────────────────────────────

def rand_key(prefix="key") -> str:
    suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    return f"{prefix}:{suffix}"

def rand_str(length: Optional[int] = None) -> str:
    length = CONFIG.value_size if length is None else length
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


# ─────────────────────────────────────────────────────────────────
# 시나리오 1: KV Cache — 단순 문자열 GET/SET
# ─────────────────────────────────────────────────────────────────

def scenario_kv_cache(r: redis.Redis, service: str) -> ScenarioResult:
    """
    SET key value → GET key 패턴.

    측정 포인트:
      - 단순 문자열 읽기/쓰기 기본 레이턴시
      - Redis vs mini-redis 기본 성능 차이
    """
    preloaded_keys = [rand_key("cache") for _ in range(CONFIG.cache_key_count)]
    for k in preloaded_keys:
        r.set(k, rand_str())

    def op():
        key = random.choice(preloaded_keys)
        r.get(key)

    return run_scenario(service, "1_kv_cache_get", op)


def scenario_kv_cache_set(r: redis.Redis, service: str) -> ScenarioResult:
    """
    SET 작업만 측정.
    쓰기 레이턴시가 읽기 레이턴시보다 얼마나 차이나는지 확인.
    """
    def op():
        r.set(rand_key("set"), rand_str(), ex=CONFIG.ttl_seconds)

    return run_scenario(service, "1_kv_cache_set", op)


# ─────────────────────────────────────────────────────────────────
# 시나리오 2: Session Store — Hash 기반 사용자 세션
# ─────────────────────────────────────────────────────────────────

def scenario_session_store(r: redis.Redis, service: str) -> ScenarioResult:
    """
    HSET user:{id} field value 패턴.

    실제 사용 사례: 로그인 세션 저장
    측정 포인트:
      - Hash 연산 레이턴시
      - 필드 수가 많을수록 어떻게 변하는지
    """
    session_keys = []
    for i in range(CONFIG.session_count):
        key = f"session:{i:04d}"
        r.hset(key, mapping={
            "user_id": str(i),
            "username": f"user_{i}",
            "email": f"user_{i}@example.com",
            "created_at": str(int(time.time())),
            "last_seen": str(int(time.time())),
        })
        session_keys.append(key)

    def op():
        key = random.choice(session_keys)
        r.hgetall(key)

    return run_scenario(service, "2_session_hgetall", op)


# ─────────────────────────────────────────────────────────────────
# 시나리오 3: Rate Limiting — INCR + TTL 패턴
# ─────────────────────────────────────────────────────────────────

def scenario_rate_limiting(r: redis.Redis, service: str) -> ScenarioResult:
    """
    INCR rate:{user_id} 후 TTL이 없으면 EXPIRE 설정.
    "슬라이딩 윈도우" 레이트 리미팅의 단순화 버전.

    측정 포인트:
      - INCR의 원자성 보장이 얼마나 빠른지
      - 실제로 API 게이트웨이에서 사용할 수 있는 패턴인지
    """
    user_ids = [f"rate:user:{i}" for i in range(CONFIG.rate_user_count)]

    def op():
        key = random.choice(user_ids)
        count = r.incr(key)
        if count == 1:
            r.expire(key, CONFIG.ttl_seconds)  # 첫 요청 시 TTL 설정

    return run_scenario(service, "3_rate_limiting_incr", op)


# ─────────────────────────────────────────────────────────────────
# 시나리오 4: Message Queue — List 기반 작업 큐
# ─────────────────────────────────────────────────────────────────

def scenario_message_queue_push(r: redis.Redis, service: str) -> ScenarioResult:
    """
    LPUSH queue:{name} message 패턴.
    Producer 역할 측정.
    """
    queues = [f"queue:{i}" for i in range(CONFIG.queue_count)]

    def op():
        q = random.choice(queues)
        r.lpush(q, json.dumps({"task_id": rand_str(8), "payload": rand_str(64)}))

    return run_scenario(service, "4_queue_lpush", op)


def scenario_message_queue_pop(r: redis.Redis, service: str) -> ScenarioResult:
    """
    RPOP queue:{name} 패턴.
    Consumer 역할 측정.
    큐에 미리 데이터를 채워두고 꺼내는 속도를 측정.
    """
    queue_key = "queue:bench"
    preload_count = CONFIG.iterations + CONFIG.warmup_iterations
    for _ in range(preload_count):
        r.lpush(queue_key, rand_str(64))

    def op():
        r.rpop(queue_key)

    return run_scenario(service, "4_queue_rpop", op)


# ─────────────────────────────────────────────────────────────────
# 시나리오 5: Leaderboard — Sorted Set 순위표
# ─────────────────────────────────────────────────────────────────

def scenario_leaderboard(r: redis.Redis, service: str) -> ScenarioResult:
    """
    ZADD + ZRANGE 패턴.
    게임 순위표, 포인트 시스템 등에 사용.

    측정 포인트:
      - Sorted Set 삽입/조회 레이턴시
      - 멤버 수 증가에 따른 성능 변화 관찰 가능
    """
    board_key = "leaderboard:global"
    players = [f"player:{i:04d}" for i in range(CONFIG.leaderboard_players)]
    for p in players:
        r.zadd(board_key, {p: random.uniform(0, 10000)})

    def op():
        choice = random.randint(0, 1)
        if choice == 0:
            # 점수 업데이트
            player = random.choice(players)
            r.zadd(board_key, {player: random.uniform(0, 10000)})
        else:
            # 상위 10명 조회
            r.zrevrange(board_key, 0, 9, withscores=True)

    return run_scenario(service, "5_leaderboard_zadd_zrange", op)


# ─────────────────────────────────────────────────────────────────
# 시나리오 6: Cache vs DB — Redis 캐시 앞단 vs MongoDB 직접 조회
# ─────────────────────────────────────────────────────────────────

def scenario_cache_vs_db(
    r: redis.Redis,
    mongo_db,
    redis_service: str,
) -> List[ScenarioResult]:
    """
    Cache-Aside 패턴:
      1. Redis에서 먼저 조회 (Cache Hit)
      2. 없으면 MongoDB 조회 후 Redis에 캐싱 (Cache Miss)

    측정 포인트:
      - Cache Hit vs Cache Miss 레이턴시 차이
      - Redis를 앞단에 두었을 때 실제 DB 부하 감소 효과

    반환: [cache_hit_result, cache_miss_result, mongo_direct_result]
    """
    collection = mongo_db["products"]
    required_products = max(
        1000,
        CONFIG.cache_hit_keys + CONFIG.iterations + CONFIG.warmup_iterations + 10,
    )

    # MongoDB에 충분한 상품 데이터 삽입
    products = [
        {"product_id": f"prod:{i:04d}", "name": f"Product {i}", "price": round(random.uniform(1, 999), 2)}
        for i in range(required_products)
    ]
    collection.drop()
    collection.insert_many(products)
    product_ids = [p["product_id"] for p in products]

    # ── Cache HIT 측정: Redis에 미리 캐싱해두고 조회 ──
    for p in products[:CONFIG.cache_hit_keys]:
        r.set(
            f"product:{p['product_id']}",
            json.dumps(p, default=str),
            ex=CONFIG.ttl_seconds,
        )

    cached_ids = [f"prod:{i:04d}" for i in range(CONFIG.cache_hit_keys)]

    def cache_hit():
        pid = random.choice(cached_ids)
        r.get(f"product:{pid}")

    result_hit = run_scenario(redis_service, "6_cache_hit", cache_hit)

    # ── Cache MISS 측정: 캐시 없이 → MongoDB 조회 → Redis 저장 ──
    miss_start = CONFIG.cache_hit_keys
    miss_end = miss_start + CONFIG.iterations + CONFIG.warmup_iterations
    uncached_ids = [f"prod:{i:04d}" for i in range(miss_start, miss_end)]
    miss_index = 0

    def cache_miss():
        nonlocal miss_index
        pid = uncached_ids[miss_index % len(uncached_ids)]
        miss_index += 1
        cache_key = f"product:{pid}"
        cached = r.get(cache_key)
        if not cached:
            doc = collection.find_one({"product_id": pid}, {"_id": 0})
            if doc:
                r.set(cache_key, json.dumps(doc, default=str), ex=CONFIG.ttl_seconds)

    result_miss = run_scenario(redis_service, "6_cache_miss_then_set", cache_miss)

    # ── MongoDB 직접 조회 (캐시 없이) ──
    def mongo_direct():
        pid = random.choice(product_ids)
        collection.find_one({"product_id": pid}, {"_id": 0})

    result_mongo = run_scenario("mongodb", "6_mongo_direct_query", mongo_direct)

    return [result_hit, result_miss, result_mongo]


# ─────────────────────────────────────────────────────────────────
# 시나리오 7: Pipeline — 파이프라인 vs 개별 요청
# ─────────────────────────────────────────────────────────────────

def scenario_pipeline(r: redis.Redis, service: str) -> List[ScenarioResult]:
    """
    같은 N개의 SET 작업을:
      A. 개별 요청으로 N번 → N번의 RTT
      B. 파이프라인으로 1번 → 1번의 RTT

    측정 포인트:
      - 네트워크 RTT가 얼마나 병목인지
      - 파이프라인으로 얼마나 개선되는지
      - (mini-redis는 파이프라인 지원 여부도 확인 가능)
    """
    N = CONFIG.pipeline_batch
    batches = max(CONFIG.iterations // N, 1)
    warmup_batches = max(CONFIG.warmup_iterations // N, 0)

    # A. 개별 요청
    def individual():
        for i in range(N):
            r.set(f"pipe:individual:{i}", rand_str())

    individual_latencies = []
    for _ in range(warmup_batches):
        try:
            individual()
        except Exception:
            pass

    individual_errors = 0
    for _ in range(batches):
        start = time.perf_counter()
        try:
            individual()
        except Exception:
            individual_errors += 1
        individual_latencies.append((time.perf_counter() - start) * 1000)

    result_individual = ScenarioResult(
        service=service,
        scenario=f"7_pipeline_individual_{N}ops",
        iterations=batches,
        errors=individual_errors,
        operations_per_iteration=N,
        latencies_ms=individual_latencies,
    )

    # B. 파이프라인
    def pipelined():
        pipe = r.pipeline(transaction=False)
        for i in range(N):
            pipe.set(f"pipe:batch:{i}", rand_str())
        pipe.execute()

    pipeline_latencies = []
    for _ in range(warmup_batches):
        try:
            pipelined()
        except Exception:
            pass

    pipeline_errors = 0
    for _ in range(batches):
        start = time.perf_counter()
        try:
            pipelined()
        except Exception:
            pipeline_errors += 1
        pipeline_latencies.append((time.perf_counter() - start) * 1000)

    result_pipelined = ScenarioResult(
        service=service,
        scenario=f"7_pipeline_batched_{N}ops",
        iterations=batches,
        errors=pipeline_errors,
        operations_per_iteration=N,
        latencies_ms=pipeline_latencies,
    )

    return [result_individual, result_pipelined]


# ─────────────────────────────────────────────────────────────────
# 시나리오 8: Pub/Sub (실제 Redis만 지원)
# ─────────────────────────────────────────────────────────────────

def scenario_pubsub(r_official: redis.Redis) -> ScenarioResult:
    """
    Publisher → Channel → Subscriber 메시지 전달 레이턴시 측정.

    측정 방법:
      - Subscriber 스레드가 채널을 구독
      - Publisher가 타임스탬프가 포함된 메시지 발행
      - Subscriber가 받은 시간 - 발행한 시간 = 전달 레이턴시

    주의: mini-redis는 기본 Pub/Sub 구조가 서버 내부에 있어
          이 시나리오는 redis-official로만 측정합니다.
    """
    channel = "bench:pubsub"
    received_times = []
    lock = threading.Lock()
    done = threading.Event()
    total_messages = CONFIG.pubsub_iterations

    def subscriber_thread():
        sub_client = redis.Redis(
            host=CONFIG.redis_official_host,
            port=CONFIG.redis_official_port,
            decode_responses=True,
            socket_timeout=CONFIG.socket_timeout_seconds,
        )
        pubsub = sub_client.pubsub()
        pubsub.subscribe(channel)
        count = 0
        for msg in pubsub.listen():
            if msg["type"] == "message":
                recv_ts = time.perf_counter()
                send_ts = float(msg["data"])
                latency_ms = (recv_ts - send_ts) * 1000
                with lock:
                    received_times.append(latency_ms)
                count += 1
                if count >= total_messages:
                    break
        done.set()
        pubsub.unsubscribe(channel)
        sub_client.close()

    t = threading.Thread(target=subscriber_thread, daemon=True)
    t.start()
    time.sleep(0.3)  # 구독자가 준비될 때까지 대기

    errors = 0
    for _ in range(total_messages):
        try:
            r_official.publish(channel, str(time.perf_counter()))
            time.sleep(0.001)  # 1ms 간격으로 발행
        except Exception:
            errors += 1

    done.wait(timeout=10)

    return ScenarioResult(
        service="redis-official",
        scenario="8_pubsub_e2e_latency",
        iterations=total_messages,
        errors=errors,
        latencies_ms=received_times,
    )


# ─────────────────────────────────────────────────────────────────
# 결과 출력 및 저장
# ─────────────────────────────────────────────────────────────────

def print_results(results: List[ScenarioResult]) -> None:
    """결과를 정렬된 테이블로 콘솔에 출력합니다."""
    col_w = [20, 38, 8, 8, 8, 8, 8, 14, 8]
    headers = ["Service", "Scenario", "N", "Err%", "Mean", "P50", "P95", "Throughput", "P99"]

    sep = "─" * (sum(col_w) + len(col_w) * 3 + 1)
    fmt = " │ ".join(f"{{:<{w}}}" for w in col_w)

    print()
    print("=" * len(sep))
    print("  mini-redis Benchmark Report")
    print("=" * len(sep))
    print("│ " + fmt.format(*headers) + " │")
    print(sep)

    # 시나리오 → 서비스 순으로 정렬
    for r in sorted(results, key=lambda x: (x.scenario, x.service)):
        row = fmt.format(
            r.service[:col_w[0]],
            r.scenario[:col_w[1]],
            str(r.iterations),
            f"{r.error_rate*100:.1f}%",
            f"{r.mean_ms:.3f}ms",
            f"{r.p50_ms:.3f}ms",
            f"{r.p95_ms:.3f}ms",
            f"{r.throughput_ops:.0f} ops/s",
            f"{r.p99_ms:.3f}ms",
        )
        print("│ " + row + " │")

    print(sep)
    print()


def save_results(results: List[ScenarioResult]) -> None:
    """결과를 JSON과 CSV로 저장합니다."""
    data = [r.to_dict() for r in results]

    # JSON
    json_path = "results/report.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  JSON 저장: {json_path}")

    # CSV
    csv_path = "results/report.csv"
    if data:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
    print(f"  CSV  저장: {csv_path}")


# ─────────────────────────────────────────────────────────────────
# 연결 초기화
# ─────────────────────────────────────────────────────────────────

def make_redis(host: str, port: int) -> redis.Redis:
    """RESP 디코딩을 활성화한 Redis 클라이언트 생성."""
    return redis.Redis(
        host=host,
        port=port,
        decode_responses=True,
        socket_timeout=CONFIG.socket_timeout_seconds,
    )


def wait_for_services(r_official, r_mini, mongo_client) -> None:
    """서비스가 준비될 때까지 대기합니다."""
    print("서비스 연결 대기 중...")
    for name, fn in [
        ("redis-official", lambda: r_official.ping()),
        ("mini-redis",     lambda: r_mini.ping()),
        ("mongodb",        lambda: mongo_client.admin.command("ping")),
    ]:
        for attempt in range(10):
            try:
                fn()
                print(f"  ✓ {name} 연결 성공")
                break
            except Exception as e:
                if attempt == 9:
                    print(f"  ✗ {name} 연결 실패: {e}")
                time.sleep(1)


# ─────────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────────

def main():
    # 클라이언트 초기화
    r_official = make_redis(CONFIG.redis_official_host, CONFIG.redis_official_port)
    r_mini     = make_redis(CONFIG.mini_redis_host, CONFIG.mini_redis_port)
    mongo      = MongoClient(
        host=CONFIG.mongo_host,
        port=CONFIG.mongo_port,
        serverSelectionTimeoutMS=int(CONFIG.socket_timeout_seconds * 1000),
    )
    mongo_db   = mongo["bench"]

    wait_for_services(r_official, r_mini, mongo)

    # 기존 데이터 초기화 (에페메럴이지만 재실행 시 정리)
    r_official.flushall()
    try:
        r_mini.flushall()
    except Exception as e:
        print(f"  ⚠ mini-redis FLUSHALL 미구현 (무시하고 계속): {e}")

    all_results: List[ScenarioResult] = []

    # 실행할 대상 서비스
    targets = [
        ("redis-official", r_official),
        ("mini-redis",     r_mini),
    ]

    print(
        f"\n총 {CONFIG.iterations}회 반복 "
        f"(warmup {CONFIG.warmup_iterations}회)으로 벤치마크를 시작합니다...\n"
    )

    # ── 시나리오 1: KV Cache ─────────────────────────────────────
    print("▶ 시나리오 1: KV Cache (GET/SET)")
    for svc, r in targets:
        all_results.append(scenario_kv_cache(r, svc))
        all_results.append(scenario_kv_cache_set(r, svc))
        print(f"    {svc} 완료")

    # ── 시나리오 2: Session Store ────────────────────────────────
    print("▶ 시나리오 2: Session Store (HSET/HGETALL)")
    for svc, r in targets:
        try:
            all_results.append(scenario_session_store(r, svc))
            print(f"    {svc} 완료")
        except Exception as e:
            print(f"    {svc} 스킵 (미구현): {e}")

    # ── 시나리오 3: Rate Limiting ────────────────────────────────
    print("▶ 시나리오 3: Rate Limiting (INCR+EXPIRE)")
    for svc, r in targets:
        try:
            all_results.append(scenario_rate_limiting(r, svc))
            print(f"    {svc} 완료")
        except Exception as e:
            print(f"    {svc} 스킵 (미구현): {e}")

    # ── 시나리오 4: Message Queue ────────────────────────────────
    print("▶ 시나리오 4: Message Queue (LPUSH/RPOP)")
    for svc, r in targets:
        try:
            all_results.append(scenario_message_queue_push(r, svc))
            all_results.append(scenario_message_queue_pop(r, svc))
            print(f"    {svc} 완료")
        except Exception as e:
            print(f"    {svc} 스킵 (미구현): {e}")

    # ── 시나리오 5: Leaderboard ──────────────────────────────────
    print("▶ 시나리오 5: Leaderboard (ZADD/ZREVRANGE)")
    for svc, r in targets:
        try:
            all_results.append(scenario_leaderboard(r, svc))
            print(f"    {svc} 완료")
        except Exception as e:
            print(f"    {svc} 스킵 (미구현): {e}")

    # ── 시나리오 6: Cache vs DB ──────────────────────────────────
    print("▶ 시나리오 6: Cache vs DB")
    for svc, r in targets:
        try:
            results_6 = scenario_cache_vs_db(r, mongo_db, svc)
            all_results.extend(results_6)
            print(f"    {svc} 완료")
        except Exception as e:
            print(f"    {svc} 스킵 (미구현): {e}")

    # ── 시나리오 7: Pipeline ─────────────────────────────────────
    print("▶ 시나리오 7: Pipeline vs Individual")
    for svc, r in targets:
        try:
            all_results.extend(scenario_pipeline(r, svc))
            print(f"    {svc} 완료")
        except Exception as e:
            print(f"    {svc} 스킵: {e}")

    # ── 시나리오 8: Pub/Sub (redis-official만) ───────────────────
    print("▶ 시나리오 8: Pub/Sub E2E Latency (redis-official only)")
    try:
        all_results.append(scenario_pubsub(r_official))
        print("    redis-official 완료")
    except Exception as e:
        print(f"    스킵: {e}")

    # ── 결과 출력 및 저장 ────────────────────────────────────────
    print_results(all_results)
    save_results(all_results)

    # 연결 종료
    r_official.close()
    r_mini.close()
    mongo.close()


if __name__ == "__main__":
    main()
