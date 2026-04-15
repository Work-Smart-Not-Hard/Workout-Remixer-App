import httpx
import asyncio
import logging

logger = logging.getLogger(__name__)

EXERCISEDB_BASE = "https://exercisedb-api-cmwf.onrender.com/api/v1"
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


class ExerciseDBService:
    _cache: list = []
    _fetch_lock = asyncio.Lock()

    def get_muscles(self) -> list[str]:
        return MUSCLES

    def get_equipments(self) -> list[str]:
        return EQUIPMENTS

    async def _fetch_all_exercises(self) -> list:
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

            all_exercises: list = []
            offset = 0

            async with httpx.AsyncClient(timeout=60.0, headers=headers) as client:
                while True:
                    params = {"offset": offset, "limit": PAGE_SIZE}
                    items: list = []
                    success = False

                    for attempt in range(5):
                        try:
                            response = await client.get(
                                f"{EXERCISEDB_BASE}/exercises", params=params
                            )
                            if response.status_code == 429:
                                wait = (attempt + 1) * 5
                                logger.info(f"Rate-limited at offset={offset}, retrying in {wait}s…")
                                await asyncio.sleep(wait)
                                continue
                            response.raise_for_status()
                            data = response.json()
                            items = data.get("data", []) if isinstance(data, dict) else data
                            success = True
                            break
                        except (httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
                            wait = (attempt + 1) * 5
                            logger.warning(f"Timeout at offset={offset} (attempt {attempt + 1}): {exc!r}. Retrying in {wait}s…")
                            await asyncio.sleep(wait)
                        except Exception as exc:
                            logger.error(f"Error fetching offset={offset}: {exc!r}")
                            break

                    if not success:
                        logger.warning(
                            "ExerciseDB fetch failed at offset=%s after retries; "
                            "falling back to cached data (%s items).",
                            offset,
                            len(self.__class__._cache),
                        )
                        return self.__class__._cache or []

                    if not items:
                        if offset == 0:
                            logger.warning(
                                "ExerciseDB returned 0 exercises at offset=0; "
                                "falling back to cached data (%s items).",
                                len(self.__class__._cache),
                            )
                            return self.__class__._cache or []
                        break

                    all_exercises.extend(items)
                    logger.info(f"Cached {len(all_exercises)} exercises (offset={offset})…")

                    if len(items) < PAGE_SIZE:
                        break

                    offset += PAGE_SIZE

            self.__class__._cache = all_exercises
            logger.info(f"ExerciseDB cache ready: {len(all_exercises)} exercises.")
            return all_exercises

        return self.__class__._cache or []

    async def get_exercises_page(
        self, search: str = "", offset: int = 0, limit: int = 100
    ) -> dict:
        try:
            all_ex = await self._fetch_all_exercises()
        except Exception as exc:
            logger.warning(
                "ExerciseDB page fetch failed; using cache fallback (%s items): %r",
                len(self.__class__._cache),
                exc,
            )
            all_ex = self.__class__._cache or []

        if search:
            search_lower = search.lower()
            all_ex = [ex for ex in all_ex if search_lower in ex.get("name", "").lower()]

        return {
            "data": all_ex[offset: offset + limit],
            "total": len(all_ex),
            "metadata": {"totalExercises": len(all_ex)},
        }

    async def get_exercise_by_id(self, exercise_id: str) -> dict | None:
        if self.__class__._cache:
            for ex in self.__class__._cache:
                if ex.get("exerciseId") == exercise_id or ex.get("id") == exercise_id:
                    return ex

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                for attempt in range(5):
                    try:
                        response = await client.get(f"{EXERCISEDB_BASE}/exercises/{exercise_id}")
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
        except Exception as exc:
            logger.warning("ExerciseDB detail fetch failed for %s: %r", exercise_id, exc)
        return None