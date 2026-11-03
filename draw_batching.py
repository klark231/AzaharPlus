#!/usr/bin/env python3
"""Adds toggleable Vulkan draw batching to AzaharPlus.

Run from the repo root:   python3 draw_batching.py
Safe to run twice (it detects it was already applied). Nothing is written unless
every edit finds its anchor, so a failed run leaves your tree untouched.

How it stays correct (this is what the old fork got wrong):
  * Accelerated draws are not recorded right away. Their vertex/index data is staged on
    the CPU and kept in one pending batch.
  * The scheduler calls back into the rasterizer BEFORE it records any other command
    (pipeline/descriptor/uniform binds, render pass changes, texture uploads, submits...).
    The callback flushes the pending batch first, so batched draws always run with exactly
    the state they were issued with, and command order never changes.
  * Binding the pipeline/descriptors is skipped when nothing changed, and identical
    texture descriptor sets are reused, so consecutive draws with the same state record
    nothing in between and can be merged into a single draw call.
  * Only plain triangle lists (count % 3 == 0) with identical fixed attributes merge.
    Indexed draws are rebased into one u16 index buffer.
Toggle: Settings > Graphics > "Draw Batching" (Android), or `vk_draw_batching = 1`
under [Renderer] in the ini. Takes effect on the next game start. Default: off.
"""
import os
import sys

ROOT = "."
files = {}


def path(p):
    return os.path.join(ROOT, p)


def load(p):
    if p not in files:
        with open(path(p), encoding="utf-8", newline="") as f:
            files[p] = f.read()
    return files[p]


def edit(p, old, new, count=1):
    s = load(p)
    n = s.count(old)
    if n != count:
        sys.exit(f"ERROR: {p}: anchor found {n}x (expected {count}):\n{old[:120]!r}")
    files[p] = s.replace(old, new)


def insert_before_last(p, marker, text):
    s = load(p)
    i = s.rfind(marker)
    if i < 0:
        sys.exit(f"ERROR: {p}: marker not found: {marker!r}")
    files[p] = s[:i] + text + s[i:]


SETTINGS_H = "src/common/settings.h"
if "vk_draw_batching" in load(SETTINGS_H):
    print("already patched")
    sys.exit(0)

VK = "src/video_core/renderer_vulkan/"

# ---------------------------------------------------------------- settings plumbing
edit(SETTINGS_H,
     "    SwitchableSetting<s32, true> vk_lighter_surfaces{0, 0, 2, Keys::vk_lighter_surfaces};\n",
     "    SwitchableSetting<s32, true> vk_lighter_surfaces{0, 0, 2, Keys::vk_lighter_surfaces};\n"
     "    /// Vulkan: merge consecutive draws with identical state (experimental)\n"
     "    SwitchableSetting<bool> vk_draw_batching{false, Keys::vk_draw_batching};\n")
edit("src/common/settings.cpp",
     '    log_setting("Renderer_LighterSurfaces", values.vk_lighter_surfaces.GetValue());\n',
     '    log_setting("Renderer_LighterSurfaces", values.vk_lighter_surfaces.GetValue());\n'
     '    log_setting("Renderer_DrawBatching", values.vk_draw_batching.GetValue());\n')
edit("src/common/settings.cpp",
     "    values.vk_lighter_surfaces.SetGlobal(true);\n",
     "    values.vk_lighter_surfaces.SetGlobal(true);\n"
     "    values.vk_draw_batching.SetGlobal(true);\n")
edit("CMakeModules/GenerateSettingKeys.cmake",
     '    "vk_lighter_surfaces"\n',
     '    "vk_lighter_surfaces"\n    "vk_draw_batching"\n')
edit("src/android/app/src/main/jni/config.cpp",
     '    ReadSetting("Renderer", Settings::values.vk_lighter_surfaces);\n',
     '    ReadSetting("Renderer", Settings::values.vk_lighter_surfaces);\n'
     '    ReadSetting("Renderer", Settings::values.vk_draw_batching);\n')
edit("src/android/app/src/main/jni/default_ini.h",
     r''')") DECLARE_KEY(vk_lighter_surfaces) BOOST_HANA_STRING(R"(
''',
     r''')") DECLARE_KEY(vk_lighter_surfaces) BOOST_HANA_STRING(R"(

# Vulkan only. Experimental. Merges consecutive draw calls that use identical state into one.
# Takes effect the next time a game starts.
# 0 (default): Off, 1: On
)") DECLARE_KEY(vk_draw_batching) BOOST_HANA_STRING(R"(
''')
KT = "src/android/app/src/main/java/org/citra/citra_emu/features/settings/"
edit(KT + "SettingKeys.kt",
     "    external fun vk_lighter_surfaces(): String\n",
     "    external fun vk_lighter_surfaces(): String\n    external fun vk_draw_batching(): String\n")
