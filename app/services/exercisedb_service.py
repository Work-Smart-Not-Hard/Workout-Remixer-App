import httpx
import asyncio

EXERCISEDB_BASE = "https://exercisedb-api-oe62.onrender.com/api/v1"
PAGE_SIZE = 100  # API hard limit

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

    async def get_exercises_page(self, search: str = "", offset: int = 0) -> dict:
        """
        Fetch a single page of 100 exercises.
        Returns the full API response including metadata so the frontend
        can handle pagination itself.
        """
        params: dict = {"offset": offset, "limit": PAGE_SIZE}
        if search:
            params["search"] = search

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(f"{EXERCISEDB_BASE}/exercises", params=params)
            response.raise_for_status()
            return response.json()

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