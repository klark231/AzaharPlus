#!/usr/bin/env python3
"""Follow-up to draw_batching.py. Run from the repo root:  python3 tweaks_and_network.py

 1. Draw Batching and Lighter Surfaces now live under the "Tweaks" header.
 2. Both are greyed out (not toggleable) while a game is running.
 3. The "takes effect the next time a game starts" sentence is removed from their
    descriptions in every language.
 4. Draw Batching and the new Web API URLs strings are translated for every locale.
 5. The two Web API URL settings are now one entry that opens a single dialog with two
    fields (second one optional), like Citra MMJ.
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
    """Android string escaping for apostrophes."""
    return s.replace("\\'", "'").replace("'", "\\'")


RES = "src/android/app/src/main/res/"
KT = "src/android/app/src/main/java/org/citra/citra_emu/features/settings/"

if "web_api_url_2_optional" in load(RES + "values/strings.xml"):
    print("already patched")
    sys.exit(0)

# ------------------------------------------------------------------ 1+2: Kotlin side
edit(KT + "model/BooleanSetting.kt",
     "            ASYNC_SHADERS,\n            DELAY_START_LLE_MODULES,\n",
     "            ASYNC_SHADERS,\n            VK_DRAW_BATCHING,\n            DELAY_START_LLE_MODULES,\n")
edit(KT + "model/IntSetting.kt",
     "            GRAPHICS_API,\n            AUDIO_INPUT_TYPE\n        )",
     "            GRAPHICS_API,\n            AUDIO_INPUT_TYPE,\n            VK_LIGHTER_SURFACES\n        )")

PRESENTER = KT + "ui/SettingsFragmentPresenter.kt"
LIGHTER_BLOCK = """            add(
                SingleChoiceSetting(
                    IntSetting.VK_LIGHTER_SURFACES,
                    R.string.lighter_surfaces,
                    R.string.lighter_surfaces_description,
                    R.array.lighterSurfacesNames,
                    R.array.lighterSurfacesValues,
                    IntSetting.VK_LIGHTER_SURFACES.key,
                    IntSetting.VK_LIGHTER_SURFACES.defaultValue
                )
            )
"""
BATCHING_BLOCK = """            add(
                SwitchSetting(
                    BooleanSetting.VK_DRAW_BATCHING,
                    R.string.draw_batching,
                    R.string.draw_batching_description,
                    BooleanSetting.VK_DRAW_BATCHING.key,
                    BooleanSetting.VK_DRAW_BATCHING.defaultValue
                )
            )
"""
edit(PRESENTER, LIGHTER_BLOCK, "")
edit(PRESENTER, BATCHING_BLOCK, "")
FLUSH_BLOCK = """            add(
                SwitchSetting(
                    BooleanSetting.DISABLE_FLUSH_CPU_WRITE,
                    R.string.disable_flush_cpu_write,
                    R.string.disable_flush_cpu_write_description,
                    BooleanSetting.DISABLE_FLUSH_CPU_WRITE.key,
                    BooleanSetting.DISABLE_FLUSH_CPU_WRITE.defaultValue
                )
            )
"""
edit(PRESENTER, FLUSH_BLOCK, FLUSH_BLOCK + BATCHING_BLOCK + LIGHTER_BLOCK)

# ------------------------------------------------------------------ 5: one dialog for both Web API URLs
edit(PRESENTER,
     """            add(
                StringInputSetting(
                    StringSetting.WEB_API_URL,
                    R.string.web_api_url,
                    R.string.web_api_url_description,
                    StringSetting.WEB_API_URL.key,
                    StringSetting.WEB_API_URL.defaultValue
                )
            )

            add(
                StringInputSetting(
                    StringSetting.WEB_API_URL_2,
                    R.string.web_api_url_2,
                    R.string.web_api_url_2_description,
                    StringSetting.WEB_API_URL_2.key,
                    StringSetting.WEB_API_URL_2.defaultValue
                )
            )
""",
     """            add(
                StringInputSetting(
                    StringSetting.WEB_API_URL,
                    R.string.web_api_urls,
                    R.string.web_api_url_description,
                    StringSetting.WEB_API_URL.key,
                    StringSetting.WEB_API_URL.defaultValue,
                    secondSetting = StringSetting.WEB_API_URL_2,
                    secondHintId = R.string.web_api_url_2_optional
                )
            )