edit(KT + "model/BooleanSetting.kt",
     "    ASYNC_SHADERS(SettingKeys.async_shader_compilation(), Settings.SECTION_RENDERER, false),\n",
     "    ASYNC_SHADERS(SettingKeys.async_shader_compilation(), Settings.SECTION_RENDERER, false),\n"
     "    VK_DRAW_BATCHING(SettingKeys.vk_draw_batching(), Settings.SECTION_RENDERER, false),\n")
edit(KT + "ui/SettingsFragmentPresenter.kt",
     """            add(
                SwitchSetting(
                    BooleanSetting.ASYNC_SHADERS,
""",
     """            add(
                SwitchSetting(
                    BooleanSetting.VK_DRAW_BATCHING,
                    R.string.draw_batching,
                    R.string.draw_batching_description,
                    BooleanSetting.VK_DRAW_BATCHING.key,
                    BooleanSetting.VK_DRAW_BATCHING.defaultValue
                )
            )
            add(
                SwitchSetting(
                    BooleanSetting.ASYNC_SHADERS,
""")
edit("src/android/app/src/main/res/values/strings.xml",
     '    <string name="lighter_surfaces_with_shadows">Lighter, with shadows</string>\n',
     '    <string name="lighter_surfaces_with_shadows">Lighter, with shadows</string>\n'
     '    <string name="draw_batching">Draw Batching</string>\n'
     '    <string name="draw_batching_description">Experimental (Vulkan). Merges consecutive draw '
     'calls that use identical state into one, reducing CPU and driver overhead. If you see missing '
     'or distorted geometry, turn this off. Takes effect the next time a game starts.</string>\n')

# ---------------------------------------------------------------- scheduler hook
edit(VK + "vk_scheduler.h",
     """    template <typename T>
    void Record(T&& command) {
        if (chunk->Record(command)) {""",
     """    template <typename T>
    void Record(T&& command) {
        if (pre_record) {
            pre_record();
        }
        if (chunk->Record(command)) {""")
edit(VK + "vk_scheduler.h",
     """    void RegisterOnDispatch(std::function<void()>&& func) {
        on_dispatch = std::move(func);
    }
""",
     """    void RegisterOnDispatch(std::function<void()>&& func) {
        on_dispatch = std::move(func);
    }

    /// Registers a callback that runs before any command is recorded or work is submitted.
    void SetPreRecordCallback(std::function<void()>&& func) {
        pre_record = std::move(func);
    }
""")
edit(VK + "vk_scheduler.h",
     "    std::function<void()> on_dispatch;\n",
     "    std::function<void()> on_dispatch;\n    std::function<void()> pre_record;\n")
edit(VK + "vk_scheduler.cpp",
     "void Scheduler::Flush(vk::Semaphore signal, vk::Semaphore wait) {\n",
     "void Scheduler::Flush(vk::Semaphore signal, vk::Semaphore wait) {\n"
     "    if (pre_record) {\n        pre_record();\n    }\n")
edit(VK + "vk_scheduler.cpp",
     "void Scheduler::Finish(vk::Semaphore signal, vk::Semaphore wait) {\n",
     "void Scheduler::Finish(vk::Semaphore signal, vk::Semaphore wait) {\n"
     "    if (pre_record) {\n        pre_record();\n    }\n")

# ---------------------------------------------------------------- descriptor update queue
edit(VK + "vk_descriptor_update_queue.h",
     "    void Flush();\n",
     """    void Flush();

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
""")
edit(VK + "vk_descriptor_update_queue.h",
     "    u32 descriptor_write_end = 0;\n",
     "    u32 descriptor_write_end = 0;\n    u32 flush_count = 0;\n")
edit(VK + "vk_descriptor_update_queue.cpp",
     '#include "video_core/renderer_vulkan/vk_descriptor_update_queue.h"\n',
     '#include <cstdint>\n#include <type_traits>\n'
     '#include "video_core/renderer_vulkan/vk_descriptor_update_queue.h"\n')
