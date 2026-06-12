// Purpose: Parses app-ready station CSV files into typed daily weather rows for the engine.

#include "csv_filereader.h"

#include <iostream>
#include <fstream>
#include <sstream>
#include <ostream>
#include <string>
#include <string_view>
#include <vector>
#include <algorithm>

using namespace std;

const double MISSING = -9999;

string clean_csv_text_field(string_view input) {
    while (!input.empty() && (input.front() == ' ' || input.front() == '"')) {
        input.remove_prefix(1);
    }

    while (!input.empty() &&
           (input.back() == ' ' || input.back() == '"' || input.back() == '\r')) {
        input.remove_suffix(1);
    }

    string output;
    output.reserve(input.size());

    for (char c : input) {
        if (c != '"') {
            output += c;
        }
    }

    return output;
}

double parse_csv_number_field(string_view input) {
    while (!input.empty() && (input.front() == ' ' || input.front() == '"')) {
        input.remove_prefix(1);
    }

    while (!input.empty() &&
           (input.back() == ' ' || input.back() == '"' || input.back() == '\r')) {
        input.remove_suffix(1);
    }

    if (input.empty()) {
        return MISSING;
    }

    double sign = 1.0;
    if (!input.empty() && input.front() == '-') {
        sign = -1.0;
        input.remove_prefix(1);
    } else if (!input.empty() && input.front() == '+') {
        input.remove_prefix(1);
    }

    double value = 0.0;
    bool has_digit = false;

    while (!input.empty() && input.front() >= '0' && input.front() <= '9') {
        has_digit = true;
        value = (value * 10.0) + (input.front() - '0');
        input.remove_prefix(1);
    }

    if (!input.empty() && input.front() == '.') {
        input.remove_prefix(1);
        double place = 0.1;

        while (!input.empty() && input.front() >= '0' && input.front() <= '9') {
            has_digit = true;
            value += (input.front() - '0') * place;
            place *= 0.1;
            input.remove_prefix(1);
        }
    }

    if (!has_digit) {
        return MISSING;
    }

    return sign * value;
}

bool split_csv_line_views(
    const string& input,
    vector<string_view>& fields
) {
    fields.clear();
    fields.reserve(8);

    bool inside_quotes = false;
    size_t field_start = 0;

    for (size_t i = 0; i < input.size(); i++) {
        char current_char = input[i];

        if (current_char == '"') {
            inside_quotes = !inside_quotes;
        } else if (current_char == ',' && !inside_quotes) {
            fields.emplace_back(input.data() + field_start, i - field_start);
            field_start = i + 1;
        }
    }

    fields.emplace_back(input.data() + field_start, input.size() - field_start);
    return fields.size() >= 8;
}

int parse_two_digit_date_part(string_view input) {
    if (input.size() < 2) {
        return 0;
    }

    return ((input[0] - '0') * 10) + (input[1] - '0');
}

int parse_four_digit_date_part(string_view input) {
    if (input.size() < 4) {
        return 0;
    }

    return ((input[0] - '0') * 1000) +
           ((input[1] - '0') * 100) +
           ((input[2] - '0') * 10) +
           (input[3] - '0');
}

/*

The function grab_data takes CSV file
and turn it into a string. I.E, creating
a vector of strings, strings of the form
a,b,c,d,e...

*/

vector<string> grab_data(string input_file) {
    ifstream file(input_file);

    if (!file) {
        cerr << "File could not be opened: " << input_file << endl;
        return {};
    }

    vector<string> lines;
    lines.reserve(100000);

    string line;

    while (getline(file, line)) {
        lines.push_back(line);
    }

    file.close();

    cerr << "Stored " << lines.size() << " lines from " << input_file << "." << endl;
    return lines;
}

//___________________________________________________________
/*

The function parse_data takes a string
of form a,b,c,d,e and turns it into a
vector of the form [1] = a, [2] = b,
[3] = c... so on.

*/

