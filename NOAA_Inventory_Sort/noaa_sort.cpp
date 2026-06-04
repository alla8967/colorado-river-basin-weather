#include "noaa_sort.h"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>

using namespace std;

bool is_inside_bounds(
    double latitude,
    double longitude,
    const InventoryFilterSettings& settings
) {
    return latitude >= settings.minLatitude &&
           latitude <= settings.maxLatitude &&
           longitude >= settings.minLongitude &&
           longitude <= settings.maxLongitude;
}

void calculate_usable_temperature_record(StationInventory& station) {
    if (!station.hasTMAX || !station.hasTMIN) {
        station.usableTempStart = 0;
        station.usableTempEnd = 0;
        station.usableTempYears = 0;
        return;
    }

    station.usableTempStart = max(station.tmaxStart, station.tminStart);
    station.usableTempEnd = min(station.tmaxEnd, station.tminEnd);
    station.usableTempYears = station.usableTempEnd - station.usableTempStart + 1;

    if (station.usableTempYears < 0) {
        station.usableTempYears = 0;
    }
}

bool has_required_temperature_elements(const StationInventory& station) {
    return station.hasTMAX && station.hasTMIN;
}

bool ends_recently_enough(
    const StationInventory& station,
    const InventoryFilterSettings& settings
) {
    return station.usableTempEnd >= settings.requiredRecentEndYear;
}

bool qualifies_as_target_candidate(
    const StationInventory& station,
    const InventoryFilterSettings& settings
) {
    if (!has_required_temperature_elements(station)) {
        return false;
    }

    if (!is_inside_bounds(station.latitude, station.longitude, settings)) {
        return false;
    }

    if (!ends_recently_enough(station, settings)) {
        return false;
    }

    return station.usableTempYears >= settings.targetMinimumYears;
}

bool qualifies_as_hub_candidate(
    const StationInventory& station,
    const InventoryFilterSettings& settings
) {
    if (!has_required_temperature_elements(station)) {
        return false;
    }

    if (!is_inside_bounds(station.latitude, station.longitude, settings)) {
        return false;
    }

    if (!ends_recently_enough(station, settings)) {
        return false;
    }

    if (station.usableTempStart > settings.hubMaximumStartYear) {
        return false;
    }

    return station.usableTempYears >= settings.hubMinimumYears;
}

vector<StationInventory> load_station_inventory(const string& input_file) {

    ifstream file(input_file);
    map<string, StationInventory> station_map;

    if (!file.is_open()) {
        cerr << "Could not open inventory file: " << input_file << endl;
        return {};
    }

    string stationID;
    double latitude;
    double longitude;
    string element;
    int startYear;
    int endYear;

    while (file >> stationID >> latitude >> longitude >> element >> startYear >> endYear) {
        StationInventory& station = station_map[stationID];

        station.stationID = stationID;
        station.latitude = latitude;
        station.longitude = longitude;

        if (element == "TMAX") {
            station.hasTMAX = true;
            station.tmaxStart = startYear;
            station.tmaxEnd = endYear;
        } else if (element == "TMIN") {
            station.hasTMIN = true;
            station.tminStart = startYear;
            station.tminEnd = endYear;
        }
    }

    vector<StationInventory> stations;

    for (auto& pair : station_map) {
        StationInventory station = pair.second;
        calculate_usable_temperature_record(station);
        stations.push_back(station);
    }

    return stations;
}

vector<StationInventory> filter_target_candidates(
    const vector<StationInventory>& stations,
    const InventoryFilterSettings& settings
) {
    vector<StationInventory> candidates;

    for (StationInventory station : stations) {
        station.isTargetCandidate = qualifies_as_target_candidate(station, settings);
        station.isHubCandidate = qualifies_as_hub_candidate(station, settings);

        if (station.isTargetCandidate && !station.isHubCandidate) {
            candidates.push_back(station);
        }
    }

    return candidates;
}

vector<StationInventory> filter_hub_candidates(
    const vector<StationInventory>& stations,
    const InventoryFilterSettings& settings
) {
    vector<StationInventory> candidates;

    for (StationInventory station : stations) {
        station.isTargetCandidate = qualifies_as_target_candidate(station, settings);
        station.isHubCandidate = qualifies_as_hub_candidate(station, settings);

        if (station.isHubCandidate) {
            candidates.push_back(station);
        }
    }

    return candidates;
}

void write_station_inventory_csv(
    const string& output_file,
    const vector<StationInventory>& stations
) {
    ofstream file(output_file);

    if (!file.is_open()) {
        cerr << "Could not open output file: " << output_file << endl;
        return;
    }

    file << "station_id,latitude,longitude,has_tmax,has_tmin,";
    file << "tmax_start,tmax_end,tmin_start,tmin_end,";
    file << "usable_temp_start,usable_temp_end,usable_temp_years,";
    file << "is_target_candidate,is_hub_candidate\n";

    for (const StationInventory& station : stations) {
        file << station.stationID << ",";
        file << station.latitude << ",";
        file << station.longitude << ",";
        file << station.hasTMAX << ",";
        file << station.hasTMIN << ",";
        file << station.tmaxStart << ",";
        file << station.tmaxEnd << ",";
        file << station.tminStart << ",";
        file << station.tminEnd << ",";
        file << station.usableTempStart << ",";
        file << station.usableTempEnd << ",";
        file << station.usableTempYears << ",";
        file << station.isTargetCandidate << ",";
        file << station.isHubCandidate << "\n";
    }
}
