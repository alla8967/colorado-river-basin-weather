// Purpose: Finds the nearest target station to a requested latitude/longitude.

#include "station_locator.h"
#include "station_distance.h"

#include <limits>
#include <vector>

using namespace std;

StationDataset find_nearest_station(
    double latitude,
    double longitude,
    const vector<StationDataset>& stations
) {
    StationDataset output;

    if (stations.size() == 0) {
        return output;
    }

    double min_dist = numeric_limits<double>::max();

    for (int i = 0; i < stations.size(); i++) {
        double temp_dist = calculate_haversine_distance_km(
            latitude,
            longitude,
            stations[i].metadata.latitude,
            stations[i].metadata.longitude
        );

        if (temp_dist < min_dist) {
            min_dist = temp_dist;
            output = stations[i];
        }
    }

    return output;
}