vector<string> parse_data(const string& input) {
    vector<string> values;
    values.reserve(12);

    string value = "";
    bool inside_quotes = false;

    for (size_t i = 0; i < input.size(); i++) {
        char current_char = input[i];

        if (current_char == '"') {
            inside_quotes = !inside_quotes;
        }
        else if (current_char == ',' && !inside_quotes) {
            values.push_back(value);
            value = "";
        }
        else {
            value += current_char;
        }
    }

    values.push_back(value);

    return values;
}

//___________________________________________________________
/*

I'm popping a little helper function in
here so that it can auto-detect missing
values in the following function.

*/

double valid_stod(string input) {
    input.erase(remove(input.begin(), input.end(), '\r'), input.end());
    input.erase(remove(input.begin(), input.end(), ' '), input.end());
    input.erase(remove(input.begin(), input.end(), '"'), input.end());

    if (input == "") {
        return MISSING;
    }

    return stod(input);
}

//___________________________________________________________
/*

This function will take the single line vector from
parse_data and transition it from a vector of strings
to the DailyData struct.

This is the original parser path for the older CSV format.

*/

DailyData stoDD(const vector<string>& input) {
    DailyData output;
    output.valid = true;

    output.stationID = "";
    output.stationName = "";
    output.latitude = MISSING;
    output.longitude = MISSING;
    output.elevation = MISSING;

    if (input.size() < 10) {
        cerr << "Bad row: expected 10 columns but found " << input.size() << endl;
        output.valid = false;
        return output;
    }

    string date = input[5];
    date.erase(remove(date.begin(), date.end(), '"'), date.end());
    date.erase(remove(date.begin(), date.end(), '\r'), date.end());
    date.erase(remove(date.begin(), date.end(), ' '), date.end());

    if (date.size() < 10) {
        cerr << "Bad row: invalid date format [" << date << "]" << endl;
        output.valid = false;
        return output;
    }

    output.year = stoi(date.substr(0, 4));
    output.month = stoi(date.substr(5, 2));
    output.day = stoi(date.substr(8, 2));

    output.daily_precip = valid_stod(input[6]);
    output.daily_snowfall = valid_stod(input[7]);
    output.tmax_d = valid_stod(input[8]);
    output.tmin_d = valid_stod(input[9]);

    if (output.tmax_d == MISSING || output.tmin_d == MISSING) {
        output.tavg_d = MISSING;
    } else {
        output.tavg_d = (output.tmax_d + output.tmin_d) / 2;
    }

    return output;
}

//___________________________________________________________
/*

This function parses the simplified app-ready NOAA bulk-data format:

station_id,station_name,latitude,longitude,elevation,date,tmax,tmin

This format is produced by filter_ghcn_years.py after filtering the
GHCN-Daily yearly bulk files. It is temperature-only, so precipitation
and snowfall are intentionally set to MISSING.

*/

DailyData stoDD_app_ready_temperature(const vector<string>& input) {
    DailyData output;
    output.valid = true;

    output.stationID = "";
    output.stationName = "";
    output.latitude = MISSING;
    output.longitude = MISSING;
    output.elevation = MISSING;

    if (input.size() < 8) {
        cerr << "Bad app-ready temperature row: expected 8 columns but found " << input.size() << endl;
        output.valid = false;
        return output;
    }

    output.stationID = input[0];
    output.stationID.erase(remove(output.stationID.begin(), output.stationID.end(), '"'), output.stationID.end());
    output.stationID.erase(remove(output.stationID.begin(), output.stationID.end(), '\r'), output.stationID.end());
    output.stationID.erase(remove(output.stationID.begin(), output.stationID.end(), ' '), output.stationID.end());

    output.stationName = input[1];
    output.stationName.erase(remove(output.stationName.begin(), output.stationName.end(), '"'), output.stationName.end());
    output.stationName.erase(remove(output.stationName.begin(), output.stationName.end(), '\r'), output.stationName.end());

    if (output.stationName == "") {
        output.stationName = output.stationID;
    }

    output.latitude = valid_stod(input[2]);
    output.longitude = valid_stod(input[3]);
    output.elevation = valid_stod(input[4]);

    string date = input[5];
    date.erase(remove(date.begin(), date.end(), '"'), date.end());
    date.erase(remove(date.begin(), date.end(), '\r'), date.end());
    date.erase(remove(date.begin(), date.end(), ' '), date.end());

    if (date.size() < 10) {
        cerr << "Bad app-ready temperature row: invalid date format [" << date << "]" << endl;
        output.valid = false;
        return output;
    }

    output.year = stoi(date.substr(0, 4));
    output.month = stoi(date.substr(5, 2));
    output.day = stoi(date.substr(8, 2));

    output.daily_precip = MISSING;
    output.daily_snowfall = MISSING;

    output.tmax_d = valid_stod(input[6]);
    output.tmin_d = valid_stod(input[7]);

    if (output.tmax_d == MISSING || output.tmin_d == MISSING) {
        output.tavg_d = MISSING;
    } else {
        output.tavg_d = (output.tmax_d + output.tmin_d) / 2;
    }

    return output;
}

