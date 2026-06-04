#ifndef CSV_FILEREADER_H
#define CSV_FILEREADER_H

#include <string>
#include <vector>

using namespace std;

extern const double MISSING;

struct DailyData {
    bool valid;

    string stationID;
    string stationName;

    double latitude;
    double longitude;
    double elevation;

    int year;
    int month;
    int day;

    double tavg_d;
    double tmin_d;
    double tmax_d;
    double daily_precip;
    double daily_snowfall;
};

struct MonthlyData {    

    int year;
    int month;

    int days_observed;
    int days_expected;
    int missing_calendar_days;

    double tavg_m;
    double tmin_m;
    double tmax_m;
    double total_monthly_precip;
    double total_monthly_snowfall;

    int missing_tmin_m;
    int missing_tmax_m;
    int missing_daily_precip_m;
    int missing_daily_snowfall_m;
};

vector<string> grab_data(string input_file);
vector<string> parse_data(const string& input);
double valid_stod(string input);
DailyData stoDD(const vector<string>& input);
DailyData stoDD_app_ready_temperature(const vector<string>& input);
DailyData stoDD_app_ready_temperature_line(const string& input);
vector<DailyData> create_daily_dataset(const vector<string>& lines);
vector<DailyData> create_app_ready_temperature_dataset(const vector<string>& lines);
vector<DailyData> sort_daily_dataset(vector<DailyData> input);
bool isLeapYear(int year);
int daysInMonth(int year, int month);
vector<MonthlyData> create_monthly_dataset(const vector<DailyData>& input);
void export_monthly_dataset(string output_file, const vector<MonthlyData>& input);

#endif
