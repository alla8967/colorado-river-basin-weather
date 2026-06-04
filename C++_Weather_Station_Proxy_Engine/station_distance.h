#ifndef STATION_DISTANCE_H
#define STATION_DISTANCE_H

#include "station_dataset.h"

double degrees_to_radians(double degrees);

double calculate_haversine_distance_km(
    double lat_a,
    double lon_a,
    double lat_b,
    double lon_b
);

double calculate_station_distance_km(
    const StationMetadata& station_a,
    const StationMetadata& station_b
);

double calculate_elevation_difference(
    const StationMetadata& station_a,
    const StationMetadata& station_b
);

#endif