DailyData stoDD_app_ready_temperature_line(const string& input) {
    DailyData output;
    output.valid = true;

    output.stationID = "";
    output.stationName = "";
    output.latitude = MISSING;
    output.longitude = MISSING;
    output.elevation = MISSING;

    vector<string_view> fields;
    if (!split_csv_line_views(input, fields)) {
        cerr << "Bad app-ready temperature row: expected at least 8 columns" << endl;
        output.valid = false;
        return output;
    }

    output.stationID = clean_csv_text_field(fields[0]);
    output.stationName = clean_csv_text_field(fields[1]);

    if (output.stationName == "") {
        output.stationName = output.stationID;
    }

    if (output.stationID == "") {
        output.valid = false;
        return output;
    }

    output.latitude = parse_csv_number_field(fields[2]);
    output.longitude = parse_csv_number_field(fields[3]);
    output.elevation = parse_csv_number_field(fields[4]);

    string_view date = fields[5];
    while (!date.empty() && (date.front() == ' ' || date.front() == '"')) {
        date.remove_prefix(1);
    }

    if (date.size() < 10) {
        cerr << "Bad app-ready temperature row: invalid date format" << endl;
        output.valid = false;
        return output;
    }

    output.year = parse_four_digit_date_part(date.substr(0, 4));
    output.month = parse_two_digit_date_part(date.substr(5, 2));
    output.day = parse_two_digit_date_part(date.substr(8, 2));

    output.daily_precip = MISSING;
    output.daily_snowfall = MISSING;

    output.tmax_d = parse_csv_number_field(fields[6]);
    output.tmin_d = parse_csv_number_field(fields[7]);

    if (output.tmax_d == MISSING || output.tmin_d == MISSING) {
        output.tavg_d = MISSING;
    } else {
        output.tavg_d = (output.tmax_d + output.tmin_d) / 2;
    }

    return output;
}

//___________________________________________________________
/*

This function applies everything so far,
creating a vector of DailyData structs
with all of the data on a CSV list. This
accounts for missing values and malformed
lines of CSV.

This is the original parser path.

*/

vector<DailyData> create_daily_dataset(const vector<string>& lines) {
    vector<DailyData> dataset;
    dataset.reserve(lines.size());

    for (size_t i = 1; i < lines.size(); i++) {
        vector<string> values = parse_data(lines[i]);
        DailyData day = stoDD(values);

        if (day.valid) {
            dataset.push_back(day);
        } else {
            cerr << "Skipping bad row at CSV line " << i + 1 << endl;
        }
    }

    return dataset;
}

//___________________________________________________________
/*

This function creates a daily dataset from the simplified app-ready
NOAA temperature CSV format:

station_id,station_name,latitude,longitude,elevation,date,tmax,tmin

*/

vector<DailyData> create_app_ready_temperature_dataset(const vector<string>& lines) {
    vector<DailyData> dataset;
    dataset.reserve(lines.size());

    for (size_t i = 1; i < lines.size(); i++) {
        DailyData day = stoDD_app_ready_temperature_line(lines[i]);

        if (day.valid) {
            dataset.push_back(day);
        } else {
            cerr << "Skipping bad app-ready temperature row at CSV line " << i + 1 << endl;
        }
    }

    return dataset;
}

