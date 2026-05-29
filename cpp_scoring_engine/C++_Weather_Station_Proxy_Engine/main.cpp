#include <iostream>
#include <iomanip>
#include <vector>

#include "station_dataset.h"
#include "similarity_scores.h"
#include "station_distance.h"
#include "station_pair_score.h"


using namespace std;

void print_station_summary(const StationDataset& station, int station_number) {
    cout << "Station #" << station_number << endl;
    cout << "Station ID: " << station.metadata.stationID << endl;
    cout << "Station Name: " << station.metadata.stationName << endl;
    cout << "Latitude: " << station.metadata.latitude << endl;
    cout << "Longitude: " << station.metadata.longitude << endl;
    cout << "Elevation: " << station.metadata.elevation << endl;
    cout << "Valid: " << station.valid << endl;
    cout << "Daily records: " << station.daily.size() << endl;
    cout << "Monthly records: " << station.monthly.size() << endl;
    cout << "Seasonal records: " << station.seasonal.size() << endl;
    cout << "----------------------------------------" << endl;
}

void print_all_station_summaries(const vector<StationDataset>& stations) {
    cout << endl;
    cout << "STATION SUMMARIES" << endl;
    cout << "----------------------------------------" << endl;

    for (int i = 0; i < stations.size(); i++) {
        print_station_summary(stations[i], i + 1);
    }
}

void print_distance_test(const StationDataset& station_a, const StationDataset& station_b) {
    double station_distance_km = calculate_station_distance_km(station_a.metadata, station_b.metadata);
    double elevation_difference_m = calculate_elevation_difference(station_a.metadata, station_b.metadata);

    cout << "DISTANCE TEST" << endl;
    cout << "----------------------------------------" << endl;

    if (station_distance_km != MISSING) {
        cout << "Horizontal distance: " << station_distance_km << " km" << endl;
        cout << "Elevation difference: " << elevation_difference_m << " m" << endl;
    } else {
        cout << "Station distance unavailable because one or both stations are missing geo data." << endl;
    }

    cout << endl;
}

void print_daily_similarity_test(const StationDataset& station_a, const StationDataset& station_b) {
    SimilarityResult daily_similarity = calculate_daily_tavg_similarity(station_a, station_b);

    cout << "DAILY TAVG SIMILARITY TEST" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Correlation: " << daily_similarity.correlation << endl;
    cout << "MAD: " << daily_similarity.mean_absolute_difference << endl;
    cout << "RMSE: " << daily_similarity.rmse << endl;
    cout << "Paired days: " << daily_similarity.range.paired_count << endl;
    cout << "Missing TMAX/TMIN Values " << daily_similarity.range.stationName_a << ": " << daily_similarity.range.missing_tvalues_a << endl;
    cout << "Missing TMAX/TMIN Values " << daily_similarity.range.stationName_b << ": " << daily_similarity.range.missing_tvalues_b << endl;
    cout << "Unmatched Daily Records from " << daily_similarity.range.stationName_a << ": " << daily_similarity.range.unmatched_records_a << endl;
    cout << "Unmatched Daily Records from " << daily_similarity.range.stationName_b << ": " << daily_similarity.range.unmatched_records_b << endl;

    if (daily_similarity.range.has_valid_pairs) {
        cout << "Start date: "
             << daily_similarity.range.start_date.year << "-"
             << daily_similarity.range.start_date.month << "-"
             << daily_similarity.range.start_date.day << endl;

        cout << "End date: "
             << daily_similarity.range.end_date.year << "-"
             << daily_similarity.range.end_date.month << "-"
             << daily_similarity.range.end_date.day << endl;
    }

    cout << endl;
}

void print_monthly_similarity_test(const StationDataset& station_a, const StationDataset& station_b) {
    SimilarityResult monthly_similarity = calculate_monthly_tavg_similarity(station_a, station_b);

    cout << "MONTHLY TAVG SIMILARITY TEST" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Correlation: " << monthly_similarity.correlation << endl;
    cout << "MAD: " << monthly_similarity.mean_absolute_difference << endl;
    cout << "RMSE: " << monthly_similarity.rmse << endl;
    cout << "Paired months: " << monthly_similarity.range.paired_count << endl;
    cout << "Missing daily TMAX/TMIN values from " << monthly_similarity.range.stationName_a << ": " << monthly_similarity.range.missing_tvalues_a << endl;
    cout << "Missing daily TMAX/TMIN values from " << monthly_similarity.range.stationName_b << ": " << monthly_similarity.range.missing_tvalues_b << endl;
    cout << "Unmatched Monthly Records from " << monthly_similarity.range.stationName_a << ": " << monthly_similarity.range.unmatched_records_a << endl;
    cout << "Unmatched Monthly Records from " << monthly_similarity.range.stationName_b << ": " << monthly_similarity.range.unmatched_records_b << endl;

    if (monthly_similarity.range.has_valid_pairs) {
        cout << "Start month: "
             << monthly_similarity.range.start_date.year << "-"
             << monthly_similarity.range.start_date.month << endl;

        cout << "End month: "
             << monthly_similarity.range.end_date.year << "-"
             << monthly_similarity.range.end_date.month << endl;
    }

    cout << endl;
}