edit(VK + "vk_descriptor_update_queue.cpp",
     """    if (descriptor_write_end == 0) {
        return;
    }
    device.updateDescriptorSets""",
     """    if (descriptor_write_end == 0) {
        return;
    }
    ++flush_count;
    device.updateDescriptorSets""")
insert_before_last(VK + "vk_descriptor_update_queue.cpp", "} // namespace Vulkan", r'''namespace {

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

''')

# ---------------------------------------------------------------- pipeline cache
edit(VK + "vk_pipeline_cache.h",
     """    /// Sets the dynamic offset for the uniform buffer at binding
    void UpdateRange(u8 binding, u32 offset) {
        offsets[binding] = offset;
    }
""",
     """    /// Sets the dynamic offset for the uniform buffer at binding
    void UpdateRange(u8 binding, u32 offset) {
        offsets[binding] = offset;
    }

    /// Returns the descriptor set currently selected for the heap type
    [[nodiscard]] vk::DescriptorSet GetBoundSet(DescriptorHeapType type) const {
        return bound_descriptor_sets[static_cast<u32>(type)];
    }

    /// Selects an already written descriptor set instead of the one that was just acquired
    void SetBoundSet(DescriptorHeapType type, vk::DescriptorSet set) {
        bound_descriptor_sets[static_cast<u32>(type)] = set;
    }

    /// When enabled, BindPipeline records nothing if pipeline, dynamic state and descriptors
    /// are identical to the previous call.
    void SetSkipRedundantBinds(bool enable) {
        skip_redundant_binds = enable;
    }
""")
edit(VK + "vk_pipeline_cache.h",
     "    std::array<u32, NumDynamicOffsets> offsets{};\n",
     """    std::array<u32, NumDynamicOffsets> offsets{};
    std::array<vk::DescriptorSet, NumRasterizerSets> last_recorded_sets{};
    std::array<u32, NumDynamicOffsets> last_recorded_offsets{};
    bool last_recorded_valid{};
    bool skip_redundant_binds{};
""")
edit(VK + "vk_pipeline_cache.cpp",
     "bool PipelineCache::BindPipeline(PipelineInfo& info, bool wait_built) {\n",
     r'''namespace {

/// Mirrors every dynamic state comparison done by the command recorded in BindPipeline.
bool DynamicStateUnchanged(const PipelineInfo& a, const PipelineInfo& b) {
    const auto& da = a.dynamic_info;
    const auto& db = b.dynamic_info;
    if (da.viewport != db.viewport || da.scissor != db.scissor ||
        da.stencil_compare_mask != db.stencil_compare_mask ||
        da.stencil_write_mask != db.stencil_write_mask ||
        da.stencil_reference != db.stencil_reference || da.blend_color != db.blend_color) {
        return false;
    }
    const auto& ra = a.state.rasterization;
    const auto& rb = b.state.rasterization;
    if (ra.cull_mode != rb.cull_mode || ra.flip_viewport != rb.flip_viewport ||
        ra.topology != rb.topology) {
        return false;
    }
    const auto& sa = a.state.depth_stencil;
    const auto& sb = b.state.depth_stencil;
    if (sa.depth_compare_op != sb.depth_compare_op || sa.depth_test_enable != sb.depth_test_enable ||
        sa.depth_write_enable != sb.depth_write_enable ||
        sa.stencil_test_enable != sb.stencil_test_enable ||
        sa.stencil_fail_op != sb.stencil_fail_op || sa.stencil_pass_op != sb.stencil_pass_op ||
        sa.stencil_depth_fail_op != sb.stencil_depth_fail_op ||
        sa.stencil_compare_op != sb.stencil_compare_op) {
        return false;
    }
    return true;
}

} // Anonymous namespace

bool PipelineCache::BindPipeline(PipelineInfo& info, bool wait_built) {
''')
edit(VK + "vk_pipeline_cache.cpp",
     """    const bool pipeline_dirty = (current_pipeline != pipeline) || is_dirty;
    scheduler.Record(""",
     """    const bool pipeline_dirty = (current_pipeline != pipeline) || is_dirty;

    // Nothing would change on the GPU: skip recording so consecutive draws can be batched.
    if (skip_redundant_binds && !pipeline_dirty && last_recorded_valid &&
        !scheduler.IsStateDirty(StateFlags::DescriptorSets) &&
        bound_descriptor_sets == last_recorded_sets && offsets == last_recorded_offsets &&
        DynamicStateUnchanged(current_info, info)) {
        current_info = info;
        return true;
    }

    scheduler.Record(""")
