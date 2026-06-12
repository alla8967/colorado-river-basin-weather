// Purpose: Computes correlation, error, and combined similarity metrics between station time series.

#include "similarity_scores.h"
#include <iostream>
#include <vector>
#include <cmath>

using namespace std;

/*

Important info:

Correlation = do they move together?
MAD = how far apart are they on average?
RMSE = are there occasional big mismatches?
Paired count = how much evidence supports the result?
Start/end date = what period was actually compared?

*/

MatchDate make_empty_date() {
    MatchDate date;
    date.year = 0;
    date.month = 0;
    date.day = 0;
    return date;
}

MatchRange make_empty_range() {
    MatchRange range;
    
    range.stationID_a = "";
    range.stationID_b = "";
    range.stationName_a = "";
    range.stationName_b = "";

    range.missing_tvalues_a = 0;
    range.missing_tvalues_b = 0;

    range.unmatched_records_a = 0;
    range.unmatched_records_b = 0;
    
    range.start_date = make_empty_date();
    range.end_date = make_empty_date();
    range.paired_count = 0;
    range.has_valid_pairs = false;
    return range;
}

int compare_daily_dates(const DailyData& a, const DailyData& b) {
    if (a.year < b.year) {
        return -1;
    }
    if (a.year > b.year) {
        return 1;
    }

    if (a.month < b.month) {
        return -1;
    }
    if (a.month > b.month) {
        return 1;
    }

    if (a.day < b.day) {
        return -1;
    }
    if (a.day > b.day) {
        return 1;
    }

    return 0;
}

double calculate_daily_correlation(const vector<double>& x, const vector<double>& y) {
    if (x.size() != y.size() || x.size() < 2) {
        return MISSING;
    }

    double sum_x = 0;
    double sum_y = 0;

    for (size_t i = 0; i < x.size(); i++) {
        sum_x += x[i];
        sum_y += y[i];
    }

    double mean_x = sum_x / x.size();
    double mean_y = sum_y / y.size();

    double numerator = 0;
    double sum_x_squared_diff = 0;
    double sum_y_squared_diff = 0;

    for (size_t i = 0; i < x.size(); i++) {
        double x_diff = x[i] - mean_x;
        double y_diff = y[i] - mean_y;

        numerator += x_diff * y_diff;
        sum_x_squared_diff += x_diff * x_diff;
        sum_y_squared_diff += y_diff * y_diff;
    }

    double denominator = sqrt(sum_x_squared_diff * sum_y_squared_diff);

    if (denominator == 0) {
        return MISSING;
    }

    return numerator / denominator;
}

CorrelationResult calculate_pcc_daily(const StationDataset& station_a, const StationDataset& station_b) {
    CorrelationResult result;

    result.correlation = MISSING;
    result.range = make_empty_range();

    const vector<DailyData>& input_a = station_a.daily;
    const vector<DailyData>& input_b = station_b.daily;

    result.range.stationID_a = station_a.metadata.stationID;
    result.range.stationID_b = station_b.metadata.stationID;
    result.range.stationName_a = station_a.metadata.stationName;
    result.range.stationName_b = station_b.metadata.stationName;

    vector<double> paired_values_a;
    vector<double> paired_values_b;

    size_t i = 0;
    size_t j = 0;

    while (i < input_a.size() && j < input_b.size()) {
        int date_comparison = compare_daily_dates(input_a[i], input_b[j]);

        if (date_comparison == 0) {
            if (input_a[i].tmax_d == MISSING) {
                result.range.missing_tvalues_a++;
            }
            if (input_a[i].tmin_d == MISSING) {
                result.range.missing_tvalues_a++;
            }
            if (input_b[j].tmax_d == MISSING) {
                result.range.missing_tvalues_b++;
            }
            if (input_b[j].tmin_d == MISSING) {
                result.range.missing_tvalues_b++;
            }

            if (input_a[i].tavg_d != MISSING && input_b[j].tavg_d != MISSING) {
                paired_values_a.push_back(input_a[i].tavg_d);
                paired_values_b.push_back(input_b[j].tavg_d);

                MatchDate current_date;
                current_date.year = input_a[i].year;
                current_date.month = input_a[i].month;
                current_date.day = input_a[i].day;

                if (!result.range.has_valid_pairs) {
                    result.range.start_date = current_date;
                    result.range.has_valid_pairs = true;
                }

                result.range.end_date = current_date;
            }

            i++;
            j++;
        } else if (date_comparison < 0) {
            result.range.unmatched_records_a++;
            i++;
        } else {
            result.range.unmatched_records_b++;
            j++;
        }
    }

    result.range.unmatched_records_a += input_a.size() - i;
    result.range.unmatched_records_b += input_b.size() - j;

    result.range.paired_count = paired_values_a.size();
    result.correlation = calculate_daily_correlation(paired_values_a, paired_values_b);

    return result;
}

