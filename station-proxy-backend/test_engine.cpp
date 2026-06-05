// Purpose: Provides a tiny mock engine executable for backend error-path and integration tests.

#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cout << "{";
        std::cout << "\"status\":\"error\",";
        std::cout << "\"message\":\"Missing latitude or longitude\"";
        std::cout << "}";

        return 1;
    }

    std::string latitude = argv[1];
    std::string longitude = argv[2];

    std::cout << "{";
    std::cout << "\"status\":\"ok\",";
    std::cout << "\"message\":\"C++ engine received coordinates\",";
    std::cout << "\"latitude\":" << latitude << ",";
    std::cout << "\"longitude\":" << longitude;
    std::cout << "}";

    return 0;
}