//___________________________________________________________
/*

This function utilizes something new that I have
not used before! It is called a lambda function,
and it was reccomended to me by chatGPT for this
particular sorting function. I was gonna make my
own bubble sorting algorithm, but this seems much
simpler and less time consuming.

*/

vector<DailyData> sort_daily_dataset(vector<DailyData> input) {
    sort(input.begin(), input.end(), [](const DailyData& a, const DailyData& b) {
        if (a.year != b.year) {
            return a.year < b.year;
        }

        if (a.month != b.month) {
            return a.month < b.month;
        }

        return a.day < b.day;
    });

    return input;
}

//___________________________________________________________
/*

Leap-year helper used by monthly rollups to calculate calendar-day coverage.

*/

bool isLeapYear(int year) {
    return (year % 4 == 0 && year % 100 != 0) || (year % 400 == 0);
}

//___________________________________________________________
/*

Return the calendar-day count for a month, including leap-year February.

*/

int daysInMonth(int year, int month) {
    if (month == 1 || month == 3 || month == 5 || month == 7 ||
        month == 8 || month == 10 || month == 12) {
        return 31;
    }

    if (month == 4 || month == 6 || month == 9 || month == 11) {
        return 30;
    }

    if (month == 2) {
        if (isLeapYear(year)) {
            return 29;
        } else {
            return 28;
        }
    }

    return 0;
}

//___________________________________________________________
/*

Next up is converting all of the daily data
into monthly data. To do this accurately, I'll
need to make sure that I am collecting how
many data points are missing and whatnot.

*/

