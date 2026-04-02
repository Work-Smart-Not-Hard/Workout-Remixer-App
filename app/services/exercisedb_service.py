import httpx
import asyncio

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

class ExerciseDBService:
    _cache = []
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

            all_exercises = []
            offset = 0
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
            
            async with httpx.AsyncClient(timeout=180.0, headers=headers) as client:
                while True:
                    params = {"offset": offset, "limit": PAGE_SIZE}
                    items = []
                    success = False
                    
                    for attempt in range(6):
                        try:
                            response = await client.get(f"{EXERCISEDB_BASE}/exercises", params=params)
                            
                            if response.status_code == 429:
                                await asyncio.sleep((attempt + 1) * 3)
                                continue
                                
                            response.raise_for_status()
                            data = response.json()
                            items = data.get("data", []) if isinstance(data, dict) else data
                            success = True
                            break
                        except httpx.ReadTimeout:
                            await asyncio.sleep(2)
                            continue
                            
                    if not success:
                        raise Exception("Failed to fetch exercises from API after multiple retries.")
                    
                    if not items:
                        if offset == 0:
                            raise Exception("API returned 0 exercises on the first page. Server likely still booting DB.")
                        break

                    all_exercises.extend(items)
                    
                    if len(items) < PAGE_SIZE:
                        break
                        
                    offset += PAGE_SIZE

            self.__class__._cache = all_exercises
            return all_exercises
    
    async def get_exercises_page(self, search: str = "", offset: int = 0, limit: int = 100) -> dict:
        all_ex = await self._fetch_all_exercises()
        
        if search:
            search_lower = search.lower()
            all_ex = [ex for ex in all_ex if search_lower in ex.get("name", "").lower()]

        paginated = all_ex[offset : offset + limit]
        
        return {
            "data": paginated,
            "total": len(all_ex),
            "metadata": {"totalExercises": len(all_ex)}
        }

    async def get_exercise_by_id(self, exercise_id: str) -> dict | None:
        if self.__class__._cache:
            for ex in self.__class__._cache:
                if ex.get("exerciseId") == exercise_id or ex.get("id") == exercise_id:
                    return ex

        async with httpx.AsyncClient(timeout=60) as client:
            for attempt in range(5):
                response = await client.get(f"{EXERCISEDB_BASE}/exercises/{exercise_id}")
                
                if response.status_code == 404:
                    return None
                
                if response.status_code == 429:
                    await asyncio.sleep((attempt + 1) * 5)
                    continue
                    
                response.raise_for_status()
                data = response.json()
                return data.get("data") if isinstance(data, dict) else data
                
            response.raise_for_status()