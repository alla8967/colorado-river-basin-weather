// Purpose: Runs the station proxy engine as a persistent stdin/stdout service for FastAPI.

#include <iostream>
#include <sstream>
#include <string>
#include <cstdlib>

#include "STATION_PROXY_ENGINE.h"

using namespace std;

const string DEFAULT_TARGET_INPUT_FILE = "../NOAA_Inventory_Sort/target_daily_app_ready.csv";
const string DEFAULT_HUB_INPUT_FILE = "../NOAA_Inventory_Sort/hub_daily_app_ready.csv";

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

string get_configured_path(const char* environment_name, const string& default_path) {
    const char* environment_value = getenv(environment_name);

    if (environment_value != nullptr && string(environment_value) != "") {
        return environment_value;
    }

    return default_path;
}

bool parse_coordinate_request(
    const string& line,
    double& latitude,
    double& longitude
) {
    stringstream input(line);
    input >> latitude >> longitude;

    return !input.fail();
}

bool is_shutdown_command(const string& line) {
    return line == "quit" || line == "exit" || line == "shutdown";
}

bool is_blank_line(const string& line) {
    return line == "" || line == "\n" || line == "\r";
}

bool load_engine(StationProxyEngine& engine) {
    string target_input_file = get_configured_path(
        "STATION_PROXY_TARGET_FILE",
        DEFAULT_TARGET_INPUT_FILE
    );
    string hub_input_file = get_configured_path(
        "STATION_PROXY_HUB_FILE",
        DEFAULT_HUB_INPUT_FILE
    );

    cerr << "Loading target stations from: " << target_input_file << endl;
    cerr << "Loading hub stations from: " << hub_input_file << endl;

    bool loaded = engine.load(target_input_file, hub_input_file);

    if (!loaded) {
        cerr << "ERROR: Failed to load target and/or hub station data." << endl;
        cerr << "Check that this executable is being run from the Station_Engine_Server folder." << endl;
        cerr << "Configured data files:" << endl;
        cerr << "  " << target_input_file << endl;
        cerr << "  " << hub_input_file << endl;
        return false;
    }

    cerr << "Loaded " << engine.target_station_count() << " targets and "
         << engine.hub_station_count() << " hubs" << endl;

    return true;
}

void write_error_response(const string& message) {
    cout << "{\"status\":\"error\",\"message\":\"" << json_escape(message) << "\"}" << endl;
    cout.flush();
}

void handle_coordinate_request(
    StationProxyEngine& engine,
    const string& line
) {
    double latitude = 0.0;
    double longitude = 0.0;

    if (!parse_coordinate_request(line, latitude, longitude)) {
        write_error_response("Invalid input. Expected: latitude longitude");
        return;
    }

    try {
        cout << engine.analyze_location_json(latitude, longitude) << endl;
        cout.flush();
    } catch (const exception& error) {
        cerr << "Exception while analyzing location: " << error.what() << endl;
        write_error_response("C++ engine exception while analyzing location");
    } catch (...) {
        cerr << "Unknown exception while analyzing location." << endl;
        write_error_response("Unknown C++ engine exception while analyzing location");
    }
}

int main() {
    ios::sync_with_stdio(false);

    StationProxyEngine engine;
    if (!load_engine(engine)) {
        return 1;
    }

    cerr << "READY" << endl;

    string line;
    while (getline(cin, line)) {
        if (is_blank_line(line)) {
            continue;
        }

        if (is_shutdown_command(line)) {
            cerr << "Shutdown command received." << endl;
            break;
        }

        handle_coordinate_request(engine, line);
    }

    return 0;
}