edit(VK + "vk_pipeline_cache.cpp",
     """                                  descriptor_sets, offsets);
    });

    current_info = info;""",
     """                                  descriptor_sets, offsets);
    });

    last_recorded_sets = bound_descriptor_sets;
    last_recorded_offsets = offsets;
    last_recorded_valid = true;
    current_info = info;""")

# ---------------------------------------------------------------- rasterizer header
edit(VK + "vk_rasterizer.h",
     "    PipelineInfo pipeline_info{};\n",
     r'''    PipelineInfo pipeline_info{};

    /// Data of the accelerated draw that is currently being processed
    struct StagedDraw {
        std::vector<u8> vertex_data;
        std::array<u32, 16> binding_start{};
        std::array<u32, 16> binding_bytes{};
        std::array<u8, 512> fixed{};
        u32 fixed_size = 0;
        std::vector<u16> indices;
    };

    /// Consecutive draws with identical GPU state, waiting to be recorded as one draw call
    struct DrawBatch {
        bool open = false;
        bool indexed = false;
        u32 binding_count = 0; // loader bindings + the fixed attribute binding
        std::array<std::vector<u8>, 16> binding_data;
        std::array<u8, 512> fixed{};
        u32 fixed_size = 0;
        std::vector<u16> indices;
        u32 vertex_total = 0;
        u32 draw_count = 0;
        u32 byte_total = 0;
    };

    void CommitStagedDraw(bool is_indexed);
    void FlushDrawBatch();
    void ReuseDescriptorSets(const DescriptorUpdateQueue::Mark& mark);

    bool batching_enabled = false;
    bool flushing_batch = false;
    StagedDraw staged;
    DrawBatch batch;

    bool have_last_descriptors = false;
    u64 last_descriptor_hash = 0;
    u64 last_descriptor_tick = 0;
    vk::DescriptorSet last_texture_set{};
    vk::DescriptorSet last_utility_set{};
''')

# ---------------------------------------------------------------- rasterizer source
RAST = VK + "vk_rasterizer.cpp"
edit(RAST,
     "constexpr u64 STREAM_BUFFER_SIZE = 64_MiB;\n",
     "constexpr u64 STREAM_BUFFER_SIZE = 64_MiB;\n"
     "constexpr u32 MAX_BATCH_BYTES = 4_MiB;\n"
     "constexpr u32 MAX_BATCH_INDEXED_VERTICES = 65535;\n")
edit(RAST,
     "    vertex_buffers.fill(stream_buffer.Handle());\n",
     """    vertex_buffers.fill(stream_buffer.Handle());

    batching_enabled = Settings::values.vk_draw_batching.GetValue();
    pipeline_cache.SetSkipRedundantBinds(batching_enabled);
    if (batching_enabled) {
        LOG_INFO(Render_Vulkan, "Draw batching enabled");
        scheduler.SetPreRecordCallback([this] {
            if (batch.open && !flushing_batch) {
                FlushDrawBatch();
            }
        });
    }
""")
edit(RAST,
     "RasterizerVulkan::~RasterizerVulkan() = default;\n",
     "RasterizerVulkan::~RasterizerVulkan() {\n    scheduler.SetPreRecordCallback({});\n}\n")
edit(RAST,
     "void RasterizerVulkan::TickFrame() {\n    scheduler.WaitWorker();\n",
     "void RasterizerVulkan::TickFrame() {\n    FlushDrawBatch();\n    scheduler.WaitWorker();\n")

