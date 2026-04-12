"""
Health platform integration stubs for the Workout Remixer App.

These functions are structural placeholders only.
No real API calls are made. No external SDKs are imported.

Intended future integrations:
  - Health Connect (Android 14+)
  - Apple HealthKit (iOS)

To activate either integration, the relevant platform SDK and
authentication flow must be implemented before calling these functions.
"""

from app.models.models import WorkoutSession


def export_to_health_connect(session: WorkoutSession) -> None:
    """
    Placeholder for exporting a completed workout session to
    Google Health Connect (Android).

    DATA THAT WOULD BE SENT:
      - session.calories_burned     → ExerciseSessionRecord / TotalCaloriesBurnedRecord
      - session.duration_minutes    → Session duration
      - session.started_at          → Session start time
      - session.completed_at        → Session end time
      - routine name (via session.routine) → Exercise type label

    PLATFORM REQUIREMENTS:
      - Android 14+ (API level 34) or Health Connect APK on Android 9+
      - Health Connect SDK: androidx.health.connect:connect-client
      - Manifest permissions:
          android.permission.health.READ_EXERCISE
          android.permission.health.WRITE_EXERCISE
          android.permission.health.WRITE_TOTAL_CALORIES_BURNED
      - User must grant runtime permissions via Health Connect consent screen
      - App must be the holder of the data write permission for that record type

    AUTHENTICATION:
      - No OAuth required for local device writes
      - Permissions are granted per-app by the user via the Health Connect app
      - Revocable at any time by the user

    IMPLEMENTATION NOTES:
      - This would require a native Android component or a cross-platform
        bridge (e.g. Capacitor plugin: @capacitor-community/health)
      - The FastAPI backend would need to receive a device token or
        delegate the write to the mobile client directly

    TODO:
      - Accept a device/session token from the mobile client
      - Serialize session data into Health Connect record format
      - POST serialized data to the mobile client or a bridge endpoint
    """
    pass


def export_to_healthkit(session: WorkoutSession) -> None:
    """
    Placeholder for exporting a completed workout session to
    Apple HealthKit (iOS).

    DATA THAT WOULD BE SENT:
      - session.calories_burned     → HKQuantityTypeIdentifierActiveEnergyBurned
      - session.duration_minutes    → Workout duration
      - session.started_at          → HKWorkout startDate
      - session.completed_at        → HKWorkout endDate
      - routine name (via session.routine) → HKWorkoutActivityType label

    PLATFORM REQUIREMENTS:
      - iOS 8+ (HealthKit framework)
      - Xcode entitlement: com.apple.developer.healthkit
      - Info.plist keys:
          NSHealthShareUsageDescription
          NSHealthUpdateUsageDescription
      - User must grant read/write permissions via iOS HealthKit authorization sheet
      - App must be distributed via App Store or TestFlight (HealthKit not
        available in simulator for production data)

    AUTHENTICATION:
      - No OAuth required for on-device writes
      - Permissions are granted per data type by the user via iOS Settings
      - Revocable at any time via Settings → Privacy → Health

    IMPLEMENTATION NOTES:
      - This would require a native iOS component or a cross-platform
        bridge (e.g. Capacitor plugin: @capacitor-community/health)
      - The FastAPI backend would need to delegate the HealthKit write
        to the iOS client, as HealthKit only allows on-device access
      - Server-side HealthKit writes are not supported by Apple

    TODO:
      - Accept a device/session token from the iOS client
      - Serialize session data into HealthKit quantity sample format
      - Send serialized payload to the iOS client for local HealthKit write
    """
    pass