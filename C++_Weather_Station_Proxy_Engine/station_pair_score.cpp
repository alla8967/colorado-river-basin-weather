// Purpose: Combines distance, elevation, correlation, and error metrics into proxy-station scores.

#include "station_pair_score.h"
#include "station_distance.h"
#include <algorithm>
#include <cmath>

/*

Score Evaluation Metrics:

Daily correlation, MAD, and RMSE must carry the most weight
because those metrics indicate the similarity of the two
climate regions the best. The next highest weighted value
is distance, because weather stations that are closer to
eachother will have overlapping weather patterns, and
that should be included. Elevation next, because while
it is important that the two stations share similar
elevations, it is unlikely that two weather stations in
mountainous regions will have very similar elevations.

Record overlap was not taken into account, since the
objective of this program is to compare stations with
small relative datasets to be compared with stations
of large relative datasets.

Weight Breakdown:
Daily Correlation: 20%
MAD: 35%
RMSE: 25%
Distance: 15%
Elevation: 5%

*/

double calculate_correlation_score(double correlation) {
    const double excellent_threshold = 0.95;
    const double bottom_threshold = 0.75;

    if (correlation >= excellent_threshold) {
        return 1.0;
    }

    if (correlation <= bottom_threshold) {
        return 0.0;
    }

    double normalized_position =
        (excellent_threshold - correlation) /
        (excellent_threshold - bottom_threshold);

    return 0.5 * (1.0 + cos(M_PI * normalized_position));
}

double calculate_MAD_score(double mad) {
    const double excellent_threshold = 2.0;
    const double decay_rate = 0.12;

    if (mad == MISSING) {
        return 0.0;
    }

    if (mad <= excellent_threshold) {
        return 1.0;
    }

    return exp(-decay_rate * (mad - excellent_threshold));
}

double calculate_RMSE_score(double rmse) {
    const double excellent_threshold = 2.75;
    const double decay_rate = 0.13;

    if (rmse == MISSING) {
        return 0.0;
    }

    if (rmse <= excellent_threshold) {
        return 1.0;
    }

    return exp(-decay_rate * (rmse - excellent_threshold));
}

double calculate_distance_score(double distance_km) {
    const double excellent_threshold = 35.0;
    const double decay_rate = 0.006;

    if (distance_km == MISSING) {
        return 0.0;
    }

    if (distance_km <= excellent_threshold) {
        return 1.0;
    }

    return exp(-decay_rate * (distance_km - excellent_threshold));
}

double calculate_elevation_score(double elevation_difference_m) {
    const double excellent_threshold = 50.0;
    const double decay_rate = 0.0025;

    if (elevation_difference_m == MISSING) {
        return 0.0;
    }

    if (elevation_difference_m <= excellent_threshold) {
        return 1.0;
    }

    return exp(-decay_rate * (elevation_difference_m - excellent_threshold));
}