# vertex array: stage on the CPU when batching
edit(RAST,
     """    const auto [vs_input_index_min, vs_input_index_max, vs_input_size] = vertex_info;
    auto [array_ptr, array_offset, invalidate] = stream_buffer.Map(vs_input_size, 16);
""",
     """    const auto [vs_input_index_min, vs_input_index_max, vs_input_size] = vertex_info;
    u8* array_ptr;
    u32 array_offset;
    if (batching_enabled) {
        staged.vertex_data.resize(vs_input_size);
        array_ptr = staged.vertex_data.data();
        array_offset = 0;
    } else {
        auto [mapped_ptr, mapped_offset, invalidate] = stream_buffer.Map(vs_input_size, 16);
        array_ptr = mapped_ptr;
        array_offset = mapped_offset;
    }
""")
edit(RAST,
     """        // Keep track of the binding offsets so we can bind the vertex buffer later
        binding_offsets[layout.binding_count++] = static_cast<u32>(array_offset + buffer_offset);
        buffer_offset += Common::AlignUp(aligned_stride * vertex_num, 4);
    }

    stream_buffer.Commit(buffer_offset);
""",
     """        // Keep track of the binding offsets so we can bind the vertex buffer later
        staged.binding_start[layout.binding_count] = buffer_offset;
        staged.binding_bytes[layout.binding_count] = aligned_stride * vertex_num;
        binding_offsets[layout.binding_count++] = static_cast<u32>(array_offset + buffer_offset);
        buffer_offset += Common::AlignUp(aligned_stride * vertex_num, 4);
    }

    if (!batching_enabled) {
        stream_buffer.Commit(buffer_offset);
    }
""")
edit(RAST,
     """    auto [fixed_ptr, fixed_offset, _] = stream_buffer.Map(16 * sizeof(Common::Vec4f), 0);
    binding_offsets[layout.binding_count] = static_cast<u32>(fixed_offset);
""",
     """    u8* fixed_ptr;
    u32 fixed_offset;
    if (batching_enabled) {
        staged.fixed.fill(0);
        fixed_ptr = staged.fixed.data();
        fixed_offset = 0;
    } else {
        auto [mapped_ptr, mapped_offset, invalidate] =
            stream_buffer.Map(16 * sizeof(Common::Vec4f), 0);
        fixed_ptr = mapped_ptr;
        fixed_offset = mapped_offset;
    }
    binding_offsets[layout.binding_count] = static_cast<u32>(fixed_offset);
""")
edit(RAST,
     """    binding.byte_count.Assign(offset);

    stream_buffer.Commit(offset);
}""",
     """    binding.byte_count.Assign(offset);

    if (batching_enabled) {
        staged.fixed_size = offset;
    } else {
        stream_buffer.Commit(offset);
    }
}""")
edit(RAST,
     """    const u8* index_data =
        memory.GetPhysicalPointer(regs.pipeline.vertex_attributes.GetPhysicalBaseAddress() +
                                  regs.pipeline.index_array.offset);

    auto [index_ptr, index_offset, _] = stream_buffer.Map(index_buffer_size, 2);
""",
     """    const u8* index_data =
        memory.GetPhysicalPointer(regs.pipeline.vertex_attributes.GetPhysicalBaseAddress() +
                                  regs.pipeline.index_array.offset);

    if (batching_enabled) {
        // Indices are widened to u16 and rebased when the draw joins a batch.
        const u32 count = regs.pipeline.num_vertices;
        staged.indices.resize(count);
        if (index_u8) {
            for (u32 i = 0; i < count; i++) {
                staged.indices[i] = index_data[i];
            }
        } else {
            std::memcpy(staged.indices.data(), index_data, count * sizeof(u16));
        }
        return;
    }

    auto [index_ptr, index_offset, _] = stream_buffer.Map(index_buffer_size, 2);
""")

# commit instead of recording the draw
edit(RAST,
     """    if (!pipeline_cache.BindPipeline(pipeline_info, wait_built)) {
        return true;
    }

    const DrawParams params = {""",
     """    if (!pipeline_cache.BindPipeline(pipeline_info, wait_built)) {
        return true;
    }

    if (batching_enabled) {
        CommitStagedDraw(is_indexed);
        return true;
    }

    const DrawParams params = {""")

