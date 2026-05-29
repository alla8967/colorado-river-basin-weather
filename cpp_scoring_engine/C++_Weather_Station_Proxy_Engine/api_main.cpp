#include <iostream>
#include <iomanip>
#include <string>
#include <cstdlib>

#include "STATION_PROXY_ENGINE.h"

using namespace std;

const string DEFAULT_TARGET_INPUT_FILE = "ml_reconstruction/NOAA_Inventory_Sort/target_daily_app_ready.csv";
const string DEFAULT_HUB_INPUT_FILE = "ml_reconstruction/NOAA_Inventory_Sort/hub_daily_app_ready.csv";

string json_escape(const string& input) {
    string output;

    for (char c : input) {
        if (c == '"') {
            output += "\\\"";
        } else if (c == '\\') {
            output += "\\\\";
        } else if (c == '\n') {
            output += "\\n";
        } else if (c == '\r') {
            output += "\\r";
        } else if (c == '\t') {
            output += "\\t";
        } else {
            output += c;
        }
    }

    return output;
}

string get_configured_path(
    int argc,
    char* argv[],
    int argument_index,
    const char* environment_name,
    const string& default_path
) {
    if (argc > argument_index) {
        return argv[argument_index];
    }

    const char* environment_value = getenv(environment_name);
    if (environment_value != nullptr && string(environment_value) != "") {
        return environment_value;
    }

    return default_path;
}

void print_json_error(const string& message) {
    cout << "{";
    cout << "\"status\":\"error\",";
    cout << "\"message\":\"" << json_escape(message) << "\"";
    cout << "}";
}

int main(int argc, char* argv[]) {
    cout << fixed << setprecision(6);

    if (argc < 3) {
        print_json_error("Missing latitude or longitude");
        return 1;
    }

    double latitude = 0.0;
    double longitude = 0.0;

    try {
        latitude = stod(argv[1]);
        longitude = stod(argv[2]);
    } catch (...) {
        print_json_error("Latitude and longitude must be valid numbers");
        return 1;
    }

    string target_input_file = get_configured_path(
        argc,
        argv,
        3,
        "STATION_PROXY_TARGET_FILE",
        DEFAULT_TARGET_INPUT_FILE
    );
    string hub_input_file = get_configured_path(
        argc,
        argv,
        4,
        "STATION_PROXY_HUB_FILE",
        DEFAULT_HUB_INPUT_FILE
    );

    StationProxyEngine engine;

    bool loaded = engine.load(
        target_input_file,
        hub_input_file
    );

    if (!loaded) {
        cout << "{";
        cout << "\"status\":\"error\",";
        cout << "\"message\":\"StationProxyEngine failed to load target and/or hub station data\",";
        cout << "\"targetInputFile\":\"" << json_escape(target_input_file) << "\",";
        cout << "\"hubInputFile\":\"" << json_escape(hub_input_file) << "\"";
        cout << "}";
        return 1;
    }

    cout << engine.analyze_location_json(latitude, longitude);

    return 0;
}
