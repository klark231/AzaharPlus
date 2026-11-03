#!/usr/bin/env python3
"""Adds "Relaxed Precision Shaders" (Vulkan). Run from the repo root, after the earlier scripts:
    python3 relaxed_precision.py

* The SPIR-V fragment generator marks the TEV color/alpha blending math as RelaxedPrecision so
  Mali and Adreno GPUs can use 16-bit math. Texture coordinates, depth, lighting, fog and
  Dot3 bump mapping stay at full precision.
* The option only appears in Settings > Tweaks on Mali (incl. Immortalis / Exynos Mali) and
  Adreno GPUs, and the core also ignores it on any other driver.
* It needs shaders to be rebuilt, so it is greyed out while a game is running. The shader disk
  cache regenerates itself automatically when the option changes.
Safe to run twice. Nothing is written unless every edit finds its anchor.
"""
import os
import re
import sys

files = {}


def load(p):
    if p not in files:
        with open(p, encoding="utf-8", newline="") as f:
            files[p] = f.read()
    return files[p]


def edit(p, old, new, count=1):
    s = load(p)
    n = s.count(old)
    if n != count:
        sys.exit(f"ERROR: {p}: anchor found {n}x (expected {count}):\n{old[:140]!r}")
    files[p] = s.replace(old, new)


def esc(s):
    return s.replace("\\'", "'").replace("'", "\\'")


RES = "src/android/app/src/main/res/"
KT = "src/android/app/src/main/java/org/citra/citra_emu/"
SET = KT + "features/settings/"
GEN = "src/video_core/shader/generator/"

if "vk_relaxed_precision" in load("src/common/settings.h"):
    print("already patched")
    sys.exit(0)

# ---------------------------------------------------------------- setting plumbing
edit("src/common/settings.h",
     "    SwitchableSetting<bool> vk_draw_batching{false, Keys::vk_draw_batching};\n",
     "    SwitchableSetting<bool> vk_draw_batching{false, Keys::vk_draw_batching};\n"
     "    /// Vulkan: let Mali/Adreno GPUs use 16-bit math for shader color blending\n"
     "    SwitchableSetting<bool> vk_relaxed_precision{false, Keys::vk_relaxed_precision};\n")
edit("src/common/settings.cpp",
     '    log_setting("Renderer_DrawBatching", values.vk_draw_batching.GetValue());\n',
     '    log_setting("Renderer_DrawBatching", values.vk_draw_batching.GetValue());\n'
     '    log_setting("Renderer_RelaxedPrecision", values.vk_relaxed_precision.GetValue());\n')
edit("src/common/settings.cpp",
     "    values.vk_draw_batching.SetGlobal(true);\n",
     "    values.vk_draw_batching.SetGlobal(true);\n    values.vk_relaxed_precision.SetGlobal(true);\n")
edit("CMakeModules/GenerateSettingKeys.cmake",
     '    "vk_draw_batching"\n',
     '    "vk_draw_batching"\n    "vk_relaxed_precision"\n')
edit("src/android/app/src/main/jni/config.cpp",
     '    ReadSetting("Renderer", Settings::values.vk_draw_batching);\n',
     '    ReadSetting("Renderer", Settings::values.vk_draw_batching);\n'
     '    ReadSetting("Renderer", Settings::values.vk_relaxed_precision);\n')
edit("src/android/app/src/main/jni/default_ini.h",
     r''')") DECLARE_KEY(vk_draw_batching) BOOST_HANA_STRING(R"(
''',
     r''')") DECLARE_KEY(vk_draw_batching) BOOST_HANA_STRING(R"(

# Vulkan only. Experimental. Lets Mali and Adreno GPUs use 16-bit math for shader color blending.
# 0 (default): Off, 1: On
)") DECLARE_KEY(vk_relaxed_precision) BOOST_HANA_STRING(R"(
''')

# ---------------------------------------------------------------- Android UI
edit(SET + "SettingKeys.kt",
     "    external fun vk_draw_batching(): String\n",
     "    external fun vk_draw_batching(): String\n    external fun vk_relaxed_precision(): String\n")
