#include "similarity_scores.h"
#include "station_dataset.h"

/*
This small executable is an independent validation tool for the Python
temperature reconstruction workflow.

The Python model writes two app-ready station CSVs:

1. an "actual" station CSV with the real target daily average temperature
2. a "predicted" station CSV with the model's reconstructed daily average temperature

Both files use the same app-ready temperature format as the rest of the C++
engine:

station_id,station_name,latitude,longitude,elevation,date,tmax,tmin

For validation files, tmax and tmin are intentionally set to the same value so
the C++ loader calculates tavg as exactly that value. This lets the existing
C++ daily similarity code compare actual vs predicted TAVG without needing a
separate prediction-specific parser.

This tool does not train a model. It only scores the prediction that Python
already produced.
*/

#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>

using namespace std;

void print_usage(const string& program_name) {
    cerr << "Usage: " << program_name << " <actual_station_csv> <predicted_station_csv>" << endl;
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        print_usage(argv[0]);
        return EXIT_FAILURE;
    }

    string actual_file = argv[1];
    string predicted_file = argv[2];

    StationDataset actual_station = load_app_ready_temperature_station_dataset(actual_file);
    StationDataset predicted_station = load_app_ready_temperature_station_dataset(predicted_file);

    if (!actual_station.valid) {
        cerr << "Could not load actual station CSV: " << actual_file << endl;
        return EXIT_FAILURE;
    }

    if (!predicted_station.valid) {
        cerr << "Could not load predicted station CSV: " << predicted_file << endl;
        return EXIT_FAILURE;
    }

    SimilarityResult similarity = calculate_daily_tavg_similarity(
        actual_station,
        predicted_station
    );

    cout << fixed << setprecision(4);
    cout << endl;
    cout << "C++ prediction similarity validation" << endl;
    cout << "====================================" << endl;
    cout << "Actual CSV: " << actual_file << endl;
    cout << "Predicted CSV: " << predicted_file << endl;
    cout << endl;
    cout << "Actual station: " << actual_station.metadata.stationID << endl;
    cout << "Predicted station: " << predicted_station.metadata.stationID << endl;
    cout << "Actual rows loaded: " << actual_station.daily.size() << endl;
    cout << "Predicted rows loaded: " << predicted_station.daily.size() << endl;
    cout << "Paired days compared: " << similarity.range.paired_count << endl;
    cout << endl;
    cout << "Daily correlation: " << similarity.correlation << endl;
    cout << "Daily MAD / MAE: " << similarity.mean_absolute_difference << " F" << endl;
    cout << "Daily RMSE: " << similarity.rmse << " F" << endl;

    if (similarity.range.has_valid_pairs) {
        cout << "Compared date range: "
             << similarity.range.start_date.year << "-"
             << setw(2) << setfill('0') << similarity.range.start_date.month << "-"
             << setw(2) << setfill('0') << similarity.range.start_date.day
             << " through "
             << setfill(' ') << similarity.range.end_date.year << "-"
             << setw(2) << setfill('0') << similarity.range.end_date.month << "-"
             << setw(2) << setfill('0') << similarity.range.end_date.day
             << setfill(' ') << endl;
    }

    return EXIT_SUCCESS;
}
