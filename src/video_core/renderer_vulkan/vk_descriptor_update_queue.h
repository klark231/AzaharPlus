// Copyright 2024 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <memory>
#include <variant>

#include "common/common_types.h"
#include "video_core/renderer_vulkan/vk_common.h"

namespace Vulkan {

class Instance;

struct DescriptorInfoUnion {
    DescriptorInfoUnion() {}

    union {
        vk::DescriptorImageInfo image_info;
        vk::DescriptorBufferInfo buffer_info;
        vk::BufferView buffer_view;
    };
};

class DescriptorUpdateQueue {
public:
    explicit DescriptorUpdateQueue(const Instance& instance, u32 descriptor_write_max = 2048);
    ~DescriptorUpdateQueue() = default;

    void Flush();

    /// Position in the queue, used to hash or discard the writes queued after it.
    struct Mark {
        u32 pending;
        u32 flush_count;
    };

    [[nodiscard]] Mark GetMark() const noexcept {
        return {descriptor_write_end, flush_count};
    }

    /// Hashes the writes queued since the mark (the target sets are ignored).
    /// Returns false when there is nothing to hash or the queue was flushed since the mark.
    [[nodiscard]] bool HashSince(const Mark& mark, u64& hash) const;

    /// Drops the writes queued since the mark. Returns false if the queue was flushed since.
    bool DiscardSince(const Mark& mark);

    void AddStorageImage(vk::DescriptorSet target, u8 binding, vk::ImageView image_view,
                         vk::ImageLayout image_layout = vk::ImageLayout::eGeneral);

    void AddImageSampler(vk::DescriptorSet target, u8 binding, u8 array_index,
                         vk::ImageView image_view, vk::Sampler sampler,
                         vk::ImageLayout imageLayout = vk::ImageLayout::eGeneral);

    void AddBuffer(vk::DescriptorSet target, u8 binding, vk::Buffer buffer, vk::DeviceSize offset,
                   vk::DeviceSize size = VK_WHOLE_SIZE,
                   vk::DescriptorType type = vk::DescriptorType::eUniformBufferDynamic);

    void AddTexelBuffer(vk::DescriptorSet target, u8 binding, vk::BufferView buffer_view);

private:
    const vk::Device device;
    const u32 descriptor_write_max;
    std::unique_ptr<DescriptorInfoUnion[]> descriptor_infos;
    std::unique_ptr<vk::WriteDescriptorSet[]> descriptor_writes;
    u32 descriptor_write_end = 0;
    u32 flush_count = 0;
};

} // namespace Vulkan