edit(SET + "model/BooleanSetting.kt",
     "    VK_DRAW_BATCHING(SettingKeys.vk_draw_batching(), Settings.SECTION_RENDERER, false),\n",
     "    VK_DRAW_BATCHING(SettingKeys.vk_draw_batching(), Settings.SECTION_RENDERER, false),\n"
     "    VK_RELAXED_PRECISION(SettingKeys.vk_relaxed_precision(), Settings.SECTION_RENDERER, false),\n")
edit(SET + "model/BooleanSetting.kt",
     "            VK_DRAW_BATCHING,\n            DELAY_START_LLE_MODULES,\n",
     "            VK_DRAW_BATCHING,\n            VK_RELAXED_PRECISION,\n            DELAY_START_LLE_MODULES,\n")
edit(KT + "utils/GraphicsUtil.kt",
     "    fun isUsingAngleForOpenGL(): Boolean {",
     """    /**
     * True on GPUs that run 16-bit shader math faster: ARM Mali (including Immortalis, which is
     * what most Exynos and MediaTek phones use) and Qualcomm Adreno.
     */
    fun supportsRelaxedPrecision(): Boolean {
        val renderer = openGLRendererString
        return renderer.contains("Mali", ignoreCase = true) ||
            renderer.contains("Immortalis", ignoreCase = true) ||
            renderer.contains("Adreno", ignoreCase = true)
    }

    fun isUsingAngleForOpenGL(): Boolean {""")
edit(SET + "ui/SettingsFragmentPresenter.kt",
     """                    IntSetting.VK_LIGHTER_SURFACES.key,
                    IntSetting.VK_LIGHTER_SURFACES.defaultValue
                )
            )
""",
     """                    IntSetting.VK_LIGHTER_SURFACES.key,
                    IntSetting.VK_LIGHTER_SURFACES.defaultValue
                )
            )
            if (GraphicsUtil.supportsRelaxedPrecision()) {
                add(
                    SwitchSetting(
                        BooleanSetting.VK_RELAXED_PRECISION,
                        R.string.relaxed_precision,
                        R.string.relaxed_precision_description,
                        BooleanSetting.VK_RELAXED_PRECISION.key,
                        BooleanSetting.VK_RELAXED_PRECISION.defaultValue
                    )
                )
            }
""")

# ---------------------------------------------------------------- core: profile + generator
edit("src/video_core/shader/generator/profile.h",
     "    u8 is_vulkan{};\n",
     "    u8 is_vulkan{};\n\n    /// Mark TEV blending math as RelaxedPrecision (Mali/Adreno)\n    u8 vk_relaxed_precision{};\n")
edit("src/video_core/renderer_vulkan/vk_pipeline_cache.cpp",
     "        .is_vulkan = true,\n    };\n",
     """        .is_vulkan = true,
        .vk_relaxed_precision =
            Settings::values.vk_relaxed_precision.GetValue() &&
            (instance.GetDriverID() == vk::DriverId::eArmProprietary ||
             instance.GetDriverID() == vk::DriverId::eQualcommProprietary ||
             instance.GetDriverID() == vk::DriverId::eMesaTurnip),
    };
""")
edit(GEN + "spv_fs_shader_gen.h",
     "    [[nodiscard]] Id Byteround(Id variable_id, u32 size = 1);\n",
     "    [[nodiscard]] Id Byteround(Id variable_id, u32 size = 1);\n\n"
     "    /// Marks the result as RelaxedPrecision when the profile asks for it (Mali/Adreno)\n"
     "    Id Relax(Id id);\n")

