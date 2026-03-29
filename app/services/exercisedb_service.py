import httpx

EXERCISEDB_BASE = "https://exercisedb-api-oe62.onrender.com/api/v1"
BATCH_SIZE = 100  # API hard limit per request

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

    async def _fetch_page(self, client: httpx.AsyncClient, params: dict) -> dict:
        response = await client.get(f"{EXERCISEDB_BASE}/exercises", params=params)
        response.raise_for_status()
        return response.json()

    async def get_all_exercises(self, search: str = "") -> list:
        """Fetch all exercises by paginating through the API in batches of 100."""
        all_exercises = []
        offset = 0

        async with httpx.AsyncClient(timeout=60) as client:
            # First page — tells us the total
            params: dict = {"offset": 0, "limit": BATCH_SIZE}
            if search:
                params["search"] = search

            first = await self._fetch_page(client, params)
            total = first.get("metadata", {}).get("totalExercises", 0)
            all_exercises.extend(first.get("data", []))

            # Fetch remaining pages
            offset = BATCH_SIZE
            while offset < total:
                params = {"offset": offset, "limit": BATCH_SIZE}
                if search:
                    params["search"] = search
                page = await self._fetch_page(client, params)
                all_exercises.extend(page.get("data", []))
                offset += BATCH_SIZE

        return all_exercises

    async def get_exercise_by_id(self, exercise_id: str) -> dict | None:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{EXERCISEDB_BASE}/exercises/{exercise_id}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("data")

    def get_muscles(self) -> list:
        return MUSCLES

    def get_equipments(self) -> list:
        return EQUIPMENTS