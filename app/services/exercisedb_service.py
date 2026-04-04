import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

EXERCISEDB_BASE = "https://exercisedb-api-oe62.onrender.com/api/v1"
PAGE_SIZE = 100

MUSCLES = sorted([
    "abs", "abdominals", "abductors", "adductors", "ankles", "ankle stabilizers",
    "back", "biceps", "brachialis", "calves", "cardiovascular system", "chest",
    "core", "delts", "deltoids", "feet", "forearms", "glutes", "grip muscles",
    "groin", "hamstrings", "hands", "hip flexors", "inner thighs", "lats",
    "latissimus dorsi", "levator scapulae", "lower abs", "lower back", "obliques",
    "pectorals", "quadriceps", "quads", "rear deltoids", "rhomboids", "rotator cuff",
    "serratus anterior", "shins", "shoulders", "soleus", "spine",
    "sternocleidomastoid", "traps", "trapezius", "triceps", "upper back",
    "upper chest", "wrist extensors", "wrist flexors", "wrists",
])

EQUIPMENTS = sorted([
    "assisted", "band", "barbell", "body weight", "bosu ball", "cable",
    "dumbbell", "elliptical machine", "ez barbell", "hammer", "kettlebell",
    "leverage machine", "medicine ball", "olympic barbell", "resistance band",
    "roller", "rope", "sled machine", "skierg machine", "smith machine",
    "stability ball", "stationary bike", "stepmill machine", "tire", "trap bar",
    "upper body ergometer", "weighted", "wheel roller",
])

_WAKE_RETRY_DELAYS = [5, 10, 15, 20, 30, 30, 30, 30, 30, 30]


class ExerciseDBService:
    _cache: list = []
    _fetch_lock = asyncio.Lock()

    def get_muscles(self) -> list[str]:
        return MUSCLES

    def get_equipments(self) -> list[str]:
        return EQUIPMENTS

    async def _ping_until_alive(self, client: httpx.AsyncClient) -> bool:
        """
        Send lightweight requests to the ExerciseDB service until it responds
        with a real HTTP status (not a connection error / timeout).
        This is what actually wakes up the Render free-tier instance.
        Returns True once the server is alive, False if we exhausted all attempts.
        """
        url = f"{EXERCISEDB_BASE}/exercises"
        params = {"offset": 0, "limit": 1}

        for attempt, delay in enumerate(_WAKE_RETRY_DELAYS, start=1):
            try:
                response = await client.get(url, params=params)
                if response.status_code == 429:
                    logger.info(f"ExerciseDB alive (rate-limited) on wake attempt {attempt}")
                    return True
                if response.status_code < 500:
                    logger.info(f"ExerciseDB alive (status {response.status_code}) on wake attempt {attempt}")
                    return True
                logger.warning(f"ExerciseDB returned {response.status_code} on wake attempt {attempt}, retrying in {delay}s…")
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError) as exc:
                logger.info(f"ExerciseDB not yet reachable (attempt {attempt}/{len(_WAKE_RETRY_DELAYS)}): {exc!r}. Waiting {delay}s…")
            except Exception as exc:
                logger.warning(f"Unexpected error during ExerciseDB wake ping (attempt {attempt}): {exc!r}")

            await asyncio.sleep(delay)

        logger.error("ExerciseDB did not come online after all wake attempts.")
        return False

    async def _fetch_all_exercises(self) -> list:
        """Fetch every exercise from ExerciseDB and store in the class-level cache."""
        if self.__class__._cache:
            return self.__class__._cache

        async with self.__class__._fetch_lock:
            if self.__class__._cache:
                return self.__class__._cache

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }

            async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:

                alive = await self._ping_until_alive(client)
                if not alive:
                    raise Exception(
                        "ExerciseDB API did not come online. "
                        "It may still be cold-starting — the next request will retry."
                    )

                all_exercises: list = []
                offset = 0

                while True:
                    params = {"offset": offset, "limit": PAGE_SIZE}
                    items: list = []
                    success = False

                    for attempt in range(8):
                        try:
                            response = await client.get(
                                f"{EXERCISEDB_BASE}/exercises", params=params
                            )

                            if response.status_code == 429:
                                wait = (attempt + 1) * 5
                                logger.info(f"Rate-limited on page offset={offset}, waiting {wait}s…")
                                await asyncio.sleep(wait)
                                continue

                            response.raise_for_status()
                            data = response.json()
                            items = (
                                data.get("data", []) if isinstance(data, dict) else data
                            )
                            success = True
                            break

                        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
                            wait = (attempt + 1) * 5
                            logger.warning(f"Timeout fetching offset={offset} (attempt {attempt+1}): {exc!r}. Retrying in {wait}s…")
                            await asyncio.sleep(wait)

                        except Exception as exc:
                            logger.error(f"Unexpected error fetching offset={offset}: {exc!r}")
                            break

                    if not success:
                        raise Exception(
                            f"Failed to fetch exercises from ExerciseDB at offset={offset} after multiple retries."
                        )

                    if not items:
                        if offset == 0:
                            raise Exception(
                                "ExerciseDB returned 0 exercises on the first page — "
                                "the server may still be initialising its database."
                            )
                        break

                    all_exercises.extend(items)
                    logger.info(f"Fetched {len(all_exercises)} exercises so far (offset={offset})…")

                    if len(items) < PAGE_SIZE:
                        break

                    offset += PAGE_SIZE

            self.__class__._cache = all_exercises
            logger.info(f"ExerciseDB cache populated with {len(all_exercises)} exercises.")
            return all_exercises

    async def get_exercises_page(
        self, search: str = "", offset: int = 0, limit: int = 100
    ) -> dict:
        all_ex = await self._fetch_all_exercises()

        if search:
            search_lower = search.lower()
            all_ex = [ex for ex in all_ex if search_lower in ex.get("name", "").lower()]

        paginated = all_ex[offset: offset + limit]

        return {
            "data": paginated,
            "total": len(all_ex),
            "metadata": {"totalExercises": len(all_ex)},
        }

    async def get_exercise_by_id(self, exercise_id: str) -> dict | None:
        if self.__class__._cache:
            for ex in self.__class__._cache:
                if ex.get("exerciseId") == exercise_id or ex.get("id") == exercise_id:
                    return ex

        async with httpx.AsyncClient(timeout=60.0) as client:
            for attempt in range(5):
                try:
                    response = await client.get(
                        f"{EXERCISEDB_BASE}/exercises/{exercise_id}"
                    )

                    if response.status_code == 404:
                        return None

                    if response.status_code == 429:
                        await asyncio.sleep((attempt + 1) * 5)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    return data.get("data") if isinstance(data, dict) else data

                except (httpx.ReadTimeout, httpx.ConnectTimeout):
                    await asyncio.sleep((attempt + 1) * 5)

            return None