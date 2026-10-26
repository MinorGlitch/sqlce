#include <array>
#include <cstdint>
#include <span>

#include "TestSupport.hpp"
#include "sdf/domain/InvalidSdfException.hpp"
#include "sdf/domain/PageSize.hpp"
#include "sdf/parsing/PageView.hpp"
#include "sdf/parsing/SdfFormat.hpp"

namespace
{

void WriteUInt32(std::span<std::uint8_t> bytes, std::size_t offset, std::uint32_t value)
{
    for (std::size_t i = 0; i < 4; ++i)
    {
        bytes[offset + i] = static_cast<std::uint8_t>(value >> (8 * i));
    }
}

void TestPageBounds()
{
    using namespace sdf::parsing;
    using sdf::domain::InvalidSdfException;
    using sdf::domain::PageSize;
    using sdf::tests::Require;
    using sdf::tests::RequireThrows;

    std::array<std::uint8_t, PageSize + 1> buffer{};
    for (std::size_t size = 0; size < PageSize; ++size)
    {
        RequireThrows<InvalidSdfException>([&] { PageView page{std::span(buffer).first(size)}; },
            "short page was accepted");
    }
    RequireThrows<InvalidSdfException>([&] { PageView page(buffer); }, "oversized page was accepted");

    auto bytes = std::span(buffer).first(PageSize);
    // Exercise the entire encoded count range, including the subtraction boundary.
    for (std::uint32_t count = 0; count <= SlotCountFieldMask; ++count)
    {
        WriteUInt32(bytes, SlotCountFieldOffset, count);
        PageView page(bytes, RowValidationMode::CompatibleRecovery);
        if (count > SlotArrayBaseIndex + 1)
        {
            RequireThrows<InvalidSdfException>([&] { (void)page.SlotCount(); }, "excessive slot count was accepted");
            RequireThrows<InvalidSdfException>([&] { (void)page.Rows(); }, "row scan accepted excessive slot count");
            RequireThrows<InvalidSdfException>([&] { (void)page.RowsWithContinuation(); },
                "continuation scan accepted excessive slot count");
        }
        else
        {
            Require(page.SlotCount() == count, "bounded slot count changed");
            (void)page.Rows();
            (void)page.RowsWithContinuation();
        }
    }

    buffer.fill(0);
    bytes[PageTypeOffset] = DataPageType;
    WriteUInt32(bytes, SlotCountFieldOffset, 1);
    constexpr std::size_t slotDwordOffset = SlotArrayBaseIndex * SlotEntryLength + SlotEntryDwordOffset;
    WriteUInt32(bytes, slotDwordOffset, 100 | (7 << RecordLengthFieldShift) | (2u << 24));
    bytes[128] = 7;
    bytes[129] = 8;
    bytes[130] = 9;
    PageView page(bytes, RowValidationMode::CompatibleRecovery);
    Require(page.IsDataPage(), "data page type changed");
    const auto rows = page.Rows();
    Require(rows.size() == 1 && rows[0].slotIndex == 0 && rows[0].bytes.size() == 3
        && rows[0].bytes[2] == 9, "valid row changed");
    WriteUInt32(bytes, 100 + RowContinuationDwordOffset, (1234 << ContinuationLogicalPageIdShift) | 5);
    const auto continued = page.RowsWithContinuation();
    Require(continued.size() == 1 && continued[0].isFirstFragment && continued[0].hasContinuation
        && continued[0].continuationLogicalPageId == 1234 && continued[0].continuationSlotIndex == 5,
        "valid continuation changed");

    WriteUInt32(bytes, slotDwordOffset, 0x01ffffff);
    Require(page.Rows().empty() && page.RowsWithContinuation().empty(), "ghost slot was not skipped");
    WriteUInt32(bytes, slotDwordOffset, 4090 | (64 << RecordLengthFieldShift));
    Require(page.Rows().empty() && page.RowsWithContinuation().empty(), "row recovery behavior changed");

    PageView strict(bytes);
    for (std::uint32_t slot : {std::uint32_t(0), std::uint32_t(4 << RecordLengthFieldShift),
        std::uint32_t(4090 | (64 << RecordLengthFieldShift))})
    {
        WriteUInt32(bytes, slotDwordOffset, slot);
        RequireThrows<InvalidSdfException>([&] { (void)strict.Rows(); }, "strict reader skipped invalid row");
        RequireThrows<InvalidSdfException>([&] { (void)strict.RowsWithContinuation(); },
            "strict continuation reader skipped invalid row");
    }
    WriteUInt32(bytes, slotDwordOffset, 0x01ffffff);
    Require(strict.Rows().empty() && strict.RowsWithContinuation().empty(), "strict reader rejected ghost slot");
    WriteUInt32(bytes, slotDwordOffset, 100 | (7 << RecordLengthFieldShift) | (2u << 24));
    Require(strict.Rows().size() == 1 && strict.RowsWithContinuation().size() == 1,
        "strict reader rejected valid row");
}

}

int main()
{
    return sdf::tests::Run(TestPageBounds);
}
