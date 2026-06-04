#include "csv_filereader.h"
#include "seasonal_analysis.h"
#include <iostream>

using namespace std;


/*

I want this function to sort the input dataset into the
different seasons and use that to compute seasonal
averages. I want it to keep track of how many missing
temperature values there are for data validation later
down the line.

To do this, I probably need to create a vector that stores
the seasonal data. Once the program calculates all of the
associated values, it needs to pushback those values into
the new vector.

*/

string getSeason(int month) {

    if (month == 1 || month == 2 || month == 12) {
        return "Winter";
    }

    if (month == 3 || month == 4 || month == 5) {
        return "Spring";
    }

    if (month == 6 || month == 7 || month == 8) {
        return "Summer";
    }

    if (month == 9 || month == 10 || month == 11) {
        return "Fall";
    }

    return "ERROR";
}

int getSeasonYear(int month, int year) {
    if (month != 12) {
        return year;
    }else {
        return year + 1;
    }
}

vector<SeasonalData> compute_seasonal_data(const vector<MonthlyData>& input) {

    vector<SeasonalData> seasonal_dataset;

    if (input.size() == 0) {
        cerr << "Empty monthly dataset" << endl;
        return seasonal_dataset;
    }
    
    string current_season = getSeason(input[0].month);
    int current_season_year = getSeasonYear(input[0].month, input[0].year);

    double sum_tavg = 0;
    double sum_tmax = 0;
    double sum_tmin = 0;
    double sum_precip = 0;
    double sum_snowfall = 0;

    int count_tavg = 0;
    int count_tmax = 0;
    int count_tmin = 0;

    int missing_tavg_months = 0;
    int missing_tmax_months = 0;
    int missing_tmin_months = 0;

    int missing_tmax_days = 0;
    int missing_tmin_days = 0;

    int months_observed = 0;
    int months_expected = 3;

    SeasonalData temp_sd;

    for (int i = 0; i < input.size(); i++) {

        string row_season = getSeason(input[i].month);
        int row_season_year = getSeasonYear(input[i].month, input[i].year);

        if (row_season != current_season || row_season_year != current_season_year) {

            temp_sd.season = current_season;
            temp_sd.season_year = current_season_year;
            temp_sd.months_observed = months_observed;
            temp_sd.months_expected = months_expected;
            temp_sd.complete = (months_observed == months_expected);
            temp_sd.total_seasonal_precip = sum_precip;
            temp_sd.total_seasonal_snowfall = sum_snowfall;
            temp_sd.missing_tavg_months = missing_tavg_months;
            temp_sd.missing_tmax_days = missing_tmax_days;
            temp_sd.missing_tmin_days = missing_tmin_days;
            temp_sd.missing_tmax_months = missing_tmax_months;
            temp_sd.missing_tmin_months = missing_tmin_months;

            if (count_tavg > 0) {
                temp_sd.seasonal_tavg = sum_tavg / count_tavg;
            } else {
                temp_sd.seasonal_tavg = MISSING;
            }

            if (count_tmax > 0) {
                temp_sd.seasonal_tmax = sum_tmax / count_tmax;
            } else {
                temp_sd.seasonal_tmax = MISSING;
            }

            if (count_tmin > 0) {
                temp_sd.seasonal_tmin = sum_tmin / count_tmin;
            } else {
                temp_sd.seasonal_tmin = MISSING;
            }

            seasonal_dataset.push_back(temp_sd);

            sum_tavg = 0;
            sum_tmax = 0;
            sum_tmin = 0;
            sum_precip = 0;
            sum_snowfall = 0;

            count_tavg = 0;
            count_tmax = 0;
            count_tmin = 0;

            missing_tavg_months = 0;
            missing_tmax_months = 0;
            missing_tmin_months = 0;
            missing_tmax_days = 0;
            missing_tmin_days = 0;

            months_observed = 0;

            current_season = row_season;
            current_season_year = row_season_year;
        }

        months_observed++;

        if (input[i].tavg_m != MISSING) {
            sum_tavg += input[i].tavg_m;
            count_tavg++;
        } else {
            missing_tavg_months++;
        }

        if (input[i].tmax_m != MISSING) {
            sum_tmax += input[i].tmax_m;
            count_tmax++;
        } else {
            missing_tmax_months++;
        }

        if (input[i].tmin_m != MISSING) {
            sum_tmin += input[i].tmin_m;
            count_tmin++;
        } else {
            missing_tmin_months++;
        }

        missing_tmax_days += input[i].missing_tmax_m;
        missing_tmin_days += input[i].missing_tmin_m;

        sum_precip += input[i].total_monthly_precip;
        sum_snowfall += input[i].total_monthly_snowfall;
    }

    temp_sd.season = current_season;
    temp_sd.season_year = current_season_year;
    temp_sd.months_observed = months_observed;
    temp_sd.months_expected = months_expected;
    temp_sd.complete = (months_observed == months_expected);
    temp_sd.total_seasonal_precip = sum_precip;
    temp_sd.total_seasonal_snowfall = sum_snowfall;
    temp_sd.missing_tavg_months = missing_tavg_months;
    temp_sd.missing_tmax_days = missing_tmax_days;
    temp_sd.missing_tmin_days = missing_tmin_days;
    temp_sd.missing_tmax_months = missing_tmax_months;
    temp_sd.missing_tmin_months = missing_tmin_months;

    if (count_tavg > 0) {
        temp_sd.seasonal_tavg = sum_tavg / count_tavg;
    } else {
        temp_sd.seasonal_tavg = MISSING;
    }

    if (count_tmax > 0) {
        temp_sd.seasonal_tmax = sum_tmax / count_tmax;
    } else {
        temp_sd.seasonal_tmax = MISSING;
    }

    if (count_tmin > 0) {
        temp_sd.seasonal_tmin = sum_tmin / count_tmin;
    } else {
        temp_sd.seasonal_tmin = MISSING;
    }

    seasonal_dataset.push_back(temp_sd);

    return seasonal_dataset;
}
