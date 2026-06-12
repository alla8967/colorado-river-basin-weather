// Purpose: Implements the high-level station proxy engine that loads station datasets and ranks candidate proxy stations.

#include "STATION_PROXY_ENGINE.h"

#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

#include "station_dataset.h"
#include "station_locator.h"
#include "station_pair_score.h"
#include "similarity_scores.h"
#include "csv_filereader.h"

using namespace std;

StationProxyEngine::StationProxyEngine() {
    target_input_file = "";
    hub_input_file = "";
    top_match_limit = 5;
    loaded = false;
}

string StationProxyEngine::json_escape(const string& input) const {
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

void StationProxyEngine::write_json_string_field(
    ostringstream& out,
    const string& key,
    const string& value,
    bool trailing_comma
) const {
    out << "\"" << key << "\":\"" << json_escape(value) << "\"";
    if (trailing_comma) {
        out << ",";
    }
}

void StationProxyEngine::write_json_number_field(
    ostringstream& out,
    const string& key,
    double value,
    bool trailing_comma
) const {
    out << "\"" << key << "\":" << value;
    if (trailing_comma) {
        out << ",";
    }
}

void StationProxyEngine::write_json_size_field(
    ostringstream& out,
    const string& key,
    size_t value,
    bool trailing_comma
) const {
    out << "\"" << key << "\":" << value;
    if (trailing_comma) {
        out << ",";
    }
}

void StationProxyEngine::write_station_record_fields(
    ostringstream& out,
    const StationDataset& station,
    bool trailing_comma
) const {
    if (!station.daily.empty()) {
        write_json_number_field(out, "preparedObservationStartYear", station.daily.front().year, true);
        write_json_number_field(out, "preparedObservationEndYear", station.daily.back().year, true);
        write_json_number_field(out, "preparedObservationYears", station.daily.back().year - station.daily.front().year + 1, true);
    } else {
        write_json_number_field(out, "preparedObservationStartYear", 0, true);
        write_json_number_field(out, "preparedObservationEndYear", 0, true);
        write_json_number_field(out, "preparedObservationYears", 0, true);
    }

    write_json_number_field(out, "fullObservationStartYear", station.metadata.fullObservationStartYear, true);
    write_json_number_field(out, "fullObservationEndYear", station.metadata.fullObservationEndYear, true);
    write_json_number_field(out, "fullObservationYears", station.metadata.fullObservationYears, trailing_comma);
}

void StationProxyEngine::write_station_json(
    ostringstream& out,
    const StationDataset& station
) const {
    out << "{";
    write_json_string_field(out, "stationID", station.metadata.stationID, true);
    write_json_string_field(out, "stationName", station.metadata.stationName, true);
    write_json_string_field(out, "stationRole", is_hub_station_id(station.metadata.stationID) ? "hub" : "target", true);
    out << "\"isHubStation\":" << (is_hub_station_id(station.metadata.stationID) ? "true" : "false") << ",";
    out << "\"isTargetStation\":" << (is_target_station_id(station.metadata.stationID) ? "true" : "false") << ",";
    write_json_number_field(out, "latitude", station.metadata.latitude, true);
    write_json_number_field(out, "longitude", station.metadata.longitude, true);
    write_json_number_field(out, "elevation", station.metadata.elevation, true);
    write_json_size_field(out, "dailyRecords", station.daily.size(), true);
    write_json_size_field(out, "monthlyRecords", station.monthly.size(), true);
    write_json_size_field(out, "seasonalRecords", station.seasonal.size(), true);
    write_station_record_fields(out, station, false);
    out << "}";
}

bool StationProxyEngine::is_hub_station_id(const string& station_id) const {
    return hub_station_by_id.find(station_id) != hub_station_by_id.end();
}

bool StationProxyEngine::is_target_station_id(const string& station_id) const {
    return target_station_by_id.find(station_id) != target_station_by_id.end();
}

const StationDataset* StationProxyEngine::find_station_by_id(const string& station_id) const {
    auto station = station_by_id.find(station_id);
    return station == station_by_id.end() ? nullptr : station->second;
}

void StationProxyEngine::write_pair_score_json(
    ostringstream& out,
    const StationPairScore& score,
    int rank
) const {
    const StationDataset* target_station = find_station_by_id(score.stationID_a);
    const StationDataset* proxy_station = find_station_by_id(score.stationID_b);

    out << "{";
    write_json_number_field(out, "rank", rank, true);
    write_json_number_field(out, "score", score.score, true);

    out << "\"targetStation\":{";
    write_json_string_field(out, "stationID", score.stationID_a, true);
    write_json_string_field(out, "stationName", score.stationName_a, true);
    write_json_string_field(out, "stationRole", is_hub_station_id(score.stationID_a) ? "hub" : "target", true);
    out << "\"isHubStation\":" << (is_hub_station_id(score.stationID_a) ? "true" : "false") << ",";
    out << "\"isTargetStation\":" << (is_target_station_id(score.stationID_a) ? "true" : "false");
    if (target_station != nullptr) {
        out << ",";
        write_json_number_field(out, "latitude", target_station->metadata.latitude, true);
        write_json_number_field(out, "longitude", target_station->metadata.longitude, true);
        write_json_number_field(out, "elevation", target_station->metadata.elevation, true);
        write_json_size_field(out, "dailyRecords", target_station->daily.size(), true);
        write_station_record_fields(out, *target_station, false);
    }
    out << "},";

    out << "\"proxyStation\":{";
    write_json_string_field(out, "stationID", score.stationID_b, true);
    write_json_string_field(out, "stationName", score.stationName_b, true);
    write_json_string_field(out, "stationRole", is_hub_station_id(score.stationID_b) ? "hub" : "target", true);
    out << "\"isHubStation\":" << (is_hub_station_id(score.stationID_b) ? "true" : "false") << ",";
    out << "\"isTargetStation\":" << (is_target_station_id(score.stationID_b) ? "true" : "false");
    if (proxy_station != nullptr) {
        out << ",";
        write_json_number_field(out, "latitude", proxy_station->metadata.latitude, true);
        write_json_number_field(out, "longitude", proxy_station->metadata.longitude, true);
        write_json_number_field(out, "elevation", proxy_station->metadata.elevation, true);
        write_json_size_field(out, "dailyRecords", proxy_station->daily.size(), true);
        write_station_record_fields(out, *proxy_station, false);
    }
    out << "},";

    write_json_number_field(out, "distanceKm", score.distance_km, true);
    write_json_number_field(out, "elevationDifferenceM", score.elevation_difference_m, true);
    write_json_number_field(out, "dailyCorrelation", score.daily_correlation, true);
    write_json_number_field(out, "dailyMAD", score.daily_mad, true);
    write_json_number_field(out, "dailyRMSE", score.daily_rmse, true);
    write_json_number_field(out, "pairedDays", score.paired_days, true);
    write_json_number_field(out, "monthlyCorrelation", score.monthly_correlation, true);
    write_json_number_field(out, "monthlyMAD", score.monthly_mad, true);
    write_json_number_field(out, "monthlyRMSE", score.monthly_rmse, true);
    write_json_number_field(out, "pairedMonths", score.paired_months, false);
    out << "}";
}

vector<StationPairScore> StationProxyEngine::find_top_proxy_matches_local(
    const StationDataset& target_station,
    const vector<StationDataset>& candidate_stations,
    int top_n
) const {
    vector<StationPairScore> scores = find_ranked_proxy_matches_local(
        target_station,
        candidate_stations
    );

    if (top_n < 0) {
        top_n = 0;
    }

    if (scores.size() > static_cast<size_t>(top_n)) {
        scores.resize(top_n);
    }

    return scores;
}

vector<StationPairScore> StationProxyEngine::find_ranked_proxy_matches_local(
    const StationDataset& target_station,
    const vector<StationDataset>& candidate_stations
) const {
    const double MAX_CANDIDATE_DISTANCE_KM = 300.0;
    const double MAX_CANDIDATE_ELEVATION_DIFFERENCE_M = 1500.0;
    const int MIN_PAIRED_DAYS = min(365, static_cast<int>(target_station.daily.size()));

    vector<StationPairScore> scores;
    scores.reserve(candidate_stations.size());

    for (const StationDataset& candidate_station : candidate_stations) {
        if (candidate_station.metadata.stationID == target_station.metadata.stationID) {
            continue;
        }

        StationPairScore score = calculate_station_pair_score(
            target_station,
            candidate_station,
            false
        );

        if (score.score == 0.0) {
            continue;
        }

        if (score.distance_km > MAX_CANDIDATE_DISTANCE_KM) {
            continue;
        }

        if (score.elevation_difference_m > MAX_CANDIDATE_ELEVATION_DIFFERENCE_M) {
            continue;
        }

        if (score.paired_days < MIN_PAIRED_DAYS) {
            continue;
        }

        scores.push_back(score);
    }

    sort(scores.begin(), scores.end(), [](const StationPairScore& a, const StationPairScore& b) {
        return a.score > b.score;
    });

    return scores;
}

void StationProxyEngine::precompute_derived_summaries(
    vector<StationDataset>& stations
) const {
    for (StationDataset& station : stations) {
        if (station.monthly.empty() && !station.daily.empty()) {
            station.monthly = create_monthly_dataset(station.daily);
        }

        if (station.seasonal.empty() && !station.monthly.empty()) {
            station.seasonal = compute_seasonal_data(station.monthly);
        }
    }
}

void StationProxyEngine::rebuild_station_indexes() {
    target_station_by_id.clear();
    hub_station_by_id.clear();
    station_by_id.clear();
    all_station_pointers.clear();

    target_station_by_id.reserve(target_stations.size());
    hub_station_by_id.reserve(hub_stations.size());
    station_by_id.reserve(target_stations.size() + hub_stations.size());
    all_station_pointers.reserve(target_stations.size() + hub_stations.size());

    for (const StationDataset& station : target_stations) {
        target_station_by_id[station.metadata.stationID] = &station;
        station_by_id[station.metadata.stationID] = &station;
        all_station_pointers.push_back(&station);
    }

    for (const StationDataset& station : hub_stations) {
        hub_station_by_id[station.metadata.stationID] = &station;
        if (station_by_id.find(station.metadata.stationID) == station_by_id.end()) {
            station_by_id[station.metadata.stationID] = &station;
        }
        all_station_pointers.push_back(&station);
    }
}

string parent_directory(const string& input_file) {
    size_t slash_position = input_file.find_last_of("/\\");

    if (slash_position == string::npos) {
        return ".";
    }

    return input_file.substr(0, slash_position);
}

struct CandidateRecordMetadata {
    int usable_start_year = 0;
    int usable_end_year = 0;
    int usable_years = 0;
};

map<string, CandidateRecordMetadata> load_candidate_record_metadata(
    const string& candidate_file
) {
    map<string, CandidateRecordMetadata> metadata_by_station_id;
    ifstream file(candidate_file);

    if (!file.is_open()) {
        cerr << "Could not open station candidate metadata file: " << candidate_file << endl;
        return metadata_by_station_id;
    }

    string header;
    getline(file, header);

    string line;
    while (getline(file, line)) {
        vector<string> row = parse_data(line);

        if (row.size() < 12) {
            continue;
        }

        CandidateRecordMetadata metadata;
        metadata.usable_start_year = static_cast<int>(valid_stod(row[9]));
        metadata.usable_end_year = static_cast<int>(valid_stod(row[10]));
        metadata.usable_years = static_cast<int>(valid_stod(row[11]));

        metadata_by_station_id[row[0]] = metadata;
    }

    return metadata_by_station_id;
}

void apply_candidate_record_metadata(
    vector<StationDataset>& stations,
    const map<string, CandidateRecordMetadata>& metadata_by_station_id
) {
    for (StationDataset& station : stations) {
        auto metadata = metadata_by_station_id.find(station.metadata.stationID);

        if (metadata == metadata_by_station_id.end()) {
            continue;
        }

        station.metadata.fullObservationStartYear = metadata->second.usable_start_year;
        station.metadata.fullObservationEndYear = metadata->second.usable_end_year;
        station.metadata.fullObservationYears = metadata->second.usable_years;
    }
}

void StationProxyEngine::enrich_station_metadata_from_candidates() {
    string data_directory = parent_directory(target_input_file);
    map<string, CandidateRecordMetadata> target_metadata = load_candidate_record_metadata(
        data_directory + "/target_station_candidates.csv"
    );
    map<string, CandidateRecordMetadata> hub_metadata = load_candidate_record_metadata(
        data_directory + "/hub_station_candidates.csv"
    );

    apply_candidate_record_metadata(target_stations, target_metadata);
    apply_candidate_record_metadata(hub_stations, hub_metadata);
}

void StationProxyEngine::add_monthly_metrics_to_score(
    StationPairScore& score,
    const StationDataset& target_station,
    const StationDataset& proxy_station
) const {
    SimilarityResult monthly_similarity = calculate_monthly_tavg_similarity(
        target_station,
        proxy_station
    );

    score.monthly_correlation = monthly_similarity.correlation;
    score.monthly_mad = monthly_similarity.mean_absolute_difference;
    score.monthly_rmse = monthly_similarity.rmse;
    score.paired_months = monthly_similarity.range.paired_count;
}

void StationProxyEngine::write_monthly_comparison_json(
    ostringstream& out,
    const StationDataset& target_station,
    const StationDataset& proxy_station,
    int month_limit
) const {
    vector<pair<const MonthlyData*, const MonthlyData*>> paired_months;

    int i = 0;
    int j = 0;

    while (i < static_cast<int>(target_station.monthly.size()) &&
           j < static_cast<int>(proxy_station.monthly.size())) {
        int comparison = compare_monthly_dates(
            target_station.monthly[i],
            proxy_station.monthly[j]
        );

        if (comparison == 0) {
            if (target_station.monthly[i].tavg_m != MISSING &&
                proxy_station.monthly[j].tavg_m != MISSING) {
                paired_months.push_back({
                    &target_station.monthly[i],
                    &proxy_station.monthly[j]
                });
            }

            i++;
            j++;
        } else if (comparison < 0) {
            i++;
        } else {
            j++;
        }
    }

    int start_index = 0;
    if (static_cast<int>(paired_months.size()) > month_limit) {
        start_index = static_cast<int>(paired_months.size()) - month_limit;
    }

    out << "[";
    bool needs_comma = false;

    for (int index = start_index; index < static_cast<int>(paired_months.size()); index++) {
        const MonthlyData* target_month = paired_months[index].first;
        const MonthlyData* proxy_month = paired_months[index].second;

        if (needs_comma) {
            out << ",";
        }

        out << "{";
        write_json_number_field(out, "year", target_month->year, true);
        write_json_number_field(out, "month", target_month->month, true);
        write_json_number_field(out, "targetTavg", target_month->tavg_m, true);
        write_json_number_field(out, "proxyTavg", proxy_month->tavg_m, true);
        write_json_number_field(out, "difference", target_month->tavg_m - proxy_month->tavg_m, false);
        out << "}";

        needs_comma = true;
    }

    out << "]";
}

void StationProxyEngine::write_daily_comparison_json(
    ostringstream& out,
    const StationDataset& target_station,
    const StationDataset& proxy_station,
    int day_limit
) const {
    vector<pair<const DailyData*, const DailyData*>> paired_days;

    int i = 0;
    int j = 0;

    while (i < static_cast<int>(target_station.daily.size()) &&
           j < static_cast<int>(proxy_station.daily.size())) {
        int comparison = compare_daily_dates(
            target_station.daily[i],
            proxy_station.daily[j]
        );

        if (comparison == 0) {
            if (target_station.daily[i].tavg_d != MISSING &&
                proxy_station.daily[j].tavg_d != MISSING) {
                paired_days.push_back({
                    &target_station.daily[i],
                    &proxy_station.daily[j]
                });
            }

            i++;
            j++;
        } else if (comparison < 0) {
            i++;
        } else {
            j++;
        }
    }

    int start_index = 0;
    if (static_cast<int>(paired_days.size()) > day_limit) {
        start_index = static_cast<int>(paired_days.size()) - day_limit;
    }

    out << "[";
    bool needs_comma = false;

    for (int index = start_index; index < static_cast<int>(paired_days.size()); index++) {
        const DailyData* target_day = paired_days[index].first;
        const DailyData* proxy_day = paired_days[index].second;

        if (needs_comma) {
            out << ",";
        }

        out << "{";
        write_json_number_field(out, "year", target_day->year, true);
        write_json_number_field(out, "month", target_day->month, true);
        write_json_number_field(out, "day", target_day->day, true);
        write_json_number_field(out, "targetTavg", target_day->tavg_d, true);
        write_json_number_field(out, "proxyTavg", proxy_day->tavg_d, true);
        write_json_number_field(out, "difference", target_day->tavg_d - proxy_day->tavg_d, false);
        out << "}";

        needs_comma = true;
    }

    out << "]";
}

void StationProxyEngine::write_daily_comparison_option_json(
    ostringstream& out,
    const StationPairScore& score,
    const StationDataset& target_station,
    const StationDataset& proxy_station,
    int rank,
    int day_limit
) const {
    out << "{";
    out << "\"match\":";
    write_pair_score_json(out, score, rank);
    out << ",\"dailyComparison\":";
    write_daily_comparison_json(
        out,
        target_station,
        proxy_station,
        day_limit
    );
    out << "}";
}

bool StationProxyEngine::load(
    const string& target_file,
    const string& hub_file
) {
    target_input_file = target_file;
    hub_input_file = hub_file;
    loaded = false;

    target_stations.clear();
    hub_stations.clear();
    rebuild_station_indexes();

    target_stations = load_app_ready_temperature_station_datasets(target_input_file);
    hub_stations = load_app_ready_temperature_station_datasets(hub_input_file);
    enrich_station_metadata_from_candidates();
    precompute_derived_summaries(target_stations);
    precompute_derived_summaries(hub_stations);
    rebuild_station_indexes();

    loaded = !target_stations.empty() && !hub_stations.empty();

    return loaded;
}

bool StationProxyEngine::is_loaded() const {
    return loaded;
}

int StationProxyEngine::target_station_count() const {
    return static_cast<int>(target_stations.size());
}

int StationProxyEngine::hub_station_count() const {
    return static_cast<int>(hub_stations.size());
}

string StationProxyEngine::analyze_location_json(
    double latitude,
    double longitude
) const {
    ostringstream out;

    if (!loaded) {
        out << "{";
        write_json_string_field(out, "status", "error", true);
        write_json_string_field(out, "message", "StationProxyEngine has not loaded target and hub station data", false);
        out << "}";
        return out.str();
    }

    if (target_stations.empty()) {
        out << "{";
        write_json_string_field(out, "status", "error", true);
        write_json_string_field(out, "message", "No target stations loaded", true);
        write_json_string_field(out, "targetInputFile", target_input_file, false);
        out << "}";
        return out.str();
    }

    if (hub_stations.empty()) {
        out << "{";
        write_json_string_field(out, "status", "error", true);
        write_json_string_field(out, "message", "No hub stations loaded", true);
        write_json_string_field(out, "hubInputFile", hub_input_file, false);
        out << "}";
        return out.str();
    }

    const StationDataset* nearest_station = find_nearest_station(
        latitude,
        longitude,
        all_station_pointers
    );

    if (nearest_station == nullptr) {
        out << "{";
        write_json_string_field(out, "status", "error", true);
        write_json_string_field(out, "message", "No nearest station found", false);
        out << "}";
        return out.str();
    }

    bool nearest_station_is_hub = is_hub_station_id(nearest_station->metadata.stationID);
    string match_mode = nearest_station_is_hub ? "hub_to_hub" : "target_to_hub";

    vector<StationPairScore> ranked_matches = find_ranked_proxy_matches_local(
        *nearest_station,
        hub_stations
    );
    vector<StationPairScore> top_matches = ranked_matches;

    if (top_matches.size() > static_cast<size_t>(top_match_limit)) {
        top_matches.resize(top_match_limit);
    }

    for (StationPairScore& score : top_matches) {
        for (const StationDataset& proxy_station : hub_stations) {
            if (proxy_station.metadata.stationID == score.stationID_b) {
                add_monthly_metrics_to_score(
                    score,
                    *nearest_station,
                    proxy_station
                );
                break;
            }
        }
    }

    const StationDataset* best_proxy = nullptr;
    StationPairScore low_correlation_score;
    const StationDataset* low_correlation_proxy = nullptr;
    vector<pair<StationPairScore, const StationDataset*>> high_correlation_options;
    vector<pair<StationPairScore, const StationDataset*>> low_correlation_options;

    if (!top_matches.empty()) {
        best_proxy = find_station_by_id(top_matches[0].stationID_b);
    }

    for (const StationPairScore& score : top_matches) {
        const StationDataset* proxy_station = find_station_by_id(score.stationID_b);
        if (proxy_station != nullptr) {
            high_correlation_options.push_back({
                score,
                proxy_station
            });
        }
    }

    if (!ranked_matches.empty()) {
        low_correlation_score = *min_element(
            ranked_matches.begin(),
            ranked_matches.end(),
            [](const StationPairScore& a, const StationPairScore& b) {
                return a.daily_correlation < b.daily_correlation;
            }
        );

        low_correlation_proxy = find_station_by_id(low_correlation_score.stationID_b);

        vector<StationPairScore> low_ranked_matches = ranked_matches;
        sort(
            low_ranked_matches.begin(),
            low_ranked_matches.end(),
            [](const StationPairScore& a, const StationPairScore& b) {
                return a.daily_correlation < b.daily_correlation;
            }
        );

        for (const StationPairScore& score : low_ranked_matches) {
            if (low_correlation_options.size() >= 5) {
                break;
            }

            const StationDataset* proxy_station = find_station_by_id(score.stationID_b);
            if (proxy_station != nullptr) {
                low_correlation_options.push_back({
                    score,
                    proxy_station
                });
            }
        }
    }

    out << "{";
    write_json_string_field(out, "status", "ok", true);
    write_json_string_field(out, "message", "Location analysis complete", true);
    write_json_string_field(out, "targetInputFile", target_input_file, true);
    write_json_string_field(out, "hubInputFile", hub_input_file, true);
    write_json_string_field(out, "matchMode", match_mode, true);
    write_json_string_field(
        out,
        "matchDescription",
        nearest_station_is_hub
            ? "Nearest station is a hub; matching against the five most similar other hubs"
            : "Nearest station is a target; matching against proxy hub stations",
        true
    );
    write_json_size_field(out, "targetStationCount", target_stations.size(), true);
    write_json_size_field(out, "hubStationCount", hub_stations.size(), true);

    out << "\"selectedLocation\":{";
    write_json_number_field(out, "latitude", latitude, true);
    write_json_number_field(out, "longitude", longitude, false);
    out << "},";

    out << "\"nearestStation\":";
    write_station_json(out, *nearest_station);
    out << ",";

    out << "\"bestProxyStation\":";
    if (top_matches.empty()) {
        out << "null";
    } else {
        write_pair_score_json(out, top_matches[0], 1);
    }
    out << ",";

    out << "\"topProxyMatches\":[";
    for (int i = 0; i < static_cast<int>(top_matches.size()); i++) {
        if (i > 0) {
            out << ",";
        }

        write_pair_score_json(out, top_matches[i], i + 1);
    }
    out << "]";

    out << ",\"bestProxyMonthlyComparison\":";
    if (best_proxy != nullptr) {
        write_monthly_comparison_json(
            out,
            *nearest_station,
            *best_proxy,
            12
        );
    } else {
        out << "[]";
    }

    out << ",\"bestProxyDailyComparison\":";
    if (best_proxy != nullptr) {
        write_daily_comparison_json(
            out,
            *nearest_station,
            *best_proxy,
            365
        );
    } else {
        out << "[]";
    }

    out << ",\"lowCorrelationExample\":";
    if (low_correlation_proxy != nullptr) {
        out << "{";
        out << "\"match\":";
        write_pair_score_json(out, low_correlation_score, 0);
        out << ",\"dailyComparison\":";
        write_daily_comparison_json(
            out,
            *nearest_station,
            *low_correlation_proxy,
            365
        );
        out << "}";
    } else {
        out << "null";
    }

    out << ",\"highCorrelationComparisonOptions\":[";
    for (int i = 0; i < static_cast<int>(high_correlation_options.size()); i++) {
        if (i > 0) {
            out << ",";
        }

        write_daily_comparison_option_json(
            out,
            high_correlation_options[i].first,
            *nearest_station,
            *high_correlation_options[i].second,
            i + 1,
            365
        );
    }
    out << "]";

    out << ",\"lowCorrelationComparisonOptions\":[";
    for (int i = 0; i < static_cast<int>(low_correlation_options.size()); i++) {
        if (i > 0) {
            out << ",";
        }

        write_daily_comparison_option_json(
            out,
            low_correlation_options[i].first,
            *nearest_station,
            *low_correlation_options[i].second,
            i + 1,
            365
        );
    }
    out << "]";

    out << "}";

    return out.str();
}
