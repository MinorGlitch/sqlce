#ifndef SDF_TESTS_TEST_SUPPORT_HPP
#define SDF_TESTS_TEST_SUPPORT_HPP

#include <cstdlib>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

namespace sdf::tests
{

inline void Require(bool condition, const char* message)
{
    // Unlike assert(), these checks also run in Release builds.
    if (!condition)
    {
        throw std::runtime_error(message);
    }
}

template <typename TException, typename TAction>
void RequireThrows(TAction action, const char* message)
{
    try
    {
        action();
    }
    catch (const TException&)
    {
        return;
    }
    throw std::runtime_error(message);
}

template <typename TAction>
int Run(TAction action)
{
    try
    {
        action();
        return EXIT_SUCCESS;
    }
    catch (const std::exception& error)
    {
        std::cerr << error.what() << '\n';
        return EXIT_FAILURE;
    }
}

}

#endif