CPP = GEN + "spv_fs_shader_gen.cpp"
edit(CPP,
     """Id FragmentModule::Byteround(Id variable_id, u32 size) {
    if (size > 1) {
        const Id scaled_vec_id{
            OpVectorTimesScalar(vec_ids.Get(size), variable_id, ConstF32(255.f))};
        const Id rounded_id{OpRound(vec_ids.Get(size), scaled_vec_id)};
        return OpVectorTimesScalar(vec_ids.Get(size), rounded_id, ConstF32(1.f / 255.f));
    } else {
        const Id rounded_id{OpRound(f32_id, OpFMul(f32_id, variable_id, ConstF32(255.f)))};
        return OpFMul(f32_id, rounded_id, ConstF32(1.f / 255.f));
    }
}
""",
     """Id FragmentModule::Relax(Id id) {
    if (profile.vk_relaxed_precision) {
        Decorate(id, spv::Decoration::RelaxedPrecision);
    }
    return id;
}

Id FragmentModule::Byteround(Id variable_id, u32 size) {
    if (size > 1) {
        const Id scaled_vec_id{
            Relax(OpVectorTimesScalar(vec_ids.Get(size), variable_id, ConstF32(255.f)))};
        const Id rounded_id{Relax(OpRound(vec_ids.Get(size), scaled_vec_id))};
        return Relax(OpVectorTimesScalar(vec_ids.Get(size), rounded_id, ConstF32(1.f / 255.f)));
    } else {
        const Id scaled_id{Relax(OpFMul(f32_id, variable_id, ConstF32(255.f)))};
        const Id rounded_id{Relax(OpRound(f32_id, scaled_id))};
        return Relax(OpFMul(f32_id, rounded_id, ConstF32(1.f / 255.f)));
    }
}
""")

# modifiers: only the arithmetic (1 - x) results are marked
s = load(CPP)
s, n1 = re.subn(r"return (OpFSub\(vec_ids\.Get\(3\), one_vec, shuffle\([0-9, ]+\)\));",
                r"return Relax(\1);", s)
s, n2 = re.subn(r"return (OpFSub\(f32_id, one_f32, component\([0-9]\)\));",
                r"return Relax(\1);", s)
if (n1, n2) != (5, 4):
    sys.exit(f"ERROR: modifier patterns matched {n1}/{n2} times, expected 5/4")
files[CPP] = s

# combiners: rewritten with relaxed math (Dot3 bump mapping stays at full precision)
s = load(CPP)
start = s.find("Id FragmentModule::AppendColorCombiner(")
end = s.find("void FragmentModule::DefineArithmeticTypes() {")
region = s[start:end] if start >= 0 and end > start else ""
if ("Unknown color combiner operation" not in region
        or "Unknown alpha combiner operation" not in region
        or region.count("Id FragmentModule::Append") != 2):
    sys.exit("ERROR: combiner region not recognised")