# new functions
edit(RAST,
     "void RasterizerVulkan::SetupIndexArray() {\n",
     r'''void RasterizerVulkan::CommitStagedDraw(bool is_indexed) {
    const u32 binding_count = pipeline_info.state.vertex_layout.binding_count;
    if (binding_count == 0) {
        return;
    }
    const u32 loader_bindings = binding_count - 1; // the last binding holds the fixed attributes
    const u32 draw_count = regs.pipeline.num_vertices;
    const u32 index_min = vertex_info.vs_input_index_min;
    const u32 vertex_num = vertex_info.vs_input_index_max - index_min + 1;

    // Only plain triangle lists can be concatenated without changing what gets drawn.
    const bool mergeable = regs.pipeline.triangle_topology == TriangleTopology::List &&
                           draw_count % 3 == 0 && (is_indexed || vertex_num == draw_count);

    if (batch.open) {
        // If the batch is still open, nothing was recorded since it was started, so the GPU
        // state is identical. The remaining differences only exist on the CPU side.
        const bool compatible =
            mergeable && batch.indexed == is_indexed && batch.binding_count == binding_count &&
            batch.fixed_size == staged.fixed_size &&
            std::memcmp(batch.fixed.data(), staged.fixed.data(), staged.fixed_size) == 0 &&
            batch.byte_total + staged.vertex_data.size() <= MAX_BATCH_BYTES &&
            (!is_indexed || batch.vertex_total + vertex_num <= MAX_BATCH_INDEXED_VERTICES);
        if (!compatible) {
            FlushDrawBatch();
        }
    }

    if (!batch.open) {
        batch.open = true;
        batch.indexed = is_indexed;
        batch.binding_count = binding_count;
        for (auto& data : batch.binding_data) {
            data.clear();
        }
        batch.indices.clear();
        batch.vertex_total = 0;
        batch.draw_count = 0;
        batch.byte_total = 0;
        batch.fixed = staged.fixed;
        batch.fixed_size = staged.fixed_size;
    }

    for (u32 k = 0; k < loader_bindings; k++) {
        const u8* src = staged.vertex_data.data() + staged.binding_start[k];
        batch.binding_data[k].insert(batch.binding_data[k].end(), src,
                                     src + staged.binding_bytes[k]);
        batch.byte_total += staged.binding_bytes[k];
    }

    if (is_indexed) {
        const u32 base = batch.vertex_total;
        const std::size_t old_size = batch.indices.size();
        batch.indices.resize(old_size + draw_count);
        for (u32 i = 0; i < draw_count; i++) {
            const u32 index = staged.indices[i];
            u32 relative = index >= index_min ? index - index_min : 0;
            if (relative >= vertex_num) {
                relative = vertex_num - 1;
            }
            batch.indices[old_size + i] = static_cast<u16>(base + relative);
        }
        batch.byte_total += draw_count * sizeof(u16);
    }

    batch.vertex_total += vertex_num;
    batch.draw_count += draw_count;

    if (!mergeable || batch.byte_total >= MAX_BATCH_BYTES) {
        FlushDrawBatch();
    }
}

void RasterizerVulkan::FlushDrawBatch() {
    if (!batch.open || flushing_batch) {
        return;
    }
    flushing_batch = true;
    batch.open = false;

    const u32 loader_bindings = batch.binding_count - 1;

    // Lay the merged data out in one stream buffer allocation.
    std::array<u32, 16> region{};
    u32 size = 0;
    for (u32 k = 0; k < loader_bindings; k++) {
        region[k] = size;
        size = Common::AlignUp(size + static_cast<u32>(batch.binding_data[k].size()), 16);
    }
    const u32 fixed_region = size;
    size = Common::AlignUp(size + std::max<u32>(batch.fixed_size, 16), 16);
    const u32 index_region = size;
    if (batch.indexed) {
        size += static_cast<u32>(batch.indices.size() * sizeof(u16));
    }
    size = std::max<u32>(size, 16);

    auto [ptr, base, invalidate] = stream_buffer.Map(size, 16);
    for (u32 k = 0; k < loader_bindings; k++) {
        if (!batch.binding_data[k].empty()) {
            std::memcpy(ptr + region[k], batch.binding_data[k].data(),
                        batch.binding_data[k].size());
        }
    }
    std::memcpy(ptr + fixed_region, batch.fixed.data(), batch.fixed_size);
    if (batch.indexed && !batch.indices.empty()) {
        std::memcpy(ptr + index_region, batch.indices.data(),
                    batch.indices.size() * sizeof(u16));
    }
    stream_buffer.Commit(size);

    std::array<vk::DeviceSize, 16> offsets{};
    for (u32 k = 0; k < loader_bindings; k++) {
        offsets[k] = static_cast<vk::DeviceSize>(base + region[k]);
    }
    offsets[loader_bindings] = static_cast<vk::DeviceSize>(base + fixed_region);

    scheduler.Record([this, offsets, binding_count = batch.binding_count, indexed = batch.indexed,
                      index_offset = static_cast<vk::DeviceSize>(base + index_region),
                      count = batch.draw_count](vk::CommandBuffer cmdbuf) {
        cmdbuf.bindVertexBuffers(0, binding_count, vertex_buffers.data(), offsets.data());
        if (indexed) {
            cmdbuf.bindIndexBuffer(stream_buffer.Handle(), index_offset, vk::IndexType::eUint16);
            cmdbuf.drawIndexed(count, 1, 0, 0, 0);
        } else {
            cmdbuf.draw(count, 1, 0, 0);
        }
    });

    flushing_batch = false;
}

void RasterizerVulkan::ReuseDescriptorSets(const DescriptorUpdateQueue::Mark& mark) {
    u64 hash{};
    if (!update_queue.HashSince(mark, hash)) {
        have_last_descriptors = false;
        return;
    }

    // Sets are only safe to reuse inside the command buffer they were acquired in.
    const u64 tick = scheduler.CurrentTick();
    if (have_last_descriptors && last_descriptor_tick == tick && last_descriptor_hash == hash &&
        update_queue.DiscardSince(mark)) {
        pipeline_cache.SetBoundSet(DescriptorHeapType::Texture, last_texture_set);
        pipeline_cache.SetBoundSet(DescriptorHeapType::Utility, last_utility_set);
        return;
    }

    have_last_descriptors = true;
    last_descriptor_hash = hash;
    last_descriptor_tick = tick;
    last_texture_set = pipeline_cache.GetBoundSet(DescriptorHeapType::Texture);
    last_utility_set = pipeline_cache.GetBoundSet(DescriptorHeapType::Utility);
}

void RasterizerVulkan::SetupIndexArray() {
''')

