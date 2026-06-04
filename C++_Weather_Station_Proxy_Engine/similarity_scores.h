#ifndef SIMILARITY_SCORES_H
#define SIMILARITY_SCORES_H

#include <string>
#include <vector>

#include "csv_filereader.h"
#include "station_dataset.h"

using namespace std;

struct MatchDate {
    int year;
    int month;
    int day;
};

struct MatchRange {
    string stationID_a;
    string stationName_a;
    string stationID_b;
    string stationName_b;

    int missing_tvalues_a;
    int missing_tvalues_b;

    int unmatched_records_a;
    int unmatched_records_b;

    MatchDate start_date;
    MatchDate end_date;
    int paired_count;
    bool has_valid_pairs;
};

struct CorrelationResult {
    double correlation;
    MatchRange range;
};

struct SimilarityResult {
    double correlation;
    double mean_absolute_difference;
    double rmse;
    MatchRange range;
};

MatchDate make_empty_date();
MatchRange make_empty_range();

int compare_daily_dates(const DailyData& a, const DailyData& b);
int compare_monthly_dates(const MonthlyData& a, const MonthlyData& b);

double calculate_daily_correlation(const vector<double>& x, const vector<double>& y);
double calculate_mean_absolute_difference(const vector<double>& x, const vector<double>& y);
double calculate_rmse(const vector<double>& x, const vector<double>& y);

CorrelationResult calculate_pcc_daily(const StationDataset& station_a, const StationDataset& station_b);
SimilarityResult calculate_daily_tavg_similarity(const StationDataset& station_a, const StationDataset& station_b);

CorrelationResult calculate_pcc_monthly(const StationDataset& station_a, const StationDataset& station_b);
SimilarityResult calculate_monthly_tavg_similarity(const StationDataset& station_a, const StationDataset& station_b);

#endif