NEW_COMBINERS = r'''Id FragmentModule::AppendColorCombiner(Pica::TexturingRegs::TevStageConfig::Operation operation) {
    using Operation = TevStageConfig::Operation;
    const Id half_vec{ConstF32(0.5f, 0.5f, 0.5f)};
    const Id one_vec{ConstF32(1.f, 1.f, 1.f)};
    const Id zero_vec{ConstF32(0.f, 0.f, 0.f)};
    Id color{};

    switch (operation) {
    case Operation::Replace:
        color = color_results_1;
        break;
    case Operation::Modulate:
        color = Relax(OpFMul(vec_ids.Get(3), color_results_1, color_results_2));
        break;
    case Operation::Add:
        color = Relax(OpFAdd(vec_ids.Get(3), color_results_1, color_results_2));
        break;
    case Operation::AddSigned:
        color = Relax(OpFSub(vec_ids.Get(3),
                             Relax(OpFAdd(vec_ids.Get(3), color_results_1, color_results_2)),
                             half_vec));
        break;
    case Operation::Lerp:
        color = Relax(OpFMix(vec_ids.Get(3), color_results_2, color_results_1, color_results_3));
        break;
    case Operation::Subtract:
        color = Relax(OpFSub(vec_ids.Get(3), color_results_1, color_results_2));
        break;
    case Operation::MultiplyThenAdd:
        color = Relax(OpFma(vec_ids.Get(3), color_results_1, color_results_2, color_results_3));
        break;
    case Operation::AddThenMultiply:
        color = Relax(OpFMin(vec_ids.Get(3),
                             Relax(OpFAdd(vec_ids.Get(3), color_results_1, color_results_2)),
                             one_vec));
        color = Relax(OpFMul(vec_ids.Get(3), color, color_results_3));
        break;
    case Operation::Dot3_RGB:
    case Operation::Dot3_RGBA:
        // Bump mapping: kept at full precision
        color = OpDot(f32_id, OpFSub(vec_ids.Get(3), color_results_1, half_vec),
                      OpFSub(vec_ids.Get(3), color_results_2, half_vec));
        color = OpFMul(f32_id, color, ConstF32(4.f));
        color = OpCompositeConstruct(vec_ids.Get(3), color, color, color);
        break;
    default:
        color = zero_vec;
        LOG_CRITICAL(Render, "Unknown color combiner operation: {}", operation);
        break;
    }

    // Clamp result to 0.0, 1.0
    return Relax(OpFClamp(vec_ids.Get(3), color, zero_vec, one_vec));
}

Id FragmentModule::AppendAlphaCombiner(TevStageConfig::Operation operation) {
    using Operation = TevStageConfig::Operation;
    Id color{};

    switch (operation) {
    case Operation::Replace:
        color = alpha_results_1;
        break;
    case Operation::Modulate:
        color = Relax(OpFMul(f32_id, alpha_results_1, alpha_results_2));
        break;
    case Operation::Add:
        color = Relax(OpFAdd(f32_id, alpha_results_1, alpha_results_2));
        break;
    case Operation::AddSigned:
        color = Relax(OpFSub(f32_id, Relax(OpFAdd(f32_id, alpha_results_1, alpha_results_2)),
                             ConstF32(0.5f)));
        break;
    case Operation::Lerp:
        color = Relax(OpFMix(f32_id, alpha_results_2, alpha_results_1, alpha_results_3));
        break;
    case Operation::Subtract:
        color = Relax(OpFSub(f32_id, alpha_results_1, alpha_results_2));
        break;
    case Operation::MultiplyThenAdd:
        color = Relax(OpFma(f32_id, alpha_results_1, alpha_results_2, alpha_results_3));
        break;
    case Operation::AddThenMultiply:
        color = Relax(OpFMin(f32_id, Relax(OpFAdd(f32_id, alpha_results_1, alpha_results_2)),
                             ConstF32(1.f)));
        color = Relax(OpFMul(f32_id, color, alpha_results_3));
        break;
    default:
        color = ConstF32(0.f);
        LOG_CRITICAL(Render, "Unknown alpha combiner operation: {}", operation);
        break;
    }

    return Relax(OpFClamp(f32_id, color, ConstF32(0.f), ConstF32(1.f)));
}

'''
files[CPP] = s[:start] + NEW_COMBINERS + s[end:]