vector<MonthlyData> create_monthly_dataset(const vector<DailyData>& input) {
    vector<MonthlyData> monthly_dataset;
    monthly_dataset.reserve(input.size() / 28 + 1);

    if (input.size() == 0) {
        cerr << "Empty Input" << endl;
        return monthly_dataset;
    }

    int current_year = input[0].year;
    int current_month = input[0].month;

    double sum_tmin = 0;
    double sum_tmax = 0;
    double sum_precip = 0;
    double sum_snowfall = 0;

    int count_tmax = 0;
    int count_tmin = 0;

    int missing_tmin = 0;
    int missing_tmax = 0;
    int missing_precip = 0;
    int missing_snowfall = 0;
    int days_observed = 0;

    MonthlyData temp_md;

    for (size_t i = 0; i < input.size(); i++) {

        if (input[i].month != current_month || input[i].year != current_year) {

            temp_md.month = current_month;
            temp_md.year = current_year;
            temp_md.days_observed = days_observed;
            temp_md.days_expected = daysInMonth(current_year, current_month);
            temp_md.missing_calendar_days = temp_md.days_expected - temp_md.days_observed;
            temp_md.missing_tmax_m = missing_tmax + temp_md.missing_calendar_days;
            temp_md.missing_tmin_m = missing_tmin + temp_md.missing_calendar_days;
            temp_md.missing_daily_precip_m = missing_precip;
            temp_md.missing_daily_snowfall_m = missing_snowfall;
            temp_md.total_monthly_precip = sum_precip;
            temp_md.total_monthly_snowfall = sum_snowfall;

            if (count_tmax > 0) {
                temp_md.tmax_m = (sum_tmax / count_tmax);
            } else {
                temp_md.tmax_m = MISSING;
            }

            if (count_tmin > 0) {
                temp_md.tmin_m = (sum_tmin / count_tmin);
            } else {
                temp_md.tmin_m = MISSING;
            }

            if (count_tmax > 0 && count_tmin > 0) {
                temp_md.tavg_m = ((sum_tmin / count_tmin) + (sum_tmax / count_tmax)) / 2;
            } else {
                temp_md.tavg_m = MISSING;
            }

            monthly_dataset.push_back(temp_md);

            sum_tmin = 0;
            sum_tmax = 0;
            sum_precip = 0;
            sum_snowfall = 0;

            count_tmax = 0;
            count_tmin = 0;

            missing_tmin = 0;
            missing_tmax = 0;
            missing_precip = 0;
            missing_snowfall = 0;
            days_observed = 0;

            current_month = input[i].month;
            current_year = input[i].year;
        }

        days_observed++;

        if (input[i].tmin_d != MISSING) {
            sum_tmin += input[i].tmin_d;
            count_tmin++;
        } else {
            missing_tmin++;
        }

        if (input[i].tmax_d != MISSING) {
            sum_tmax += input[i].tmax_d;
            count_tmax++;
        } else {
            missing_tmax++;
        }

        if (input[i].daily_precip != MISSING) {
            sum_precip += input[i].daily_precip;
        } else {
            missing_precip++;
        }

        if (input[i].daily_snowfall != MISSING) {
            sum_snowfall += input[i].daily_snowfall;
        } else {
            missing_snowfall++;
        }
    }

    temp_md.month = current_month;
    temp_md.year = current_year;
    temp_md.days_observed = days_observed;
    temp_md.days_expected = daysInMonth(current_year, current_month);
    temp_md.missing_calendar_days = temp_md.days_expected - temp_md.days_observed;
    temp_md.missing_tmax_m = missing_tmax + temp_md.missing_calendar_days;
    temp_md.missing_tmin_m = missing_tmin + temp_md.missing_calendar_days;
    temp_md.missing_daily_precip_m = missing_precip;
    temp_md.missing_daily_snowfall_m = missing_snowfall;
    temp_md.total_monthly_precip = sum_precip;
    temp_md.total_monthly_snowfall = sum_snowfall;

    if (count_tmax > 0) {
        temp_md.tmax_m = (sum_tmax / count_tmax);
    } else {
        temp_md.tmax_m = MISSING;
    }

    if (count_tmin > 0) {
        temp_md.tmin_m = (sum_tmin / count_tmin);
    } else {
        temp_md.tmin_m = MISSING;
    }

    if (count_tmax > 0 && count_tmin > 0) {
        temp_md.tavg_m = ((sum_tmin / count_tmin) + (sum_tmax / count_tmax)) / 2;
    } else {
        temp_md.tavg_m = MISSING;
    }

    monthly_dataset.push_back(temp_md);

    return monthly_dataset;
}

//___________________________________________________________
/*

The next chunk of code is going to write out these accumulated
monthly data points and put it back into CSV format. This is
not a process that I am too familiar with, but I imagine it'll
be somewhat straightforward.

*/

void export_monthly_dataset(string output_file, const vector<MonthlyData>& input) {

    ofstream file(output_file);

    if (!file) {
        cerr << "Output file could not be opened" << endl;
        return;
    }

    file << "\"YEAR\","
         << "\"MONTH\","
         << "\"TAVG\","
         << "\"AVG_TMAX\","
         << "\"AVG_TMIN\","
         << "\"TOTAL_PRCP\","
         << "\"TOTAL_SNOW\","
         << "\"MISSING_TMAX\","
         << "\"MISSING_TMIN\","
         << "\"MISSING_PRCP\","
         << "\"MISSING_SNOW\""
         << endl;

    for (size_t i = 0; i < input.size(); i++) {
        file
            << "\"" << input[i].year << "\","
            << "\"" << input[i].month << "\","
            << "\"" << input[i].tavg_m << "\","
            << "\"" << input[i].tmax_m << "\","
            << "\"" << input[i].tmin_m << "\","
            << "\"" << input[i].total_monthly_precip << "\","
            << "\"" << input[i].total_monthly_snowfall << "\","
            << "\"" << input[i].missing_tmax_m << "\","
            << "\"" << input[i].missing_tmin_m << "\","
            << "\"" << input[i].missing_daily_precip_m << "\","
            << "\"" << input[i].missing_daily_snowfall_m << "\""
            << endl;
    }

    file.close();

    cerr << "Successfully exported data to CSV file " << output_file << "." << endl;
}

//___________________________________________________________
