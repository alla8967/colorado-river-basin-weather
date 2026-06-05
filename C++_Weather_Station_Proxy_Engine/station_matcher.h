// Purpose: Declares station match result structures and pair-evaluation helpers.

#ifndef STATION_MATCHER_H
#define STATION_MATCHER_H

#include <string>

#include "station_dataset.h"
#include "similarity_scores.h"

using namespace std;

struct StationMatchResult {

    string target_stationID;
    string target_stationName;
    string candidate_stationID;
    string candidate_stationName;

    double distance_km;
    double elevation_difference_m;

    SimilarityResult daily_similarity;
    SimilarityResult monthly_similarity;

};


#endif