StationPairScore calculate_station_pair_score(
    const StationDataset& station_a,
    const StationDataset& station_b,
    bool include_monthly
) {
    double daily_correlation_score;
    double daily_MAD_score;
    double daily_RMSE_score;
    double distance_score;
    double elevation_score;

    double total_score;

    SimilarityResult result_daily;
    SimilarityResult result_monthly;
    StationPairScore output;


    result_daily = calculate_daily_tavg_similarity(station_a, station_b);
    if (include_monthly && !station_a.monthly.empty() && !station_b.monthly.empty()) {
        result_monthly = calculate_monthly_tavg_similarity(station_a, station_b);
    } else {
        result_monthly.correlation = MISSING;
        result_monthly.mean_absolute_difference = MISSING;
        result_monthly.rmse = MISSING;
        result_monthly.range = make_empty_range();
    }
    
    double distance_km = calculate_haversine_distance_km(
        station_a.metadata.latitude, 
        station_a.metadata.longitude, 
        station_b.metadata.latitude,
        station_b.metadata.longitude
    );

    double elevation_difference = calculate_elevation_difference(
        station_a.metadata,
        station_b.metadata
    );


    output.stationID_a = station_a.metadata.stationID;
    output.stationName_a = station_a.metadata.stationName;
    output.stationID_b = station_b.metadata.stationID;
    output.stationName_b = station_b.metadata.stationName;

    output.daily_correlation = result_daily.correlation;
    output.daily_mad = result_daily.mean_absolute_difference;
    output.daily_rmse = result_daily.rmse;
    output.paired_days = result_daily.range.paired_count;
    output.distance_km = distance_km;
    output.elevation_difference_m = elevation_difference;
    
    output.monthly_correlation = result_monthly.correlation;
    output.monthly_mad = result_monthly.mean_absolute_difference;
    output.monthly_rmse = result_monthly.rmse;
    output.paired_months = result_monthly.range.paired_count;

    if (output.paired_days == 0 ||
        output.daily_correlation == MISSING ||
        output.daily_mad == MISSING ||
        output.daily_rmse == MISSING) {
        output.score = 0.0;
        return output;
    }

    daily_correlation_score = calculate_correlation_score(output.daily_correlation);
    daily_MAD_score = calculate_MAD_score(output.daily_mad);
    daily_RMSE_score = calculate_RMSE_score(output.daily_rmse);
    distance_score = calculate_distance_score(output.distance_km);
    elevation_score = calculate_elevation_score(output.elevation_difference_m);

    total_score = 
        (daily_correlation_score * 0.20) +
        (daily_MAD_score * 0.35) +
        (daily_RMSE_score * 0.25) +
        (distance_score * 0.15) +
        (elevation_score * 0.05)
    ;

    output.score = total_score * 100;

    return output;
}

vector<StationPairScore> calculate_all_station_pair_scores(
    const vector<StationDataset>& stations
) {
    vector<StationPairScore> scores;

    if (stations.size() < 2) {
        return scores;
    }

    size_t possible_pairs = (stations.size() * (stations.size() - 1)) / 2;
    scores.reserve(possible_pairs);

    const double MAX_CANDIDATE_DISTANCE_KM = 300.0;
    const double MAX_CANDIDATE_ELEVATION_DIFFERENCE_M = 1500.0;
    const int MIN_PAIRED_DAYS = 365;

    for (size_t i = 0; i < stations.size(); i++) {
        for (size_t j = i + 1; j < stations.size(); j++) {
            StationPairScore score = calculate_station_pair_score(stations[i], stations[j]);

            if (score.score == 0.0) {
                continue;
            }

            if (score.distance_km > MAX_CANDIDATE_DISTANCE_KM) {
                continue;
            }

            if (score.elevation_difference_m > MAX_CANDIDATE_ELEVATION_DIFFERENCE_M) {
                continue;
            }

            if (score.paired_days < MIN_PAIRED_DAYS) {
                continue;
            }

            scores.push_back(score);
        }
    }

    sort(scores.begin(), scores.end(), [](const StationPairScore& a, const StationPairScore& b) {
        return a.score > b.score;
    });

    return scores;
}

StationPairScore find_best_match(
    const StationDataset& target, 
    const vector<StationDataset>& dataset_pool
) {
    StationPairScore best_match;
    best_match.score = 0.0;

    const double MAX_CANDIDATE_DISTANCE_KM = 300.0;
    const double MAX_CANDIDATE_ELEVATION_DIFFERENCE_M = 1500.0;
    const int MIN_PAIRED_DAYS = 365;

    for (size_t i = 0; i < dataset_pool.size(); i++) {
        if (dataset_pool[i].metadata.stationID == target.metadata.stationID) {
            continue;
        }

        StationPairScore temp_match = calculate_station_pair_score(target, dataset_pool[i]);

        if (temp_match.score == 0.0) {
            continue;
        }

        if (temp_match.distance_km > MAX_CANDIDATE_DISTANCE_KM) {
            continue;
        }

        if (temp_match.elevation_difference_m > MAX_CANDIDATE_ELEVATION_DIFFERENCE_M) {
            continue;
        }

        if (temp_match.paired_days < MIN_PAIRED_DAYS) {
            continue;
        }

        if (temp_match.score > best_match.score) {
            best_match = temp_match;
        }
    }

    return best_match;
}
