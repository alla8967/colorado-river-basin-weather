// Purpose: Runs the C++ NOAA inventory filtering utility from the command line.



#include "noaa_sort.h"

#include <iostream>
#include <vector>

using namespace std;

int main() {
    const string input_file = "ghcnd-inventory.txt";
    const string target_output_file = "target_station_candidates.csv";
    const string hub_output_file = "hub_station_candidates.csv";

    InventoryFilterSettings settings;

    // Loose western U.S. / Colorado River Basin bounding box.
    settings.minLatitude = 31.0;
    settings.maxLatitude = 43.5;
    settings.minLongitude = -115.0;
    settings.maxLongitude = -102.0;

    // Candidate rules.
    settings.targetMinimumYears = 20;
    settings.hubMinimumYears = 42;
    settings.hubMaximumStartYear = 1960;
    settings.requiredRecentEndYear = 2020;

    cout << "NOAA INVENTORY FILTER TEST" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Input file: " << input_file << endl;
    cout << "Latitude bounds: " << settings.minLatitude << " to " << settings.maxLatitude << endl;
    cout << "Longitude bounds: " << settings.minLongitude << " to " << settings.maxLongitude << endl;
    cout << "Target minimum years: " << settings.targetMinimumYears << endl;
    cout << "Hub minimum years: " << settings.hubMinimumYears << endl;
    cout << "Hub latest allowed start year: " << settings.hubMaximumStartYear << endl;
    cout << "Required recent end year: " << settings.requiredRecentEndYear << endl;
    cout << "----------------------------------------" << endl;

    vector<StationInventory> all_stations = load_station_inventory(input_file);

    cout << "Stations loaded from inventory: " << all_stations.size() << endl;

    vector<StationInventory> target_candidates = filter_target_candidates(
        all_stations,
        settings
    );

    vector<StationInventory> hub_candidates = filter_hub_candidates(
        all_stations,
        settings
    );

    cout << "Target candidates found: " << target_candidates.size() << endl;
    cout << "Hub candidates found: " << hub_candidates.size() << endl;
    cout << "----------------------------------------" << endl;

    write_station_inventory_csv(target_output_file, target_candidates);
    write_station_inventory_csv(hub_output_file, hub_candidates);

    cout << "Wrote target candidates to: " << target_output_file << endl;
    cout << "Wrote hub candidates to: " << hub_output_file << endl;
    cout << "----------------------------------------" << endl;

    cout << "FIRST 10 HUB CANDIDATES" << endl;
    cout << "----------------------------------------" << endl;

    int hub_print_limit = 10;
    if (hub_candidates.size() < hub_print_limit) {
        hub_print_limit = hub_candidates.size();
    }

    for (int i = 0; i < hub_print_limit; i++) {
        const StationInventory& station = hub_candidates[i];

        cout << "Hub #" << i + 1 << endl;
        cout << "Station ID: " << station.stationID << endl;
        cout << "Latitude: " << station.latitude << endl;
        cout << "Longitude: " << station.longitude << endl;
        cout << "TMAX: " << station.tmaxStart << "-" << station.tmaxEnd << endl;
        cout << "TMIN: " << station.tminStart << "-" << station.tminEnd << endl;
        cout << "Usable temp period: " << station.usableTempStart << "-" << station.usableTempEnd << endl;
        cout << "Usable temp years: " << station.usableTempYears << endl;
        cout << "----------------------------------------" << endl;
    }

    cout << "Done." << endl;

    return 0;
}
