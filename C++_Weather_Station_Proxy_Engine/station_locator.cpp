// Purpose: Finds the nearest target station to a requested latitude/longitude.

#include "station_locator.h"
#include "station_distance.h"

#include <limits>
#include <vector>

using namespace std;

const StationDataset* find_nearest_station(
    double latitude,
    double longitude,
    const vector<const StationDataset*>& stations
) {
    if (stations.size() == 0) {
        return nullptr;
    }

    double min_dist = numeric_limits<double>::max();
    const StationDataset* nearest_station = nullptr;

    for (int i = 0; i < stations.size(); i++) {
        if (stations[i] == nullptr) {
            continue;
        }

        double temp_dist = calculate_haversine_distance_km(
            latitude,
            longitude,
            stations[i]->metadata.latitude,
            stations[i]->metadata.longitude
        );

        if (temp_dist < min_dist) {
            min_dist = temp_dist;
            nearest_station = stations[i];
        }
    }

    return nearest_station;
}
