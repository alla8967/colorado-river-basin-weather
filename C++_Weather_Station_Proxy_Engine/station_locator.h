// Purpose: Declares nearest-station lookup helpers for the engine API.

#ifndef STATION_LOCATOR_H
#define STATION_LOCATOR_H

#include <vector>

#include "station_dataset.h"

using namespace std;

const StationDataset* find_nearest_station(
    double latitude,
    double longitude,
    const vector<const StationDataset*>& stations
);

#endif
