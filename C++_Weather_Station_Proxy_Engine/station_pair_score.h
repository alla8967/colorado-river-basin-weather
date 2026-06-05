// Purpose: Declares scoring weights, metric breakdowns, and station pair score structures.

#ifndef STATION_PAIR_SCORE_H
#define STATION_PAIR_SCORE_H

#include <string>
#include <vector>

#include "station_dataset.h"
#include "similarity_scores.h"

using namespace std;

struct StationPairScore {
    string stationID_a; //
    string stationName_a; //
    string stationID_b; //
    string stationName_b; //

    double score; //

    double distance_km; //
    double elevation_difference_m; //

    double daily_correlation; //
    double daily_mad; //
    double daily_rmse; //
    int paired_days;

    double monthly_correlation;
    double monthly_mad;
    double monthly_rmse;
    int paired_months;
};

StationPairScore calculate_station_pair_score(
    const StationDataset& station_a,
    const StationDataset& station_b
);

vector<StationPairScore> calculate_all_station_pair_scores(
    const vector<StationDataset>& stations
);

StationPairScore find_best_match(
    const StationDataset& target, 
    const vector<StationDataset>& dataset_pool
);

#endif