#include "station_dataset.h"

#include <algorithm>
#include <fstream>
#include <map>
#include <iostream>

using namespace std;

bool is_daily_dataset_sorted(const vector<DailyData>& input) {
    for (int i = 1; i < static_cast<int>(input.size()); i++) {
        if (input[i - 1].year > input[i].year) {
            return false;
        }

        if (input[i - 1].year == input[i].year &&
            input[i - 1].month > input[i].month) {
            return false;
        }

        if (input[i - 1].year == input[i].year &&
            input[i - 1].month == input[i].month &&
            input[i - 1].day > input[i].day) {
            return false;
        }
    }

    return true;
}

void sort_daily_dataset_if_needed(vector<DailyData>& input) {
    if (!is_daily_dataset_sorted(input)) {
        input = sort_daily_dataset(input);
    }
}

StationMetadata extract_station_metadata(const vector<string>& row) {
    StationMetadata metadata;

    metadata.stationID = "";
    metadata.stationName = "";
    metadata.latitude = MISSING;
    metadata.longitude = MISSING;
    metadata.elevation = MISSING;
    metadata.has_geo_data = false;

    if (row.size() < 5) {
        return metadata;
    }

    metadata.stationID = row[0];
    metadata.stationName = row[1];

    metadata.stationID.erase(remove(metadata.stationID.begin(), metadata.stationID.end(), '"'), metadata.stationID.end());
    metadata.stationName.erase(remove(metadata.stationName.begin(), metadata.stationName.end(), '"'), metadata.stationName.end());
    metadata.stationID.erase(remove(metadata.stationID.begin(), metadata.stationID.end(), '\r'), metadata.stationID.end());
    metadata.stationName.erase(remove(metadata.stationName.begin(), metadata.stationName.end(), '\r'), metadata.stationName.end());

    metadata.latitude = valid_stod(row[2]);
    metadata.longitude = valid_stod(row[3]);
    metadata.elevation = valid_stod(row[4]);

    metadata.has_geo_data =
        metadata.latitude != MISSING &&
        metadata.longitude != MISSING &&
        metadata.elevation != MISSING;

    return metadata;
}

StationMetadata extract_app_ready_temperature_station_metadata(const DailyData& day) {
    StationMetadata metadata;

    metadata.stationID = day.stationID;
    metadata.stationName = day.stationName;
    metadata.latitude = day.latitude;
    metadata.longitude = day.longitude;
    metadata.elevation = day.elevation;

    metadata.has_geo_data =
        metadata.latitude != MISSING &&
        metadata.longitude != MISSING &&
        metadata.elevation != MISSING;

    return metadata;
}

StationDataset load_station_dataset(const string& input_file) {
    StationDataset station;
    station.input_file = input_file;
    station.valid = false;

    vector<string> lines = grab_data(input_file);

    if (lines.size() <= 1) {
        cerr << "No usable data found in " << input_file << endl;
        return station;
    }
    vector<string> first_data_row = parse_data(lines[1]);
    station.metadata = extract_station_metadata(first_data_row);

    station.daily = create_daily_dataset(lines);

    if (station.daily.size() == 0) {
        cerr << "Daily dataset is empty for " << input_file << endl;
        return station;
    }

    sort_daily_dataset_if_needed(station.daily);
    station.monthly = create_monthly_dataset(station.daily);

    if (station.monthly.size() == 0) {
        cerr << "Monthly dataset is empty for " << input_file << endl;
        return station;
    }

    station.seasonal = compute_seasonal_data(station.monthly);

    station.valid = true;
    return station;
}

StationDataset load_app_ready_temperature_station_dataset(const string& input_file) {
    StationDataset station;
    station.input_file = input_file;
    station.valid = false;

    vector<string> lines = grab_data(input_file);

    if (lines.size() <= 1) {
        cerr << "No usable app-ready temperature data found in " << input_file << endl;
        return station;
    }

    station.daily = create_app_ready_temperature_dataset(lines);

    if (station.daily.size() == 0) {
        cerr << "App-ready temperature daily dataset is empty for " << input_file << endl;
        return station;
    }

    station.metadata = extract_app_ready_temperature_station_metadata(station.daily[0]);

    sort_daily_dataset_if_needed(station.daily);
    station.monthly = create_monthly_dataset(station.daily);

    if (station.monthly.size() == 0) {
        cerr << "Monthly dataset is empty for app-ready temperature file " << input_file << endl;
        return station;
    }

    station.seasonal = compute_seasonal_data(station.monthly);

    station.valid = true;
    return station;
}

