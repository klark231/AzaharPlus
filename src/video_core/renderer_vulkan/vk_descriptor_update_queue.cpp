// Copyright 2024 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#include <cstdint>
#include <type_traits>
#include "video_core/renderer_vulkan/vk_descriptor_update_queue.h"
#include "video_core/renderer_vulkan/vk_instance.h"

namespace Vulkan {

DescriptorUpdateQueue::DescriptorUpdateQueue(const Instance& instance, u32 descriptor_write_max_)
    : device{instance.GetDevice()}, descriptor_write_max{descriptor_write_max_} {
    descriptor_infos = std::make_unique<DescriptorInfoUnion[]>(descriptor_write_max);
    descriptor_writes = std::make_unique<vk::WriteDescriptorSet[]>(descriptor_write_max);
}

void DescriptorUpdateQueue::Flush() {
    if (descriptor_write_end == 0) {
        return;
    }
    ++flush_count;
    device.updateDescriptorSets({std::span(descriptor_writes.get(), descriptor_write_end)}, {});
    descriptor_write_end = 0;
}

void DescriptorUpdateQueue::AddStorageImage(vk::DescriptorSet target, u8 binding,
                                            vk::ImageView image_view,
                                            vk::ImageLayout image_layout) {
    if (descriptor_write_end >= descriptor_write_max) [[unlikely]] {
        Flush();
    }

    auto& image_info = descriptor_infos[descriptor_write_end].image_info;
    image_info.sampler = VK_NULL_HANDLE;
    image_info.imageView = image_view;
    image_info.imageLayout = image_layout;

    descriptor_writes[descriptor_write_end++] = vk::WriteDescriptorSet{
        .dstSet = target,
        .dstBinding = binding,
        .dstArrayElement = 0,
        .descriptorCount = 1,
        .descriptorType = vk::DescriptorType::eStorageImage,
        .pImageInfo = &image_info,
    };
}

void DescriptorUpdateQueue::AddImageSampler(vk::DescriptorSet target, u8 binding, u8 array_index,
                                            vk::ImageView image_view, vk::Sampler sampler,
                                            vk::ImageLayout image_layout) {
    if (descriptor_write_end >= descriptor_write_max) [[unlikely]] {
        Flush();
    }

    auto& image_info = descriptor_infos[descriptor_write_end].image_info;
    image_info.sampler = sampler;
    image_info.imageView = image_view;
    image_info.imageLayout = image_layout;

    descriptor_writes[descriptor_write_end++] = vk::WriteDescriptorSet{
        .dstSet = target,
        .dstBinding = binding,
        .dstArrayElement = array_index,
        .descriptorCount = 1,
        .descriptorType =
            sampler ? vk::DescriptorType::eCombinedImageSampler : vk::DescriptorType::eSampledImage,
        .pImageInfo = &image_info,
    };
}

void DescriptorUpdateQueue::AddBuffer(vk::DescriptorSet target, u8 binding, vk::Buffer buffer,
                                      vk::DeviceSize offset, vk::DeviceSize size,
                                      vk::DescriptorType type) {
    if (descriptor_write_end >= descriptor_write_max) [[unlikely]] {
        Flush();
    }

    auto& buffer_info = descriptor_infos[descriptor_write_end].buffer_info;
    buffer_info.buffer = buffer;
    buffer_info.offset = offset;
    buffer_info.range = size;

    descriptor_writes[descriptor_write_end++] = vk::WriteDescriptorSet{
        .dstSet = target,
        .dstBinding = binding,
        .dstArrayElement = 0,
        .descriptorCount = 1,
        .descriptorType = type,
        .pBufferInfo = &buffer_info,
    };
}

void DescriptorUpdateQueue::AddTexelBuffer(vk::DescriptorSet target, u8 binding,
                                           vk::BufferView buffer_view) {
    if (descriptor_write_end >= descriptor_write_max) [[unlikely]] {
        Flush();
    }

    auto& buffer_info = descriptor_infos[descriptor_write_end].buffer_view;
    buffer_info = buffer_view;
    descriptor_writes[descriptor_write_end++] = vk::WriteDescriptorSet{
        .dstSet = target,
        .dstBinding = binding,
        .dstArrayElement = 0,
        .descriptorCount = 1,
        .descriptorType = vk::DescriptorType::eUniformTexelBuffer,
        .pTexelBufferView = &buffer_info,
    };
}

namespace {

template <typename T>
u64 HandleBits(const T& handle) {
    using Raw = typename T::CType;
    const Raw raw = static_cast<Raw>(handle);
    if constexpr (std::is_pointer_v<Raw>) {
        return static_cast<u64>(reinterpret_cast<std::uintptr_t>(raw));
    } else {
        return static_cast<u64>(raw);
    }
}

} // Anonymous namespace

bool DescriptorUpdateQueue::HashSince(const Mark& mark, u64& hash) const {
    if (mark.flush_count != flush_count || mark.pending >= descriptor_write_end) {
        return false;
    }

    u64 h = 0xcbf29ce484222325ULL;
    const auto mix = [&h](u64 value) {
        h ^= value;
        h *= 0x100000001b3ULL;
    };

    for (u32 i = mark.pending; i < descriptor_write_end; ++i) {
        const vk::WriteDescriptorSet& write = descriptor_writes[i];
        mix(write.dstBinding);
        mix(write.dstArrayElement);
        mix(static_cast<u64>(write.descriptorType));
        switch (write.descriptorType) {
        case vk::DescriptorType::eCombinedImageSampler:
        case vk::DescriptorType::eSampledImage:
        case vk::DescriptorType::eStorageImage: {
            const auto& info = descriptor_infos[i].image_info;
            mix(HandleBits(info.sampler));
            mix(HandleBits(info.imageView));
            mix(static_cast<u64>(info.imageLayout));
            break;
        }
        case vk::DescriptorType::eUniformBuffer:
        case vk::DescriptorType::eUniformBufferDynamic: {
            const auto& info = descriptor_infos[i].buffer_info;
            mix(HandleBits(info.buffer));
            mix(static_cast<u64>(info.offset));
            mix(static_cast<u64>(info.range));
            break;
        }
        case vk::DescriptorType::eUniformTexelBuffer:
            mix(HandleBits(descriptor_infos[i].buffer_view));
            break;
        default:
            return false;
        }
    }
    mix(descriptor_write_end - mark.pending);
    hash = h;
    return true;
}

bool DescriptorUpdateQueue::DiscardSince(const Mark& mark) {
    if (mark.flush_count != flush_count || mark.pending > descriptor_write_end) {
        return false;
    }
    descriptor_write_end = mark.pending;
    return true;
}

} // namespace Vulkan
