DEFAULT_MET = 5.0

SECONDS_PER_REP = 4

DEFAULT_REST_SECONDS = 60


def estimate_duration_seconds(
    sets: int, 
    reps: int, 
    rest_seconds: int = DEFAULT_REST_SECONDS
    ) -> float:
 
    if sets <= 0 or reps <= 0:
        return 0.0

    active_time = sets * reps * SECONDS_PER_REP
    rest_time = (sets - 1) * rest_seconds
    return float(active_time + rest_time)


def calculate_calories(
    weight_kg: float,
    duration_seconds: float,
    met: float = DEFAULT_MET,
) -> float:

    if weight_kg <= 0 or duration_seconds <= 0:
        return 0.0

    duration_hours = duration_seconds / 3600.0
    calories = met * weight_kg * duration_hours
    return round(calories, 2)


def calculate_session_calories(
    weight_kg: float | None,
    duration_minutes: int | None,
    sets: int | None = None,
    reps: int | None = None,
    rest_seconds: int = DEFAULT_REST_SECONDS,
) -> float:
    
    if not weight_kg:
        return 0.0

    if duration_minutes and duration_minutes > 0:
        duration_seconds = duration_minutes * 60.0
    elif sets and reps:
        duration_seconds = estimate_duration_seconds(sets, reps, rest_seconds)
    else:
        return 0.0

    return calculate_calories(weight_kg=weight_kg, duration_seconds=duration_seconds)