SimilarityResult calculate_daily_tavg_similarity(const StationDataset& station_a, const StationDataset& station_b) {
    SimilarityResult result;

    result.correlation = MISSING;
    result.mean_absolute_difference = MISSING;
    result.rmse = MISSING;
    result.range = make_empty_range();

    const vector<DailyData>& input_a = station_a.daily;
    const vector<DailyData>& input_b = station_b.daily;

    result.range.stationID_a = station_a.metadata.stationID;
    result.range.stationID_b = station_b.metadata.stationID;
    result.range.stationName_a = station_a.metadata.stationName;
    result.range.stationName_b = station_b.metadata.stationName;

    vector<double> paired_values_a;
    vector<double> paired_values_b;

    size_t i = 0;
    size_t j = 0;

    while (i < input_a.size() && j < input_b.size()) {
        int date_comparison = compare_daily_dates(input_a[i], input_b[j]);

        if (date_comparison == 0) {
            if (input_a[i].tmax_d == MISSING) {
                result.range.missing_tvalues_a++;
            }
            if (input_a[i].tmin_d == MISSING) {
                result.range.missing_tvalues_a++;
            }
            if (input_b[j].tmax_d == MISSING) {
                result.range.missing_tvalues_b++;
            }
            if (input_b[j].tmin_d == MISSING) {
                result.range.missing_tvalues_b++;
            }

            if (input_a[i].tavg_d != MISSING && input_b[j].tavg_d != MISSING) {
                paired_values_a.push_back(input_a[i].tavg_d);
                paired_values_b.push_back(input_b[j].tavg_d);

                MatchDate current_date;
                current_date.year = input_a[i].year;
                current_date.month = input_a[i].month;
                current_date.day = input_a[i].day;

                if (!result.range.has_valid_pairs) {
                    result.range.start_date = current_date;
                    result.range.has_valid_pairs = true;
                }

                result.range.end_date = current_date;
            }

            i++;
            j++;
        } else if (date_comparison < 0) {
            result.range.unmatched_records_a++;
            i++;
        } else {
            result.range.unmatched_records_b++;
            j++;
        }
    }

    result.range.unmatched_records_a += input_a.size() - i;
    result.range.unmatched_records_b += input_b.size() - j;

    result.range.paired_count = paired_values_a.size();
    result.correlation = calculate_daily_correlation(paired_values_a, paired_values_b);
    result.mean_absolute_difference = calculate_mean_absolute_difference(paired_values_a, paired_values_b);
    result.rmse = calculate_rmse(paired_values_a, paired_values_b);

    return result;
}

int compare_monthly_dates(const MonthlyData& a, const MonthlyData& b) {
    if (a.year < b.year) {
        return -1;
    }
    if (a.year > b.year) {
        return 1;
    }

    if (a.month < b.month) {
        return -1;
    }
    if (a.month > b.month) {
        return 1;
    }

    return 0;
}

double calculate_mean_absolute_difference(const vector<double>& x, const vector<double>& y) {
    if (x.size() != y.size() || x.size() == 0) {
        return MISSING;
    }

    double sum_absolute_difference = 0;

    for (size_t i = 0; i < x.size(); i++) {
        sum_absolute_difference += fabs(x[i] - y[i]);
    }

    return sum_absolute_difference / x.size();
}

double calculate_rmse(const vector<double>& x, const vector<double>& y) {
    if (x.size() != y.size() || x.size() == 0) {
        return MISSING;
    }

    double sum_squared_error = 0;

    for (size_t i = 0; i < x.size(); i++) {
        double difference = x[i] - y[i];
        sum_squared_error += difference * difference;
    }

    return sqrt(sum_squared_error / x.size());
}