# descriptor reuse in Draw()
edit(RAST,
     """    // Sync and bind the texture surfaces
    SyncTextureUnits(framebuffer);
    SyncUtilityTextures(framebuffer);
""",
     """    // Sync and bind the texture surfaces
    const auto descriptor_mark = update_queue.GetMark();
    SyncTextureUnits(framebuffer);
    SyncUtilityTextures(framebuffer);
    if (batching_enabled && accelerate) {
        ReuseDescriptorSets(descriptor_mark);
    }
""")

# explicit flush points (the scheduler hook already covers everything that records)
edit(RAST,
     "void RasterizerVulkan::DrawTriangles() {\n    if (vertex_batch.empty()) {\n        return;\n    }\n",
     "void RasterizerVulkan::DrawTriangles() {\n    if (vertex_batch.empty()) {\n        return;\n    }\n\n"
     "    FlushDrawBatch();\n")
edit(RAST, "void RasterizerVulkan::FlushAll() {\n",
     "void RasterizerVulkan::FlushAll() {\n    FlushDrawBatch();\n")
edit(RAST, "void RasterizerVulkan::FlushRegion(PAddr addr, u32 size) {\n",
     "void RasterizerVulkan::FlushRegion(PAddr addr, u32 size) {\n    FlushDrawBatch();\n")
edit(RAST, "void RasterizerVulkan::InvalidateRegion(PAddr addr, u32 size) {\n",
     "void RasterizerVulkan::InvalidateRegion(PAddr addr, u32 size) {\n    FlushDrawBatch();\n")
edit(RAST, "void RasterizerVulkan::FlushAndInvalidateRegion(PAddr addr, u32 size) {\n",
     "void RasterizerVulkan::FlushAndInvalidateRegion(PAddr addr, u32 size) {\n    FlushDrawBatch();\n")
edit(RAST, "void RasterizerVulkan::ClearAll(bool flush) {\n",
     "void RasterizerVulkan::ClearAll(bool flush) {\n    FlushDrawBatch();\n")
edit(RAST, "bool RasterizerVulkan::AccelerateDisplayTransfer(const Pica::DisplayTransferConfig& config) {\n",
     "bool RasterizerVulkan::AccelerateDisplayTransfer(const Pica::DisplayTransferConfig& config) {\n"
     "    FlushDrawBatch();\n")
edit(RAST, "bool RasterizerVulkan::AccelerateTextureCopy(const Pica::DisplayTransferConfig& config) {\n",
     "bool RasterizerVulkan::AccelerateTextureCopy(const Pica::DisplayTransferConfig& config) {\n"
     "    FlushDrawBatch();\n")
edit(RAST, "bool RasterizerVulkan::AccelerateFill(const Pica::MemoryFillConfig& config) {\n",
     "bool RasterizerVulkan::AccelerateFill(const Pica::MemoryFillConfig& config) {\n"
     "    FlushDrawBatch();\n")

# ---------------------------------------------------------------- write everything
for p, content in files.items():
    with open(path(p), "w", encoding="utf-8", newline="") as f:
        f.write(content)
print(f"patched {len(files)} files")