void run_pairwise_station_test(const StationDataset& station_a, const StationDataset& station_b) {
    cout << endl;
    cout << "PAIRWISE STATION TEST" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Station A: " << station_a.metadata.stationName << " (" << station_a.metadata.stationID << ")" << endl;
    cout << "Station B: " << station_b.metadata.stationName << " (" << station_b.metadata.stationID << ")" << endl;
    cout << endl;

    print_distance_test(station_a, station_b);
    print_daily_similarity_test(station_a, station_b);
    print_monthly_similarity_test(station_a, station_b);
}


void run_first_pair_test(const vector<StationDataset>& stations) {
    if (stations.size() < 2) {
        cout << "At least two stations are needed for a pairwise comparison test." << endl;
        return;
    }

    run_pairwise_station_test(stations[0], stations[1]);
}

void run_all_pairwise_monthly_tests(const vector<StationDataset>& stations) {
    if (stations.size() < 2) {
        cout << "At least two stations are needed for all-pairwise monthly tests." << endl;
        return;
    }

    int comparison_count = 0;

    cout << endl;
    cout << "ALL PAIRWISE MONTHLY TAVG TESTS" << endl;
    cout << "----------------------------------------" << endl;

    for (int i = 0; i < stations.size(); i++) {
        for (int j = i + 1; j < stations.size(); j++) {
            comparison_count++;

            SimilarityResult monthly_similarity = calculate_monthly_tavg_similarity(stations[i], stations[j]);
            double station_distance_km = calculate_station_distance_km(stations[i].metadata, stations[j].metadata);
            double elevation_difference_m = calculate_elevation_difference(stations[i].metadata, stations[j].metadata);

            cout << "Comparison #" << comparison_count << endl;
            cout << "Station A: " << stations[i].metadata.stationName << " (" << stations[i].metadata.stationID << ")" << endl;
            cout << "Station B: " << stations[j].metadata.stationName << " (" << stations[j].metadata.stationID << ")" << endl;
            cout << "Distance km: " << station_distance_km << endl;
            cout << "Elevation difference m: " << elevation_difference_m << endl;
            cout << "Monthly correlation: " << monthly_similarity.correlation << endl;
            cout << "Monthly MAD: " << monthly_similarity.mean_absolute_difference << endl;
            cout << "Monthly RMSE: " << monthly_similarity.rmse << endl;
            cout << "Paired months: " << monthly_similarity.range.paired_count << endl;
            cout << "Unmatched monthly records from " << monthly_similarity.range.stationName_a << ": " << monthly_similarity.range.unmatched_records_a << endl;
            cout << "Unmatched monthly records from " << monthly_similarity.range.stationName_b << ": " << monthly_similarity.range.unmatched_records_b << endl;
            cout << "----------------------------------------" << endl;
        }
    }

    cout << "Total pairwise monthly comparisons run: " << comparison_count << endl;
    cout << endl;
}

void print_ranked_station_pair_scores(const vector<StationDataset>& stations) {
    vector<StationPairScore> scores = calculate_all_station_pair_scores(stations);

    cout << endl;
    cout << "RANKED STATION PAIR SCORES" << endl;
    cout << "----------------------------------------" << endl;

    if (scores.size() == 0) {
        cout << "No station pair scores were calculated." << endl;
        return;
    }

    const int MAX_RANKED_RESULTS_TO_PRINT = 25;

    int printed_rank = 1;
    int skipped_zero_scores = 0;
    int skipped_after_limit = 0;

    for (int i = 0; i < scores.size(); i++) {
        if (scores[i].score == 0.0) {
            skipped_zero_scores++;
            continue;
        }

        if (printed_rank > MAX_RANKED_RESULTS_TO_PRINT) {
            skipped_after_limit++;
            continue;
        }

        cout << "Rank #" << printed_rank << endl;
        cout << "Score: " << scores[i].score << endl;
        cout << "Station A: " << scores[i].stationName_a << " (" << scores[i].stationID_a << ")" << endl;
        cout << "Station B: " << scores[i].stationName_b << " (" << scores[i].stationID_b << ")" << endl;
        cout << "Distance km: " << scores[i].distance_km << endl;
        cout << "Elevation difference m: " << scores[i].elevation_difference_m << endl;
        cout << "Daily correlation: " << scores[i].daily_correlation << endl;
        cout << "Daily MAD: " << scores[i].daily_mad << endl;
        cout << "Daily RMSE: " << scores[i].daily_rmse << endl;
        cout << "Paired days: " << scores[i].paired_days << endl;
        cout << "Monthly correlation: " << scores[i].monthly_correlation << endl;
        cout << "Monthly MAD: " << scores[i].monthly_mad << endl;
        cout << "Monthly RMSE: " << scores[i].monthly_rmse << endl;
        cout << "Paired months: " << scores[i].paired_months << endl;
        cout << "----------------------------------------" << endl;

        printed_rank++;
    }

    cout << "Zero-score matchups skipped: " << skipped_zero_scores << endl;
    cout << "Additional ranked matchups not printed after top " << MAX_RANKED_RESULTS_TO_PRINT << ": " << skipped_after_limit << endl;
    cout << "Total candidate matchups after pruning: " << scores.size() << endl;
}