""")
edit(KT + "model/view/StringInputSetting.kt",
     """    @StringRes override var disabledMessage: Int =
        R.string.setting_disabled_description_incompatible_setting
) : SettingsItem""",
     """    @StringRes override var disabledMessage: Int =
        R.string.setting_disabled_description_incompatible_setting,
    /** When set, the item opens one dialog that edits both this setting and [secondSetting]. */
    val secondSetting: AbstractStringSetting? = null,
    @StringRes val secondHintId: Int = 0
) : SettingsItem""")
edit(KT + "ui/viewholder/StringInputViewHolder.kt",
     "        binding.textSettingValue.text = setting.setting?.valueAsString\n",
     """        val firstValue = setting.setting?.valueAsString.orEmpty()
        val secondValue = (setting as? StringInputSetting)?.secondSetting?.valueAsString.orEmpty()
        binding.textSettingValue.text =
            if (secondValue.isNotEmpty()) "$firstValue\\n$secondValue" else firstValue
""")
ADAPTER = KT + "ui/SettingsAdapter.kt"
edit(ADAPTER, "import android.view.LayoutInflater\n",
     "import android.view.LayoutInflater\nimport android.widget.LinearLayout\n")
edit(ADAPTER,
     """    fun onStringInputClick(item: StringInputSetting, position: Int) {
        clickedItem = item
""",
     """    private fun showWebApiUrlsDialog(item: StringInputSetting) {
        val second = item.secondSetting ?: return
        val inflater = LayoutInflater.from(context)
        val firstBinding = DialogSoftwareKeyboardBinding.inflate(inflater)
        val secondBinding = DialogSoftwareKeyboardBinding.inflate(inflater)

        firstBinding.root.hint = context.getString(R.string.web_api_url)
        secondBinding.root.hint = context.getString(item.secondHintId)
        firstBinding.editTextInput.setText(item.selectedValue)
        secondBinding.editTextInput.setText(second.valueAsString)

        val container = LinearLayout(context).apply {
            orientation = LinearLayout.VERTICAL
            addView(firstBinding.root)
            addView(secondBinding.root)
        }

        dialog = MaterialAlertDialogBuilder(context)
            .setView(container)
            .setTitle(item.nameId)
            .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int ->
                val firstValue = firstBinding.editTextInput.text?.toString()?.trim() ?: ""
                val secondValue = secondBinding.editTextInput.text?.toString()?.trim() ?: ""
                if (item.selectedValue != firstValue || second.valueAsString != secondValue) {
                    fragmentView?.onSettingChanged()
                }
                fragmentView?.putSetting(item.setSelectedValue(firstValue))
                second.string = secondValue
                fragmentView?.putSetting(second)
                fragmentView.loadSettingsList()
                closeDialog()
            }
            .setNegativeButton(android.R.string.cancel, defaultCancelListener)
            .show()
    }

    fun onStringInputClick(item: StringInputSetting, position: Int) {
        if (item.secondSetting != null) {
            showWebApiUrlsDialog(item)
            return
        }

        clickedItem = item
""")

# ------------------------------------------------------------------ 3+4: strings
# last sentence of the old lighter_surfaces_description in each language
OLD_SENTENCE = {
    "values": "Takes effect the next time a game starts.",
    "values-b+ca+ES+valencia": "S'aplica la pròxima vegada que s'inicie un joc.",
    "values-b+es+419": "Se aplica la próxima vez que se inicie un juego.",
    "values-b+pt+BR": "Entra em vigor na próxima vez que um jogo for iniciado.",
    "values-b+zh+CN": "下次启动游戏时生效。",
    "values-b+zh+TW": "下次啟動遊戲時生效。",
    "values-da": "Træder i kraft næste gang et spil startes.",
    "values-de": "Wirkt sich beim nächsten Spielstart aus.",
    "values-el": "Ισχύει την επόμενη φορά που θα ξεκινήσει ένα παιχνίδι.",
    "values-es": "Se aplica la próxima vez que se inicie un juego.",
    "values-fi": "Tulee voimaan, kun peli käynnistetään seuraavan kerran.",
    "values-fr": "Pris en compte au prochain lancement d'un jeu.",
    "values-hu": "A játék következő indításakor lép életbe.",
    "values-id": "Berlaku saat game dimulai berikutnya.",
    "values-it": "Ha effetto al prossimo avvio di un gioco.",
    "values-ja": "次回のゲーム起動時に反映されます。",
    "values-ko": "다음에 게임을 시작할 때 적용됩니다.",
    "values-lt": "Įsigalioja kitą kartą paleidus žaidimą.",
    "values-nb": "Trer i kraft neste gang et spill startes.",
    "values-nl": "Gaat in bij de volgende keer dat een game start.",
    "values-pl": "Zacznie działać przy następnym uruchomieniu gry.",
    "values-ro": "Se aplică la următoarea pornire a unui joc.",
    "values-ru": "Применяется при следующем запуске игры.",
    "values-sv": "Börjar gälla nästa gång ett spel startas.",
    "values-th": "มีผลเมื่อเริ่มเกมครั้งถัดไป",
    "values-tr": "Oyun bir sonraki başlatıldığında geçerli olur.",
    "values-vi": "Có hiệu lực ở lần chạy game tiếp theo.",
}

# (draw_batching, draw_batching_description, web_api_urls, web_api_url_2_optional)
T = {
    "values": (
        "Draw Batching",
        "Experimental (Vulkan). Merges consecutive draw calls that use identical state into one, reducing CPU and driver overhead. If you see missing or distorted geometry, turn this off.",
        "Web API URLs", "Web API URL 2 (optional)"),
    "values-b+en+GB": (
        "Draw Batching",
        "Experimental (Vulkan). Merges consecutive draw calls that use identical state into one, reducing CPU and driver overhead. If you see missing or distorted geometry, turn this off.",
        "Web API URLs", "Web API URL 2 (optional)"),
    "values-b+ca+ES+valencia": (
        "Agrupació de crides de dibuix",
        "Experimental (Vulkan). Combina en una sola les crides de dibuix consecutives amb un estat idèntic, la qual cosa redueix la càrrega de la CPU i del controlador. Si veus geometria que falta o deformada, desactiva-ho.",
        "URLs d'API Web", "URL d'API Web 2 (opcional)"),
    "values-b+es+419": (
        "Agrupación de llamadas de dibujo",
        "Experimental (Vulkan). Combina en una sola las llamadas de dibujo consecutivas con un estado idéntico, lo que reduce la carga de la CPU y del controlador. Si ves geometría faltante o deformada, desactívalo.",
        "URLs de la Web API", "URL de la Web API 2 (opcional)"),
    "values-b+pt+BR": (
        "Agrupamento de chamadas de desenho",
        "Experimental (Vulkan). Combina em uma só as chamadas de desenho consecutivas com estado idêntico, reduzindo a carga da CPU e do driver. Se notar geometria ausente ou distorcida, desative.",
        "URLs da API Web", "URL da API Web 2 (opcional)"),
    "values-b+zh+CN": (
        "绘制批处理",
        "实验性（Vulkan）。将状态完全相同的连续绘制调用合并为一次，降低 CPU 和驱动开销。如果出现几何体缺失或变形，请关闭此选项。",
        "Web API 地址", "Web API 地址 2（可选）"),
    "values-b+zh+TW": (
        "繪製批次處理",
        "實驗性（Vulkan）。將狀態完全相同的連續繪製呼叫合併為一次，降低 CPU 與驅動程式負擔。若出現幾何缺失或變形，請關閉此選項。",
        "Web API 網址", "Web API 網址 2（選填）"),
    "values-da": (
        "Draw-batching",
        "Eksperimentel (Vulkan). Slår på hinanden følgende tegnekald med identisk tilstand sammen til ét, hvilket reducerer belastningen på CPU og driver. Hvis du ser manglende eller forvrænget geometri, så slå det fra.",
        "Web API-URL'er", "Web API-URL 2 (valgfri)"),
    "values-de": (
        "Draw-Batching",
        "Experimentell (Vulkan). Fasst aufeinanderfolgende Zeichenaufrufe mit identischem Zustand zu einem zusammen und verringert so die Last für CPU und Treiber. Wenn Geometrie fehlt oder verzerrt aussieht, schalte dies aus.",
        "Web-API-URLs", "Web-API-URL 2 (optional)"),
    "values-el": (
        "Ομαδοποίηση κλήσεων σχεδίασης",
        "Πειραματικό (Vulkan). Συγχωνεύει διαδοχικές κλήσεις σχεδίασης με πανομοιότυπη κατάσταση σε μία, μειώνοντας το φορτίο της CPU και του προγράμματος οδήγησης. Αν δείτε γεωμετρία που λείπει ή παραμορφώνεται, απενεργοποιήστε το.",
        "Web API URLs", "Web API URL 2 (προαιρετικό)"),
    "values-es": (
        "Agrupación de llamadas de dibujo",
        "Experimental (Vulkan). Combina en una sola las llamadas de dibujo consecutivas con un estado idéntico, lo que reduce la carga de la CPU y del controlador. Si ves geometría que falta o aparece deformada, desactívalo.",
        "URLs de API Web", "URL de API Web 2 (opcional)"),
    "values-fi": (
        "Piirtokutsujen yhdistäminen",
        "Kokeellinen (Vulkan). Yhdistää peräkkäiset piirtokutsut, joilla on identtinen tila, yhdeksi, mikä vähentää suorittimen ja ajurin kuormitusta. Jos näet puuttuvaa tai vääristynyttä geometriaa, poista tämä käytöstä.",
        "Web API -URL-osoitteet", "Web API URL 2 (valinnainen)"),
    "values-fr": (
        "Regroupement des appels de rendu",
        "Expérimental (Vulkan). Fusionne en un seul les appels de rendu consécutifs ayant un état identique, ce qui réduit la charge du CPU et du pilote. Si vous voyez de la géométrie manquante ou déformée, désactivez cette option.",
        "URL de l'API Web", "URL de l'API Web 2 (facultatif)"),
    "values-hu": (
        "Rajzolási hívások csoportosítása",
        "Kísérleti (Vulkan). Az azonos állapotú, egymást követő rajzolási hívásokat eggyé vonja össze, csökkentve a CPU és az illesztőprogram terhelését. Ha hiányzó vagy torz geometriát látsz, kapcsold ki.",
        "Web API URL-ek", "Web API URL 2 (opcionális)"),
    "values-id": (
        "Draw Batching",
        "Eksperimental (Vulkan). Menggabungkan panggilan gambar berurutan dengan status identik menjadi satu, sehingga mengurangi beban CPU dan driver. Jika terlihat geometri hilang atau terdistorsi, matikan opsi ini.",
        "URL Web API", "URL Web API 2 (opsional)"),
    "values-it": (
        "Raggruppamento delle chiamate di disegno",
        "Sperimentale (Vulkan). Unisce in una sola le chiamate di disegno consecutive con stato identico, riducendo il carico di CPU e driver. Se noti geometrie mancanti o distorte, disattivalo.",
        "URL API Web", "URL API Web 2 (facoltativo)"),
    "values-ja": (
        "描画バッチ処理",
        "実験的（Vulkan）。状態が同一の連続した描画呼び出しを1つにまとめ、CPUとドライバーの負荷を減らします。ジオメトリが欠けたり歪んだりする場合は、オフにしてください。",
        "Web API URL", "Web API URL 2（任意）"),
    "values-ko": (
        "드로우 배칭",
        "실험적 기능(Vulkan). 상태가 동일한 연속된 드로우 호출을 하나로 합쳐 CPU와 드라이버 부하를 줄입니다. 지오메트리가 누락되거나 왜곡되어 보이면 이 기능을 끄세요.",
        "Web API URL", "Web API URL 2 (선택 사항)"),
    "values-lt": (
        "Piešimo iškvietimų grupavimas",
        "Eksperimentinis (Vulkan). Sujungia iš eilės einančius piešimo iškvietimus su identiška būsena į vieną, taip sumažindamas procesoriaus ir tvarkyklės apkrovą. Jei matote trūkstamą ar iškraipytą geometriją, išjunkite.",
        "Web API URL adresai", "Web API URL 2 (neprivaloma)"),
    "values-nb": (
        "Draw-batching",
        "Eksperimentell (Vulkan). Slår sammen påfølgende tegnekall med identisk tilstand til ett, noe som reduserer belastningen på CPU og driver. Hvis du ser manglende eller forvrengt geometri, slå dette av.",
        "Web API-URL-er", "Web API-URL 2 (valgfri)"),
    "values-nl": (
        "Draw-batching",
        "Experimenteel (Vulkan). Voegt opeenvolgende tekenaanroepen met identieke status samen tot één, waardoor de belasting van CPU en driver afneemt. Zie je ontbrekende of vervormde geometrie, zet dit dan uit.",
        "Web API-URL's", "Web API-URL 2 (optioneel)"),
    "values-pl": (
        "Grupowanie wywołań rysowania",
        "Eksperymentalne (Vulkan). Łączy kolejne wywołania rysowania o identycznym stanie w jedno, zmniejszając obciążenie procesora i sterownika. Jeśli widzisz brakującą lub zniekształconą geometrię, wyłącz tę opcję.",
        "Adresy URL Web API", "Web API URL 2 (opcjonalnie)"),
    "values-ro": (
        "Gruparea apelurilor de desenare",
        "Experimental (Vulkan). Combină apelurile de desenare consecutive cu stare identică într-unul singur, reducând încărcarea CPU-ului și a driverului. Dacă observi geometrie lipsă sau deformată, dezactivează opțiunea.",
        "URL-uri Web API", "Web API URL 2 (opțional)"),
    "values-ru": (
        "Пакетирование вызовов отрисовки",
        "Экспериментально (Vulkan). Объединяет последовательные вызовы отрисовки с одинаковым состоянием в один, снижая нагрузку на CPU и драйвер. Если пропадает или искажается геометрия, отключите эту функцию.",
        "URL Web API", "URL Web API 2 (необязательно)"),
    "values-sv": (
        "Draw-batching",
        "Experimentell (Vulkan). Slår ihop på varandra följande ritanrop med identiskt tillstånd till ett, vilket minskar belastningen på CPU och drivrutin. Om du ser saknad eller förvrängd geometri, stäng av detta.",
        "Webb-API-URL:er", "Webb-API-URL 2 (valfri)"),
    "values-th": (
        "การรวมคำสั่งวาด",
        "ทดลอง (Vulkan) รวมคำสั่งวาดที่ต่อเนื่องกันและมีสถานะเหมือนกันให้เป็นหนึ่งเดียว ช่วยลดภาระของ CPU และไดรเวอร์ หากพบรูปทรงหายไปหรือบิดเบี้ยว ให้ปิดตัวเลือกนี้",
        "URL ของ Web API", "URL ของ Web API 2 (ไม่บังคับ)"),
    "values-tr": (
        "Çizim Gruplama",
        "Deneysel (Vulkan). Aynı duruma sahip ardışık çizim çağrılarını tek bir çağrıda birleştirerek CPU ve sürücü yükünü azaltır. Eksik veya bozuk geometri görürseniz bunu kapatın.",
        "Web API URL'leri", "Web API URL 2 (isteğe bağlı)"),
    "values-vi": (
        "Gộp lệnh vẽ",
        "Thử nghiệm (Vulkan). Gộp các lệnh vẽ liên tiếp có trạng thái giống hệt nhau thành một, giúp giảm tải cho CPU và trình điều khiển. Nếu thấy hình học bị thiếu hoặc méo, hãy tắt tùy chọn này.",
        "URL Web API", "URL Web API 2 (không bắt buộc)"),
}

for locale, (title, desc, urls_title, url2_hint) in T.items():
    p = RES + locale + "/strings.xml"
    s = load(p)

    # drop the "takes effect next game start" sentence from the lighter surfaces description
    sentence = OLD_SENTENCE.get(locale)
    if sentence:
        m = re.search(r'(<string name="lighter_surfaces_description">)(.*?)(</string>)', s, re.S)
        if not m:
            sys.exit(f"ERROR: {p}: lighter_surfaces_description not found")
        body = m.group(2)
        old = esc(sentence)
        if old not in body:
            sys.exit(f"ERROR: {p}: old sentence not found in lighter_surfaces_description")
        body = body.replace(old, "").rstrip()
        s = s[:m.start(2)] + body + s[m.end(2):]

    if locale == "values":
        # the English draw_batching strings already exist, so only fix the description
        s = s.replace(" Takes effect the next time a game starts.", "")
        if "Takes effect the next time" in s:
            sys.exit(f"ERROR: {p}: leftover 'takes effect' sentence")
        new = (f'    <string name="web_api_urls">{esc(urls_title)}</string>\n'
               f'    <string name="web_api_url_2_optional">{esc(url2_hint)}</string>\n')
    else:
        new = (f'    <string name="draw_batching">{esc(title)}</string>\n'
               f'    <string name="draw_batching_description">{esc(desc)}</string>\n'
               f'    <string name="web_api_urls">{esc(urls_title)}</string>\n'
               f'    <string name="web_api_url_2_optional">{esc(url2_hint)}</string>\n')

    i = s.rfind("</resources>")
    if i < 0:
        sys.exit(f"ERROR: {p}: no </resources>")
    files[p] = s[:i] + new + s[i:]

for p, content in files.items():
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(content)
print(f"patched {len(files)} files")
