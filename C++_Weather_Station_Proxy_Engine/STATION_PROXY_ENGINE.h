#ifndef STATION_PROXY_ENGINE_H
#define STATION_PROXY_ENGINE_H

#include <string>
#include <vector>
#include <sstream>

#include "station_dataset.h"
#include "station_pair_score.h"

using namespace std;

/*

StationProxyEngine is the reusable core engine for the NOAA weather station
proxy tool.

This class owns the loaded target and hub station datasets, so the large CSV
files only need to be loaded once. Different wrappers can use this same class:

1. one-shot command line executable
2. persistent stdin/stdout server
3. future Python/pybind11 module
4. future C++ HTTP service

The goal is to keep the core station matching logic out of main() files.

*/

class StationProxyEngine {
private:
    vector<StationDataset> target_stations;
    vector<StationDataset> hub_stations;

    string target_input_file;
    string hub_input_file;

    int top_match_limit;
    bool loaded;

    string json_escape(const string& input) const;
    void write_json_string_field(
        ostringstream& out,
        const string& key,
        const string& value,
        bool trailing_comma
    ) const;

    void write_json_number_field(
        ostringstream& out,
        const string& key,
        double value,
        bool trailing_comma
    ) const;

    void write_json_size_field(
        ostringstream& out,
        const string& key,
        size_t value,
        bool trailing_comma
    ) const;

    void write_station_record_fields(
        ostringstream& out,
        const StationDataset& station,
        bool trailing_comma
    ) const;

    void write_station_json(
        ostringstream& out,
        const StationDataset& station
    ) const;

    bool is_hub_station_id(const string& station_id) const;

    bool is_target_station_id(const string& station_id) const;

    const StationDataset* find_station_by_id(const string& station_id) const;

    void write_pair_score_json(
        ostringstream& out,
        const StationPairScore& score,
        int rank
    ) const;

    vector<StationPairScore> find_top_proxy_matches_local(
        const StationDataset& target_station,
        const vector<StationDataset>& candidate_stations,
        int top_n
    ) const;

    vector<StationPairScore> find_ranked_proxy_matches_local(
        const StationDataset& target_station,
        const vector<StationDataset>& candidate_stations
    ) const;

    StationDataset with_derived_summaries(const StationDataset& station) const;

    void enrich_station_metadata_from_candidates();

    void add_monthly_metrics_to_score(
        StationPairScore& score,
        const StationDataset& target_station,
        const StationDataset& proxy_station
    ) const;

    void write_monthly_comparison_json(
        ostringstream& out,
        const StationDataset& target_station,
        const StationDataset& proxy_station,
        int month_limit
    ) const;

    void write_daily_comparison_json(
        ostringstream& out,
        const StationDataset& target_station,
        const StationDataset& proxy_station,
        int day_limit
    ) const;

    void write_daily_comparison_option_json(
        ostringstream& out,
        const StationPairScore& score,
        const StationDataset& target_station,
        const StationDataset& proxy_station,
        int rank,
        int day_limit
    ) const;

public:
    StationProxyEngine();

    bool load(
        const string& target_file,
        const string& hub_file
    );

    bool is_loaded() const;

    int target_station_count() const;
    int hub_station_count() const;

    string analyze_location_json(
        double latitude,
        double longitude
    ) const;
};

#endif
