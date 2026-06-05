// Purpose: Declares NOAA inventory filter settings and station candidate output structures.

#ifndef NOAA_SORT_H
#define NOAA_SORT_H

#include <string>
#include <vector>

using namespace std;

struct InventoryFilterSettings {
    double minLatitude = 31.0;
    double maxLatitude = 43.5;
    double minLongitude = -115.0;
    double maxLongitude = -102.0;

    int targetMinimumYears = 8;
    int hubMinimumYears = 42;
    int hubMaximumStartYear = 1960;
    int requiredRecentEndYear = 2020;
};

struct StationInventory {
    string stationID;
    double latitude = 0.0;
    double longitude = 0.0;

    bool hasTMAX = false;
    bool hasTMIN = false;

    int tmaxStart = 0;
    int tmaxEnd = 0;
    int tminStart = 0;
    int tminEnd = 0;

    int usableTempStart = 0;
    int usableTempEnd = 0;
    int usableTempYears = 0;

    bool isTargetCandidate = false;
    bool isHubCandidate = false;
};

bool is_inside_bounds(
    double latitude,
    double longitude,
    const InventoryFilterSettings& settings
);

void calculate_usable_temperature_record(
    StationInventory& station
);

bool has_required_temperature_elements(
    const StationInventory& station
);

bool ends_recently_enough(
    const StationInventory& station,
    const InventoryFilterSettings& settings
);

bool qualifies_as_target_candidate(
    const StationInventory& station,
    const InventoryFilterSettings& settings
);

bool qualifies_as_hub_candidate(
    const StationInventory& station,
    const InventoryFilterSettings& settings
);

vector<StationInventory> load_station_inventory(
    const string& input_file
);

vector<StationInventory> filter_target_candidates(
    const vector<StationInventory>& stations,
    const InventoryFilterSettings& settings
);

vector<StationInventory> filter_hub_candidates(
    const vector<StationInventory>& stations,
    const InventoryFilterSettings& settings
);

void write_station_inventory_csv(
    const string& output_file,
    const vector<StationInventory>& stations
);

#endif
