#ifndef STATION_LOCATOR_H
#define STATION_LOCATOR_H

#include <vector>

#include "station_dataset.h"

using namespace std;

StationDataset find_nearest_station(
    double latitude,
    double longitude,
    const vector<StationDataset>& stations
);

#endif
