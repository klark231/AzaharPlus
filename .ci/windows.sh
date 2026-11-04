#!/bin/sh -ex

mkdir -p build
cd build

if [ "$GITHUB_REF_TYPE" == "tag" ]; then
	export EXTRA_CMAKE_FLAGS=(-DENABLE_QT_UPDATE_CHECKER=ON)
fi

# Windows 7 build: Qt 6.8.3, whose DLLs are swapped for the Windows 7 backport after bundling.
# FFmpeg (only used for video dumping) is left out, its prebuilt DLLs need a newer Windows.
WIN7_QT=6.8.3
if [ "$TARGET" = "msvc-win7" ]; then
	EXTRA_CMAKE_FLAGS+=(-DCITRA_QT_VERSION=$WIN7_QT -DENABLE_FFMPEG=OFF)
fi

# libzip (ZipPass dependency) needs zlib. MSVC runners have none, so point CMake at the
# vcpkg one; MSYS2 gets zlib from pacboy instead.
if [ "$TARGET" != "msys2" ]; then
	EXTRA_CMAKE_FLAGS+=(-DZLIB_USE_STATIC_LIBS=ON \
	                    -DZLIB_ROOT="$VCPKG_INSTALLATION_ROOT/installed/x64-windows-static-md")
fi

if [ "${TARGET#msvc}" != "$TARGET" ]; then EXTRA_CMAKE_FLAGS+=(-DZLIB_ROOT=C:/vcpkg/installed/x64-windows); fi

cmake .. -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    -DENABLE_QT_TRANSLATION=ON \
    -DUSE_DISCORD_PRESENCE=ON \
	"${EXTRA_CMAKE_FLAGS[@]}"
ninja
ninja bundle
strip -s bundle/*.exe

if [ "$TARGET" = "msvc-win7" ]; then
	# https://github.com/crystalidea/qt6windows7: the same Qt version, patched to run on
	# Windows 7 SP1 (with the Platform Update, KB2670838), 8 and 8.1. Every Qt DLL and plugin the
	# bundle has is replaced by its patched twin, along with the Visual C++ runtime they need.
	gh release download "v$WIN7_QT" --repo crystalidea/qt6windows7 --pattern '*x64*' --dir win7qt
	7z x -y -owin7qt/files win7qt/*.7z
	(cd win7qt/files && find . -iname '*.dll') | while read -r dll; do
		if [ -f "bundle/$dll" ]; then
			cp -f "win7qt/files/$dll" "bundle/$dll"
			echo "Windows 7 Qt: $dll"
		fi
	done
	for runtime in win7qt/files/msvcp140*.dll win7qt/files/vcruntime140*.dll win7qt/files/concrt140.dll; do
		[ -f "$runtime" ] && cp -f "$runtime" bundle/
	done
	rm -rf win7qt
fi

ccache -s -v

ctest -VV -C Release || echo "::error ::Test error occurred on Windows build"