CorrelationResult calculate_pcc_monthly(const StationDataset& station_a, const StationDataset& station_b) {
    CorrelationResult result;

    result.correlation = MISSING;
    result.range = make_empty_range();

    const vector<MonthlyData>& input_a = station_a.monthly;
    const vector<MonthlyData>& input_b = station_b.monthly;

    result.range.stationID_a = station_a.metadata.stationID;
    result.range.stationID_b = station_b.metadata.stationID;
    result.range.stationName_a = station_a.metadata.stationName;
    result.range.stationName_b = station_b.metadata.stationName;

    vector<double> paired_values_a;
    vector<double> paired_values_b;

    size_t i = 0;
    size_t j = 0;

    while (i < input_a.size() && j < input_b.size()) {
        int date_comparison = compare_monthly_dates(input_a[i], input_b[j]);

        if (date_comparison == 0) {
            result.range.missing_tvalues_a += input_a[i].missing_tmax_m + input_a[i].missing_tmin_m;
            result.range.missing_tvalues_b += input_b[j].missing_tmax_m + input_b[j].missing_tmin_m;

            if (input_a[i].tavg_m != MISSING && input_b[j].tavg_m != MISSING) {
                paired_values_a.push_back(input_a[i].tavg_m);
                paired_values_b.push_back(input_b[j].tavg_m);

                MatchDate current_date;
                current_date.year = input_a[i].year;
                current_date.month = input_a[i].month;
                current_date.day = 0;

                if (!result.range.has_valid_pairs) {
                    result.range.start_date = current_date;
                    result.range.has_valid_pairs = true;
                }

                result.range.end_date = current_date;
            }

            i++;
            j++;
        } else if (date_comparison < 0) {
            result.range.unmatched_records_a++;
            i++;
        } else {
            result.range.unmatched_records_b++;
            j++;
        }
    }

    result.range.unmatched_records_a += input_a.size() - i;
    result.range.unmatched_records_b += input_b.size() - j;

    result.range.paired_count = paired_values_a.size();
    result.correlation = calculate_daily_correlation(paired_values_a, paired_values_b);

    return result;
}

SimilarityResult calculate_monthly_tavg_similarity(const StationDataset& station_a, const StationDataset& station_b) {
    SimilarityResult result;

    result.correlation = MISSING;
    result.mean_absolute_difference = MISSING;
    result.rmse = MISSING;
    result.range = make_empty_range();

    const vector<MonthlyData>& input_a = station_a.monthly;
    const vector<MonthlyData>& input_b = station_b.monthly;

    result.range.stationID_a = station_a.metadata.stationID;
    result.range.stationID_b = station_b.metadata.stationID;
    result.range.stationName_a = station_a.metadata.stationName;
    result.range.stationName_b = station_b.metadata.stationName;

    vector<double> paired_values_a;
    vector<double> paired_values_b;

    size_t i = 0;
    size_t j = 0;

    while (i < input_a.size() && j < input_b.size()) {
        int date_comparison = compare_monthly_dates(input_a[i], input_b[j]);

        if (date_comparison == 0) {
            result.range.missing_tvalues_a += input_a[i].missing_tmax_m + input_a[i].missing_tmin_m;
            result.range.missing_tvalues_b += input_b[j].missing_tmax_m + input_b[j].missing_tmin_m;

            if (input_a[i].tavg_m != MISSING && input_b[j].tavg_m != MISSING) {
                paired_values_a.push_back(input_a[i].tavg_m);
                paired_values_b.push_back(input_b[j].tavg_m);

                MatchDate current_date;
                current_date.year = input_a[i].year;
                current_date.month = input_a[i].month;
                current_date.day = 0;

                if (!result.range.has_valid_pairs) {
                    result.range.start_date = current_date;
                    result.range.has_valid_pairs = true;
                }

                result.range.end_date = current_date;
            }

            i++;
            j++;
        } else if (date_comparison < 0) {
            result.range.unmatched_records_a++;
            i++;
        } else {
            result.range.unmatched_records_b++;
            j++;
        }
    }

    result.range.unmatched_records_a += input_a.size() - i;
    result.range.unmatched_records_b += input_b.size() - j;

    result.range.paired_count = paired_values_a.size();
    result.correlation = calculate_daily_correlation(paired_values_a, paired_values_b);
    result.mean_absolute_difference = calculate_mean_absolute_difference(paired_values_a, paired_values_b);
    result.rmse = calculate_rmse(paired_values_a, paired_values_b);

    return result;
}
