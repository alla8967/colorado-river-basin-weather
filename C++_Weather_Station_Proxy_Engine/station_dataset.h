// Purpose: Declares station metadata, daily rows, and dataset containers used throughout the engine.

#ifndef STATION_DATASET_H
#define STATION_DATASET_H

#include <string>
#include <vector>

#include "csv_filereader.h"
#include "seasonal_analysis.h"

using namespace std;

struct StationMetadata {
    string stationID;
    string stationName;

    double latitude;
    double longitude;
    double elevation;

    bool has_geo_data;

    int fullObservationStartYear = 0;
    int fullObservationEndYear = 0;
    int fullObservationYears = 0;
};

struct StationDataset {
    string input_file;

    StationMetadata metadata;

    vector<DailyData> daily;
    vector<MonthlyData> monthly;
    vector<SeasonalData> seasonal;

    bool valid;
};

StationDataset load_station_dataset(const string& input_file);
StationDataset load_app_ready_temperature_station_dataset(const string& input_file);
vector<StationDataset> load_station_datasets(const string& input_file);
vector<StationDataset> load_app_ready_temperature_station_datasets(const string& input_file);
void sort_daily_dataset_if_needed(vector<DailyData>& input);

#endif
