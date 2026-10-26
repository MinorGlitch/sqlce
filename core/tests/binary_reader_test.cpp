#include <array>
#include <cstdint>
#include <limits>
#include <span>

#include "TestSupport.hpp"
#include "sdf/domain/InvalidSdfException.hpp"
#include "sdf/infrastructure/BinaryReader.hpp"

namespace
{

template <typename TReader>
void CheckBounds(TReader read, std::size_t width)
{
    using sdf::domain::InvalidSdfException;
    using sdf::tests::RequireThrows;
    const std::array<std::uint8_t, 32> bytes{};
    const std::span<const std::uint8_t> buffer(bytes);

    (void)read(buffer, 0);
    (void)read(buffer, buffer.size() - width);
    for (std::size_t available = 0; available < width; ++available)
    {
        RequireThrows<InvalidSdfException>([&] { (void)read(buffer.first(available), 0); },
            "short field was accepted");
        RequireThrows<InvalidSdfException>([&] { (void)read(buffer, buffer.size() - available); },
            "field crossing the end was accepted");
    }
    RequireThrows<InvalidSdfException>([&] { (void)read(buffer, buffer.size() + 1); },
        "offset beyond the buffer was accepted");
    RequireThrows<InvalidSdfException>([&] { (void)read(buffer, std::numeric_limits<std::size_t>::max()); },
        "overflowing offset was accepted");
}

void TestBinaryReads()
{
    using namespace sdf::infrastructure;
    using sdf::tests::Require;
    CheckBounds(ReadUInt16LE, 2);
    CheckBounds(ReadUInt32LE, 4);
    CheckBounds(ReadInt32LE, 4);
    CheckBounds(ReadUInt64LE, 8);
    CheckBounds(ReadInt64LE, 8);
    CheckBounds(ReadFloatLE, 4);
    CheckBounds(ReadDoubleLE, 8);
    CheckBounds(ReadBytes16, 16);

    const std::array<std::uint8_t, 17> bytes{
        0, 0x01, 0x23, 0x45, 0x67, 0x89, 0xab, 0xcd, 0xef,
        0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
    Require(ReadUInt16LE(bytes, 1) == 0x2301, "16-bit value changed");
    Require(ReadUInt32LE(bytes, 1) == 0x67452301, "32-bit value changed");
    Require(ReadUInt64LE(bytes, 1) == 0xefcdab8967452301ULL, "64-bit value changed");
    Require(ReadInt32LE(bytes, 9) == -1, "signed 32-bit value changed");
    Require(ReadInt64LE(bytes, 9) == -1, "signed 64-bit value changed");
    const auto copied = ReadBytes16(bytes, 1);
    for (std::size_t i = 0; i < copied.size(); ++i)
    {
        Require(copied[i] == bytes[i + 1], "16-byte value changed");
    }
    const std::array<std::uint8_t, 4> oneFloat{0, 0, 0x80, 0x3f};
    const std::array<std::uint8_t, 8> oneDouble{0, 0, 0, 0, 0, 0, 0xf0, 0x3f};
    Require(ReadFloatLE(oneFloat, 0) == 1.0f, "float value changed");
    Require(ReadDoubleLE(oneDouble, 0) == 1.0, "double value changed");
}

}

int main()
{
    return sdf::tests::Run(TestBinaryReads);
}
