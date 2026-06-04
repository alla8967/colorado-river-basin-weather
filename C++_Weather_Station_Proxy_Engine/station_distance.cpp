#include "station_distance.h"
#include <cmath>

using namespace std;

const double pi = 3.14159265358979323846;
const double earth_radius = 6371;

double degrees_to_radians(double degrees) {
    double radians = 0;
    radians = degrees * (pi/180);
    return radians;
}

double calculate_haversine_distance_km(
    double lat_a,
    double lon_a,
    double lat_b,
    double lon_b
) {

    double lat_a_rad = degrees_to_radians(lat_a);
    double lat_b_rad = degrees_to_radians(lat_b);
    double lon_a_rad = degrees_to_radians(lon_a);
    double lon_b_rad = degrees_to_radians(lon_b);
    
    double distance = 0;
    double a = 2 * earth_radius;
    
    double sin_lat = sin((lat_b_rad-lat_a_rad)/2);
    double b = sin_lat * sin_lat;

    double sin_lon = sin((lon_b_rad-lon_a_rad)/2);
    double c = (cos(lat_a_rad)) * (cos(lat_b_rad))*(sin_lon * sin_lon);

    distance = a * asin(sqrt(b+c));

    return distance;

}

double calculate_station_distance_km (
    const StationMetadata& station_a,
    const StationMetadata& station_b
) {
    if (!station_a.has_geo_data || !station_b.has_geo_data) {
        return MISSING;
    }

    double lat_a = station_a.latitude;
    double lat_b = station_b.latitude;
    double lon_a = station_a.longitude;
    double lon_b = station_b.longitude;

    double distance = calculate_haversine_distance_km(lat_a, lon_a, lat_b, lon_b);

    return distance;
}

double calculate_elevation_difference(
    const StationMetadata& station_a,
    const StationMetadata& station_b
) {
    if (!station_a.has_geo_data || !station_b.has_geo_data) {
        return MISSING;
    }

    double elevation_a = station_a.elevation;
    double elevation_b = station_b.elevation;

    double difference = elevation_a - elevation_b;
    double result = abs(difference);

    return result;
}