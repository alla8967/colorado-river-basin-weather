#include "station_matcher.h"
#include "similarity_scores.h"
#include "station_distance.h"

using namespace std;

StationMatchResult evaluate_station_match(
    const StationDataset& target, 
    const StationDataset& candidate
    ) {

        StationMatchResult result;

        result.target_stationID = target.metadata.stationID;
        result.target_stationName = target.metadata.stationName;
        result.candidate_stationID = candidate.metadata.stationID;
        result.candidate_stationName = candidate.metadata.stationName;

        result.daily_similarity = calculate_daily_tavg_similarity(target, candidate);
        result.monthly_similarity = calculate_monthly_tavg_similarity(target, candidate);

        result.distance_km = calculate_station_distance_km(target.metadata, candidate.metadata);
        result.elevation_difference_m = calculate_elevation_difference(target.metadata, candidate.metadata);

        return result;
}