void print_ranked_score_range(
    const vector<StationPairScore>& scores,
    int start_rank,
    int end_rank
) {
    cout << endl;
    cout << "RANKS #" << start_rank << " TO #" << end_rank << endl;
    cout << "----------------------------------------" << endl;

    if (scores.size() == 0) {
        cout << "No station pair scores available." << endl;
        return;
    }

    if (start_rank < 1) {
        start_rank = 1;
    }

    if (end_rank > scores.size()) {
        end_rank = scores.size();
    }

    if (start_rank > end_rank) {
        cout << "Requested rank range is outside the available results." << endl;
        return;
    }

    for (int i = start_rank - 1; i < end_rank; i++) {
        cout << "Rank #" << i + 1 << endl;
        cout << "Score: " << scores[i].score << endl;
        cout << "Station A: " << scores[i].stationName_a << " (" << scores[i].stationID_a << ")" << endl;
        cout << "Station B: " << scores[i].stationName_b << " (" << scores[i].stationID_b << ")" << endl;
        cout << "Distance km: " << scores[i].distance_km << endl;
        cout << "Elevation difference m: " << scores[i].elevation_difference_m << endl;
        cout << "Daily correlation: " << scores[i].daily_correlation << endl;
        cout << "Daily MAD: " << scores[i].daily_mad << endl;
        cout << "Daily RMSE: " << scores[i].daily_rmse << endl;
        cout << "Paired days: " << scores[i].paired_days << endl;
        cout << "Monthly correlation: " << scores[i].monthly_correlation << endl;
        cout << "Monthly MAD: " << scores[i].monthly_mad << endl;
        cout << "Monthly RMSE: " << scores[i].monthly_rmse << endl;
        cout << "Paired months: " << scores[i].paired_months << endl;
        cout << "----------------------------------------" << endl;
    }
}

int main() {
    cout << fixed << setprecision(6);

    const string input_file = "KnownValues.csv";

    cout << "RANKED STATION MATCH TEST" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Input file: " << input_file << endl;
    cout << endl;

    vector<StationDataset> stations = load_station_datasets(input_file);

    cout << endl;
    cout << "LOAD RESULT" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Stations loaded: " << stations.size() << endl;
    cout << endl;

    if (stations.size() < 2) {
        cout << "At least two stations are needed to rank station pair scores." << endl;
        return 1;
    }

    vector<StationPairScore> scores = calculate_all_station_pair_scores(stations);

    cout << "RANKED STATION PAIR SCORES" << endl;
    cout << "----------------------------------------" << endl;
    cout << "Candidate pairs after pruning: " << scores.size() << endl;
    cout << endl;

    if (scores.size() == 0) {
        cout << "No valid station pair scores were calculated." << endl;
        return 1;
    }

    for (int i = 0; i < scores.size(); i++) {
        cout << "Rank #" << i + 1 << endl;
        cout << "Score: " << scores[i].score << endl;
        cout << "Station A: " << scores[i].stationName_a << " (" << scores[i].stationID_a << ")" << endl;
        cout << "Station B: " << scores[i].stationName_b << " (" << scores[i].stationID_b << ")" << endl;
        cout << "Distance km: " << scores[i].distance_km << endl;
        cout << "Elevation difference m: " << scores[i].elevation_difference_m << endl;
        cout << "Daily correlation: " << scores[i].daily_correlation << endl;
        cout << "Daily MAD: " << scores[i].daily_mad << endl;
        cout << "Daily RMSE: " << scores[i].daily_rmse << endl;
        cout << "Paired days: " << scores[i].paired_days << endl;
        cout << "Monthly correlation: " << scores[i].monthly_correlation << endl;
        cout << "Monthly MAD: " << scores[i].monthly_mad << endl;
        cout << "Monthly RMSE: " << scores[i].monthly_rmse << endl;
        cout << "Paired months: " << scores[i].paired_months << endl;
        cout << "----------------------------------------" << endl;
    }

    cout << "Total ranked station pairs printed: " << scores.size() << endl;

    return 0;
}