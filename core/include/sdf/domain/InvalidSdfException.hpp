#ifndef SDF_DOMAIN_INVALID_SDF_STRUCTURE_EXCEPTION_HPP
#define SDF_DOMAIN_INVALID_SDF_STRUCTURE_EXCEPTION_HPP

#include <stdexcept>
#include <string>

namespace sdf::domain
{

class InvalidSdfException final : public std::runtime_error
{
public:
    explicit InvalidSdfException(const std::string& detail)
        : std::runtime_error("invalid .sdf structure: " + detail)
    {
    }
};

}

#endif