# ---------------------------------------------------------------- strings (all locales)
T = {
    "values": ("Relaxed Precision Shaders",
               "Experimental (Vulkan). Uses 16-bit math for shader color blending, which can improve performance on Mali and Adreno GPUs. May cause slight color differences or graphical glitches with some drivers."),
    "values-b+en+GB": ("Relaxed Precision Shaders",
               "Experimental (Vulkan). Uses 16-bit maths for shader colour blending, which can improve performance on Mali and Adreno GPUs. May cause slight colour differences or graphical glitches with some drivers."),
    "values-b+ca+ES+valencia": ("Shaders de precisió relaxada",
               "Experimental (Vulkan). Utilitza càlculs de 16 bits per a la barreja de colors dels shaders, cosa que pot millorar el rendiment en GPUs Mali i Adreno. Pot causar lleugeres diferències de color o errors gràfics amb alguns controladors."),
    "values-b+es+419": ("Shaders de precisión relajada",
               "Experimental (Vulkan). Usa cálculos de 16 bits para la mezcla de color de los shaders, lo que puede mejorar el rendimiento en GPUs Mali y Adreno. Puede causar ligeras diferencias de color o fallos gráficos con algunos controladores."),
    "values-b+pt+BR": ("Shaders de precisão relaxada",
               "Experimental (Vulkan). Usa cálculos de 16 bits na mistura de cores dos shaders, o que pode melhorar o desempenho em GPUs Mali e Adreno. Pode causar pequenas diferenças de cor ou falhas gráficas com alguns drivers."),
    "values-b+zh+CN": ("宽松精度着色器",
               "实验性（Vulkan）。着色器颜色混合使用 16 位运算，可在 Mali 和 Adreno GPU 上提升性能。在某些驱动上可能造成轻微色差或画面异常。"),
    "values-b+zh+TW": ("寬鬆精度著色器",
               "實驗性（Vulkan）。著色器色彩混合使用 16 位元運算，可在 Mali 與 Adreno GPU 上提升效能。在某些驅動程式上可能造成輕微色差或畫面異常。"),
    "values-da": ("Shadere med afslappet præcision",
               "Eksperimentel (Vulkan). Bruger 16-bit beregninger til farveblanding i shadere, hvilket kan forbedre ydelsen på Mali- og Adreno-GPU'er. Kan give små farveforskelle eller grafiske fejl med nogle drivere."),
    "values-de": ("Shader mit reduzierter Genauigkeit",
               "Experimentell (Vulkan). Verwendet 16-Bit-Berechnungen für die Farbmischung in Shadern, was die Leistung auf Mali- und Adreno-GPUs verbessern kann. Kann bei manchen Treibern leichte Farbabweichungen oder Grafikfehler verursachen."),
    "values-el": ("Shaders χαλαρής ακρίβειας",
               "Πειραματικό (Vulkan). Χρησιμοποιεί υπολογισμούς 16 bit για την ανάμειξη χρωμάτων στα shaders, κάτι που μπορεί να βελτιώσει την απόδοση σε GPU Mali και Adreno. Μπορεί να προκαλέσει μικρές διαφορές χρώματος ή γραφικά προβλήματα σε ορισμένα προγράμματα οδήγησης."),
    "values-es": ("Shaders de precisión relajada",
               "Experimental (Vulkan). Usa cálculos de 16 bits para la mezcla de color de los shaders, lo que puede mejorar el rendimiento en GPUs Mali y Adreno. Puede causar ligeras diferencias de color o fallos gráficos con algunos controladores."),
    "values-fi": ("Rento tarkkuus -shaderit",
               "Kokeellinen (Vulkan). Käyttää 16-bittisiä laskutoimituksia shadereiden värien sekoitukseen, mikä voi parantaa suorituskykyä Mali- ja Adreno-GPU:illa. Voi aiheuttaa pieniä värieroja tai grafiikkavirheitä joillakin ajureilla."),
    "values-fr": ("Shaders à précision relâchée",
               "Expérimental (Vulkan). Utilise des calculs en 16 bits pour le mélange des couleurs dans les shaders, ce qui peut améliorer les performances sur les GPU Mali et Adreno. Peut provoquer de légères différences de couleur ou des défauts graphiques avec certains pilotes."),
    "values-hu": ("Relaxált pontosságú shaderek",
               "Kísérleti (Vulkan). 16 bites számításokat használ a shaderek színkeveréséhez, ami javíthatja a teljesítményt Mali és Adreno GPU-kon. Egyes illesztőprogramoknál enyhe színeltéréseket vagy grafikai hibákat okozhat."),
    "values-id": ("Shader Presisi Relaks",
               "Eksperimental (Vulkan). Menggunakan perhitungan 16-bit untuk pencampuran warna shader, yang dapat meningkatkan performa pada GPU Mali dan Adreno. Dapat menyebabkan sedikit perbedaan warna atau gangguan grafis pada beberapa driver."),
    "values-it": ("Shader a precisione ridotta",
               "Sperimentale (Vulkan). Usa calcoli a 16 bit per la miscelazione dei colori negli shader, il che può migliorare le prestazioni sulle GPU Mali e Adreno. Può causare lievi differenze di colore o glitch grafici con alcuni driver."),
    "values-ja": ("緩和精度シェーダー",
               "実験的（Vulkan）。シェーダーの色合成に16ビット演算を使用し、MaliおよびAdreno GPUでパフォーマンスが向上する場合があります。一部のドライバーでは、わずかな色の違いや表示の乱れが発生することがあります。"),
    "values-ko": ("완화된 정밀도 셰이더",
               "실험적 기능(Vulkan). 셰이더 색상 혼합에 16비트 연산을 사용하여 Mali 및 Adreno GPU에서 성능이 향상될 수 있습니다. 일부 드라이버에서는 미세한 색상 차이나 그래픽 오류가 발생할 수 있습니다."),
    "values-lt": ("Sumažinto tikslumo šešėliuokliai",
               "Eksperimentinis (Vulkan). Šešėliuoklių spalvų maišymui naudoja 16 bitų skaičiavimus, o tai gali pagerinti našumą Mali ir Adreno GPU. Su kai kuriomis tvarkyklėmis gali sukelti nedidelių spalvų skirtumų ar grafikos triktis."),
    "values-nb": ("Shadere med avslappet presisjon",
               "Eksperimentell (Vulkan). Bruker 16-biters beregninger til fargeblanding i shadere, noe som kan gi bedre ytelse på Mali- og Adreno-GPU-er. Kan gi små fargeforskjeller eller grafikkfeil med enkelte drivere."),
    "values-nl": ("Shaders met verlaagde precisie",
               "Experimenteel (Vulkan). Gebruikt 16-bits berekeningen voor kleurmenging in shaders, wat de prestaties op Mali- en Adreno-gpu's kan verbeteren. Kan bij sommige drivers lichte kleurverschillen of grafische fouten veroorzaken."),
    "values-pl": ("Shadery o obniżonej precyzji",
               "Eksperymentalne (Vulkan). Używa 16-bitowych obliczeń do mieszania kolorów w shaderach, co może poprawić wydajność na GPU Mali i Adreno. Może powodować niewielkie różnice kolorów lub błędy graficzne w przypadku niektórych sterowników."),
    "values-ro": ("Shadere cu precizie relaxată",
               "Experimental (Vulkan). Folosește calcule pe 16 biți pentru amestecarea culorilor în shadere, ceea ce poate îmbunătăți performanța pe GPU-urile Mali și Adreno. Poate cauza mici diferențe de culoare sau erori grafice cu unele drivere."),
    "values-ru": ("Шейдеры с пониженной точностью",
               "Экспериментально (Vulkan). Использует 16-битные вычисления для смешивания цветов в шейдерах, что может повысить производительность на GPU Mali и Adreno. На некоторых драйверах возможны небольшие отличия цветов или графические артефакты."),
    "values-sv": ("Shaders med avslappnad precision",
               "Experimentell (Vulkan). Använder 16-bitarsberäkningar för färgblandning i shaders, vilket kan förbättra prestandan på Mali- och Adreno-GPU:er. Kan ge små färgskillnader eller grafikfel med vissa drivrutiner."),
    "values-th": ("เชเดอร์ความแม่นยำแบบผ่อนปรน",
               "ทดลอง (Vulkan) ใช้การคำนวณ 16 บิตสำหรับการผสมสีในเชเดอร์ ซึ่งอาจช่วยเพิ่มประสิทธิภาพบน GPU Mali และ Adreno อาจทำให้สีแตกต่างเล็กน้อยหรือเกิดข้อผิดพลาดด้านกราฟิกกับไดรเวอร์บางตัว"),
    "values-tr": ("Gevşetilmiş Hassasiyetli Gölgelendiriciler",
               "Deneysel (Vulkan). Gölgelendiricilerde renk karışımı için 16 bit hesaplama kullanır; bu, Mali ve Adreno GPU'larda performansı artırabilir. Bazı sürücülerde hafif renk farklarına veya grafik hatalarına neden olabilir."),
    "values-vi": ("Shader độ chính xác nới lỏng",
               "Thử nghiệm (Vulkan). Dùng phép tính 16-bit để trộn màu trong shader, có thể cải thiện hiệu năng trên GPU Mali và Adreno. Có thể gây chênh lệch màu nhẹ hoặc lỗi đồ họa với một số trình điều khiển."),
}
for locale, (title, desc) in T.items():
    p = RES + locale + "/strings.xml"
    s = load(p)
    i = s.rfind("</resources>")
    if i < 0:
        sys.exit(f"ERROR: {p}: no </resources>")
    new = (f'    <string name="relaxed_precision">{esc(title)}</string>\n'
           f'    <string name="relaxed_precision_description">{esc(desc)}</string>\n')
    files[p] = s[:i] + new + s[i:]

for p, content in files.items():
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)
print(f"patched {len(files)} files")
