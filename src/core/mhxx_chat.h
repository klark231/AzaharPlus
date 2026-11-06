// Copyright 2026 Citra Emulator Project / Azahar Emulator Project
// Licensed under GPLv2 or any later version
// Refer to the misc/licenses/gplv2.txt file included.

#pragma once

#include <string>
#include "common/common_types.h"

namespace Core {
class System;
}

/// Types text into Monster Hunter XX's built-in keyboard from the host, so the Android keyboard can
/// replace the slow touch keyboard. Written for MHXX JP 1.4.0 (0004000000197100) only.
namespace MhxxChat {

constexpr u64 TitleId = 0x0004000000197100;

/// What fits in the game's result buffer: it ends where an object's vtable pointer starts (+0x18C).
constexpr u32 MaxChars = 28;

/// Everything that touches the game's memory runs on the emulation thread (RunOnEmulationThread).
/// Reading or writing it from the Android UI thread is not safe: the emulator may be mapping pages
/// or flushing GPU caches at the same moment. The UI thread only uses the three functions below.

/// The game's keyboard is on screen and waiting for text (as of the last emulation-thread check).
bool KeyboardOpen();

/// Queues text to be typed into the open keyboard and confirmed, as if OK had been pressed.
/// False if no keyboard is open or the text is blank.
bool InjectText(const std::u16string& text);

/// The loader reports the game's CRO modules. The keyboard is a CRO ("roSwkbd"): the game starts
/// its keyboard request before the module exists, and text typed in that gap leaves the menus stuck.
void OnModuleLoaded(const std::string& name);
void OnModuleUnloaded(const std::string& name);

/// Called from the emulation loop: tracks the keyboard and types any queued text.
void RunOnEmulationThread(Core::System& system);

/// Forgets all state, when the emulation session ends.
void Reset();

} // namespace MhxxChat
