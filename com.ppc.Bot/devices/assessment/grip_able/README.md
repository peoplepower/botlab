# Grip-Able Device Class

[Grip-Able Able-Assess](https://www.able-care.co/solutions/able-assess/) is a functional health assessment platform that measures falls risk and functional capacity through standardized clinical assessments.

## Measurements

| Parameter | Description |
|---|---|
| `able.4gs` | **4-Meter Gait Speed Test** - Walking speed over 4 meters to assess mobility and functional decline (seconds) |
| `able.atRisk` | **At Risk** - Indicates if the person is at risk based on assessment results |
| `able.cst` | **Chair Stand Test** - Lower body strength and functional capacity through sit-to-stand repetitions (seconds) |
| `able.smgt` | **Single Maximum Grip Strength Test** - Hand grip force as a biomarker for overall health and biological aging (kg) |
| `able.tug` | **Timed Up and Go Test** - Mobility and fall risk assessed by timing a rise-walk-return sequence (seconds) |

## Device Assignment

Each Grip-Able device has a `user_id` attribute that references a user with role 1 (resident). The assigned user must have a birthdate and gender defined in their profile, as these are required to contextualize assessment results against clinical norms.
