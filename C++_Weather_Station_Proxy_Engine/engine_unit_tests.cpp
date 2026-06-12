// Purpose: Runs focused C++ unit checks for station scoring, parsing, distance, and rollups.

#include <cmath>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "csv_filereader.h"
#include "seasonal_analysis.h"
#include "similarity_scores.h"
#include "station_dataset.h"
#include "station_distance.h"
#include "station_pair_score.h"

using namespace std;

void assert_close(double actual, double expected, double tolerance, const string& label) {
    if (fabs(actual - expected) > tolerance) {
        throw runtime_error(
            label + " expected " + to_string(expected) + " but got " + to_string(actual)
        );
    }
}

void assert_true(bool condition, const string& label) {
    if (!condition) {
        throw runtime_error(label);
    }
}

DailyData make_daily(
    const string& station_id,
    int year,
    int month,
    int day,
    double tmin,
    double tmax
) {
    DailyData row;
    row.valid = true;
    row.stationID = station_id;
    row.stationName = station_id;
    row.latitude = 0.0;
    row.longitude = 0.0;
    row.elevation = 0.0;
    row.year = year;
    row.month = month;
    row.day = day;
    row.tmin_d = tmin;
    row.tmax_d = tmax;
    row.tavg_d = (tmin != MISSING && tmax != MISSING) ? (tmin + tmax) / 2.0 : MISSING;
    row.daily_precip = MISSING;
    row.daily_snowfall = MISSING;
    return row;
}

StationDataset make_station(
    const string& station_id,
    double latitude,
    double longitude,
    double elevation,
    const vector<DailyData>& daily
) {
    StationDataset station;
    station.input_file = "";
    station.metadata.stationID = station_id;
    station.metadata.stationName = station_id;
    station.metadata.latitude = latitude;
    station.metadata.longitude = longitude;
    station.metadata.elevation = elevation;
    station.metadata.has_geo_data = true;
    station.daily = daily;
    station.monthly = create_monthly_dataset(station.daily);
    station.seasonal = compute_seasonal_data(station.monthly);
    station.valid = true;
    return station;
}

void test_parser_handles_quoted_commas() {
    vector<string> values = parse_data("A,\"B,C\",D");
    assert_true(values.size() == 3, "quoted CSV parser should return three fields");
    assert_true(values[0] == "A", "first field should parse");
    assert_true(values[1] == "B,C", "quoted comma should remain in one field");
    assert_true(values[2] == "D", "third field should parse");
}

void test_distance_and_scoring_curves() {
    double denver_to_boulder = calculate_haversine_distance_km(
        39.7392,
        -104.9903,
        40.01499,
        -105.27055
    );
    assert_close(denver_to_boulder, 38.9, 0.6, "Denver to Boulder distance");
    assert_close(calculate_correlation_score(0.95), 1.0, 1e-9, "excellent correlation score");
    assert_close(calculate_correlation_score(0.75), 0.0, 1e-9, "bottom correlation score");
    assert_close(calculate_MAD_score(MISSING), 0.0, 1e-9, "missing MAD score");
    assert_close(calculate_RMSE_score(2.75), 1.0, 1e-9, "excellent RMSE score");
    assert_close(calculate_distance_score(MISSING), 0.0, 1e-9, "missing distance score");
    assert_close(calculate_elevation_score(50.0), 1.0, 1e-9, "excellent elevation score");
}

void test_monthly_rollup_counts_missing_calendar_days() {
    vector<DailyData> rows = {
        make_daily("A", 2025, 1, 1, 30.0, 50.0),
        make_daily("A", 2025, 1, 2, 40.0, 60.0),
    };
    vector<MonthlyData> monthly = create_monthly_dataset(rows);
    assert_true(monthly.size() == 1, "single-month input should create one monthly row");
    assert_true(monthly[0].days_observed == 2, "monthly days observed");
    assert_true(monthly[0].days_expected == 31, "January days expected");
    assert_true(monthly[0].missing_calendar_days == 29, "January missing calendar days");
    assert_true(monthly[0].missing_tmax_m == 29, "missing Tmax includes calendar gaps");
    assert_true(monthly[0].missing_tmin_m == 29, "missing Tmin includes calendar gaps");
    assert_close(monthly[0].tavg_m, 45.0, 1e-9, "monthly TAVG");
}

void test_similarity_and_missing_values() {
    vector<double> x = {1.0, 2.0, 3.0};
    vector<double> y = {1.0, 2.0, 3.0};
    assert_close(calculate_daily_correlation(x, y), 1.0, 1e-9, "perfect correlation");
    assert_close(calculate_mean_absolute_difference({1.0, 3.0}, {2.0, 1.0}), 1.5, 1e-9, "MAD");
    assert_true(
        calculate_rmse(vector<double>{}, vector<double>{}) == MISSING,
        "empty RMSE should be missing"
    );
}

void test_station_pair_score_uses_paired_daily_values() {
    StationDataset station_a = make_station(
        "A",
        39.0,
        -105.0,
        1600.0,
        {
            make_daily("A", 2025, 1, 1, 30.0, 50.0),
            make_daily("A", 2025, 1, 2, 32.0, 52.0),
            make_daily("A", 2025, 1, 3, 34.0, 54.0),
        }
    );
    StationDataset station_b = make_station(
        "B",
        39.1,
        -105.1,
        1610.0,
        {
            make_daily("B", 2025, 1, 1, 31.0, 51.0),
            make_daily("B", 2025, 1, 2, 33.0, 53.0),
            make_daily("B", 2025, 1, 3, 35.0, 55.0),
        }
    );
    StationPairScore score = calculate_station_pair_score(station_a, station_b);
    assert_true(score.paired_days == 3, "paired day count");
    assert_close(score.daily_mad, 1.0, 1e-9, "daily MAD");
    assert_true(score.score > 0.0, "station pair should receive a positive score");
}

int main() {
    try {
        test_parser_handles_quoted_commas();
        test_distance_and_scoring_curves();
        test_monthly_rollup_counts_missing_calendar_days();
        test_similarity_and_missing_values();
        test_station_pair_score_uses_paired_daily_values();
    } catch (const exception& error) {
        cerr << "C++ unit test failed: " << error.what() << endl;
        return 1;
    }

    cout << "C++ unit tests passed." << endl;
    return 0;
}
