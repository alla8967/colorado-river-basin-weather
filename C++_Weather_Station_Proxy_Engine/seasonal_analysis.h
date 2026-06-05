// Purpose: Declares seasonal summary structures and aggregation helpers.

#ifndef SEASONAL_ANALYSIS_H
#define SEASONAL_ANALYSIS_H

#include <string>
#include <vector>
#include "csv_filereader.h"

using namespace std;

struct SeasonalData {

    string season;
    int season_year;

    int months_observed;
    int months_expected;
    bool complete;

    double seasonal_tavg;
    double seasonal_tmax;
    double seasonal_tmin;
    double total_seasonal_precip;
    double total_seasonal_snowfall;

    int missing_tavg_months; // Number of monthly records where TAVG was missing/unusable
    int missing_tmax_months; // Number of monthly records where monthly TMAX was missing/unusable
    int missing_tmin_months; // Number of monthly records where monthly TMIN was missing/unusable

    int missing_tmax_days; // Total missing daily TMAX values carried up from monthly data
    int missing_tmin_days; // Total missing daily TMIN values carried up from monthly data
};

string getSeason(int month);
int getSeasonYear(int month, int year);
bool isTAVGmissing(MonthlyData input);
vector<SeasonalData> compute_seasonal_data(const vector<MonthlyData>& input);

#endif