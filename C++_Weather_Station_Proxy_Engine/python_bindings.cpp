// Purpose: Exposes StationProxyEngine to Python through pybind11.

#include <pybind11/pybind11.h>

#include "STATION_PROXY_ENGINE.h"

namespace py = pybind11;

PYBIND11_MODULE(_station_proxy_engine, module) {
    module.doc() = "Native Python bindings for the Colorado River Basin station proxy engine.";

    py::class_<StationProxyEngine>(module, "StationProxyEngine")
        .def(py::init<>())
        .def(
            "load",
            [](StationProxyEngine& engine, const std::string& target_file, const std::string& hub_file) {
                py::gil_scoped_release release;
                return engine.load(target_file, hub_file);
            },
            py::arg("target_file"),
            py::arg("hub_file")
        )
        .def("is_loaded", &StationProxyEngine::is_loaded)
        .def("target_station_count", &StationProxyEngine::target_station_count)
        .def("hub_station_count", &StationProxyEngine::hub_station_count)
        .def(
            "analyze_location_json",
            [](const StationProxyEngine& engine, double latitude, double longitude) {
                py::gil_scoped_release release;
                return engine.analyze_location_json(latitude, longitude);
            },
            py::arg("latitude"),
            py::arg("longitude")
        );
}