vector<StationDataset> load_station_datasets(const string& input_file) {
    map<string, StationDataset> stations_by_id;

    ifstream file(input_file);

    if (!file.is_open()) {
        cerr << "Could not open input file: " << input_file << endl;
        return vector<StationDataset>();
    }

    string header;
    getline(file, header);

    if (header == "") {
        cerr << "No usable lines found in input file: " << input_file << endl;
        return vector<StationDataset>();
    }

    string line;

    int total_rows_read = 0;
    int malformed_rows = 0;
    int empty_station_id_rows = 0;
    int invalid_daily_rows = 0;
    int valid_daily_rows = 0;

    while (getline(file, line)) {
        total_rows_read++;

        vector<string> row = parse_data(line);

        if (row.size() < 1) {
            malformed_rows++;
            continue;
        }

        string stationID = row[0];
        stationID.erase(remove(stationID.begin(), stationID.end(), '"'), stationID.end());
        stationID.erase(remove(stationID.begin(), stationID.end(), '\r'), stationID.end());

        if (stationID == "") {
            empty_station_id_rows++;
            continue;
        }

        DailyData day = stoDD(row);

        if (!day.valid) {
            invalid_daily_rows++;
            continue;
        }

        valid_daily_rows++;

        if (stations_by_id.find(stationID) == stations_by_id.end()) {
            StationDataset station;
            station.input_file = input_file;
            station.valid = false;
            station.metadata = extract_station_metadata(row);

            stations_by_id[stationID] = station;
        }

        stations_by_id[stationID].daily.push_back(day);
    }

    vector<StationDataset> stations;
    stations.reserve(stations_by_id.size());

    for (auto& station_pair : stations_by_id) {
        StationDataset& station = station_pair.second;

        if (station.daily.size() == 0) {
            cerr << "Daily dataset is empty for station " << station_pair.first << endl;
            continue;
        }

        sort_daily_dataset_if_needed(station.daily);
        station.monthly = create_monthly_dataset(station.daily);

        if (station.monthly.size() == 0) {
            cerr << "Monthly dataset is empty for station " << station_pair.first << endl;
            continue;
        }

        station.seasonal = compute_seasonal_data(station.monthly);
        station.valid = true;

        stations.push_back(std::move(station));
    }

    cerr << endl;
    cerr << "LOAD DIAGNOSTICS" << endl;
    cerr << "----------------------------------------" << endl;
    cerr << "Input file: " << input_file << endl;
    cerr << "Total data rows read: " << total_rows_read << endl;
    cerr << "Valid daily rows stored: " << valid_daily_rows << endl;
    cerr << "Malformed rows skipped: " << malformed_rows << endl;
    cerr << "Rows with empty station ID skipped: " << empty_station_id_rows << endl;
    cerr << "Invalid daily rows skipped: " << invalid_daily_rows << endl;
    cerr << "Stations found: " << stations_by_id.size() << endl;
    cerr << "Stations returned: " << stations.size() << endl;
    cerr << "----------------------------------------" << endl;

    return stations;
}

vector<StationDataset> load_app_ready_temperature_station_datasets(const string& input_file) {
    map<string, StationDataset> stations_by_id;

    ifstream file(input_file);

    if (!file.is_open()) {
        cerr << "Could not open app-ready temperature input file: " << input_file << endl;
        return vector<StationDataset>();
    }

    string header;
    getline(file, header);

    if (header == "") {
        cerr << "No usable lines found in app-ready temperature input file: " << input_file << endl;
        return vector<StationDataset>();
    }

    string line;

    int total_rows_read = 0;
    int malformed_rows = 0;
    int empty_station_id_rows = 0;
    int invalid_daily_rows = 0;
    int valid_daily_rows = 0;

    while (getline(file, line)) {
        total_rows_read++;

        DailyData day = stoDD_app_ready_temperature_line(line);

        if (!day.valid) {
            invalid_daily_rows++;
            continue;
        }

        string stationID = day.stationID;

        if (stationID == "") {
            empty_station_id_rows++;
            continue;
        }

        valid_daily_rows++;

        if (stations_by_id.find(stationID) == stations_by_id.end()) {
            StationDataset station;
            station.input_file = input_file;
            station.valid = false;
            station.metadata = extract_app_ready_temperature_station_metadata(day);

            stations_by_id[stationID] = station;
        }

        stations_by_id[stationID].daily.push_back(day);
    }

    vector<StationDataset> stations;
    stations.reserve(stations_by_id.size());

    for (auto& station_pair : stations_by_id) {
        StationDataset& station = station_pair.second;

        if (station.daily.size() == 0) {
            cerr << "Daily dataset is empty for app-ready temperature station " << station_pair.first << endl;
            continue;
        }

        sort_daily_dataset_if_needed(station.daily);
        station.valid = true;

        stations.push_back(std::move(station));
    }

    cerr << endl;
    cerr << "APP-READY TEMPERATURE LOAD DIAGNOSTICS" << endl;
    cerr << "----------------------------------------" << endl;
    cerr << "Input file: " << input_file << endl;
    cerr << "Total data rows read: " << total_rows_read << endl;
    cerr << "Valid daily rows stored: " << valid_daily_rows << endl;
    cerr << "Malformed rows skipped: " << malformed_rows << endl;
    cerr << "Rows with empty station ID skipped: " << empty_station_id_rows << endl;
    cerr << "Invalid daily rows skipped: " << invalid_daily_rows << endl;
    cerr << "Stations found: " << stations_by_id.size() << endl;
    cerr << "Stations returned: " << stations.size() << endl;
    cerr << "----------------------------------------" << endl;

    return stations;
}
