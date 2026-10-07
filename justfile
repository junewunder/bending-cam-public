set shell := ["bash", "-euo", "pipefail", "-c"]

bundle := env_var_or_default("CP_BUNDLE", "")

mod phone

_default:
    @just --list

drive:
    @just _drive

_drive:
    #!/usr/bin/env bash
    set -euo pipefail
    for d in /run/media/$USER/CIRCUITPY /media/$USER/CIRCUITPY /mnt/CIRCUITPY; do
        if [ -d "$d" ]; then echo "$d"; exit 0; fi
    done
    if command -v udisksctl >/dev/null; then
        dev=$(readlink -f /dev/disk/by-label/CIRCUITPY 2>/dev/null || true)
        if [ -n "${dev:-}" ] && [ -b "$dev" ]; then
            udisksctl mount -b "$dev" >&2
            for d in /run/media/$USER/CIRCUITPY /media/$USER/CIRCUITPY; do
                if [ -d "$d" ]; then echo "$d"; exit 0; fi
            done
        fi
    fi
    echo "CIRCUITPY not mounted, and no CIRCUITPY-labelled device to mount" >&2
    if ls /dev/ttyACM* >/dev/null 2>&1; then
        echo "the board is up on serial, so it is in field mode: run 'just devmode'" >&2
    else
        echo "is the board plugged in? check: lsusb -d 303a:" >&2
    fi
    exit 1

board_id := "espressif_esp32s3_devkitc_1_n8r8"

sync: (_require_board board_id)
    #!/usr/bin/env bash
    set -euo pipefail
    d=$(just _drive)
    cp src/code.py "$d/code.py"
    sync
    cmp -s src/code.py "$d/code.py" || { echo "!! copy did not verify" >&2; exit 1; }
    echo "-> $d/code.py (from src/code.py; host-side check only -- prefer just push)"

push src follow="30":
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/push_code.py "{{src}}" --follow {{follow}}

settings follow="45":
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/push_code.py src/settings.toml --as settings.toml \
        --reset --follow {{follow}}

boot follow="20":
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/push_code.py src/boot.py --as boot.py \
        --reset --follow {{follow}}

devmode:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/devmode.py

safemode:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/push_code.py src/safemode.py --as safemode.py --follow 0

sim *args:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/sim/run.py {{args}}

fuzz *args:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/sim/fuzz.py {{args}}

willow:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/push_code.py src/willow.py --as willow.py --follow 0

ui-export:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/ui_export.py

ui follow="15": ui-export
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/push_code.py src/ui.bin --as ui.bin --follow {{follow}}

bench-ui follow="110":
    #!/usr/bin/env bash
    set -euo pipefail
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    sed 's/^BENCH_UI = False$/BENCH_UI = True/' src/code.py > "$tmp/code.py"
    grep -q '^BENCH_UI = True$' "$tmp/code.py" || { echo "!! no 'BENCH_UI = False' line in src/code.py" >&2; exit 1; }
    python3 tools/push_code.py "$tmp/code.py" --follow {{follow}}
    python3 tools/push_code.py src/code.py --follow 0

bench-auto script="full" follow="330":
    #!/usr/bin/env bash
    set -euo pipefail
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    sed 's/^BENCH_AUTO = False$/BENCH_AUTO = "{{script}}"/' src/code.py > "$tmp/code.py"
    grep -q '^BENCH_AUTO = "{{script}}"$' "$tmp/code.py" || { echo "!! no 'BENCH_AUTO = False' line in src/code.py" >&2; exit 1; }
    python3 tools/push_code.py "$tmp/code.py" --follow {{follow}}
    python3 tools/push_code.py src/code.py --follow 0

bringup n:
    @just _bringup src/bringup {{board_id}} {{n}}

_require_board board:
    #!/usr/bin/env bash
    set -euo pipefail
    d=$(just _drive)
    have=$(sed -n 's/^Board ID:\(.*\)$/\1/p' "$d/boot_out.txt" | tr -d '\r')
    if [ "$have" != "{{board}}" ]; then
        echo "!! board is '${have:-unknown}', these scripts are for '{{board}}'" >&2
        exit 1
    fi

_bringup dir board n: (_require_board board)
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    matches=({{dir}}/{{n}}_*.py)
    if [ ${#matches[@]} -eq 0 ]; then
        matches=({{dir}}/{{n}}*.py)
    fi
    if [ ${#matches[@]} -eq 0 ]; then
        echo "no bring-up script matching '{{n}}'; available:" >&2
        ls {{dir}}/ >&2
        exit 1
    fi
    src="${matches[0]}"
    d=$(just _drive)
    cp "$src" "$d/code.py"
    sync
    cmp -s "$src" "$d/code.py" || { echo "!! copy did not verify" >&2; exit 1; }
    echo "-> $d/code.py (from $src, verified)"
    echo "   the board is NOT running src/code.py -- 'just which' says what it is"

which:
    #!/usr/bin/env bash
    set -euo pipefail
    d=$(just _drive)
    if [ ! -f "$d/code.py" ]; then echo "no code.py on the board" >&2; exit 1; fi
    for f in src/code.py src/bringup/*.py; do
        if cmp -s "$f" "$d/code.py"; then echo "board is running: $f"; exit 0; fi
    done
    echo "board's code.py matches no file in src/ -- edited in place, or stale."
    echo "first line: $(head -1 "$d/code.py")"

fetch-bundle series="10.x":
    #!/usr/bin/env bash
    set -euo pipefail
    tag=$(curl -sSfL https://api.github.com/repos/adafruit/Adafruit_CircuitPython_Bundle/releases/latest \
          | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p')
    if [ -z "$tag" ]; then echo "could not resolve latest bundle tag" >&2; exit 1; fi
    zip="adafruit-circuitpython-bundle-{{series}}-mpy-$tag.zip"
    mkdir -p vendor
    if [ ! -f "vendor/$zip" ]; then
        echo "fetching $zip"
        curl -sSfL --output "vendor/$zip" \
            "https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/$tag/$zip"
    else
        echo "already have vendor/$zip"
    fi
    unzip -q -o "vendor/$zip" -d vendor
    echo "-> vendor/${zip%.zip}/lib"

libs:
    #!/usr/bin/env bash
    set -euo pipefail
    shopt -s nullglob
    lib="{{bundle}}"
    if [ -z "$lib" ]; then
        candidates=(vendor/adafruit-circuitpython-bundle-*-mpy-*/lib)
        if [ ${#candidates[@]} -eq 0 ]; then
            echo "no bundle under vendor/; run 'just fetch-bundle' or set CP_BUNDLE" >&2
            exit 1
        fi
        if [ ${#candidates[@]} -gt 1 ]; then
            echo "multiple bundles under vendor/; set CP_BUNDLE to one of:" >&2
            printf '  %s\n' "${candidates[@]}" >&2
            exit 1
        fi
        lib="${candidates[0]}"
    fi
    if [ ! -d "$lib" ]; then
        echo "bundle lib dir not found at $lib" >&2
        exit 1
    fi
    echo "using bundle: $lib"
    d=$(just _drive)
    mkdir -p "$d/lib"
    for item in adafruit_st7789.mpy; do
        if [ ! -e "$lib/$item" ]; then
            echo "missing from bundle: $item" >&2
            exit 1
        fi
        rm -rf "${d:?}/lib/$item"
        cp -r "$lib/$item" "$d/lib/"
        echo "-> lib/$item"
    done
    sync

ls:
    #!/usr/bin/env bash
    set -euo pipefail
    d=$(just _drive)
    ls -la "$d" "$d/lib" 2>/dev/null || ls -la "$d"

pull remote local:
    #!/usr/bin/env bash
    set -euo pipefail
    python3 tools/pull_serial.py "{{remote}}" "{{local}}"
    case "{{local}}" in
        *.bmp|*.BMP) just convert "{{local}}" ;;
    esac

convert +paths:
    #!/usr/bin/env bash
    set -euo pipefail
    exec uv run --no-project --quiet --with pillow python3 tools/to_jpeg.py {{paths}}

sd-ls:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/pull_serial.py --ls /sd

ble-throughput bytes="400000":
    #!/usr/bin/env bash
    set -euo pipefail
    exec uv run --no-project --quiet --with bleak python3 tools/ble_throughput.py {{bytes}}

ble-receive dir="stills" *flags:
    #!/usr/bin/env bash
    set -euo pipefail
    exec uv run --no-project --quiet --with bleak python3 tools/ble_receive.py "{{dir}}" {{flags}}

[positional-arguments]
ble-settings *args:
    #!/usr/bin/env bash
    set -euo pipefail
    exec uv run --no-project --quiet --with bleak python3 tools/ble_settings.py "$@"

console:
    #!/usr/bin/env bash
    set -euo pipefail
    port=$(ls /dev/ttyACM* 2>/dev/null | head -1)
    if [ -z "$port" ]; then echo "no /dev/ttyACM* found" >&2; exit 1; fi
    if command -v tio >/dev/null; then exec tio "$port"
    elif command -v picocom >/dev/null; then exec picocom -b 115200 "$port"
    elif command -v mpremote >/dev/null; then exec mpremote connect "$port" repl
    else echo "install tio or picocom" >&2; exit 1
    fi

_download_port:
    #!/usr/bin/env bash
    set -euo pipefail
    for t in /sys/class/tty/ttyACM*; do
        [ -e "$t" ] || continue
        u=$(readlink -f "$t/device/..")
        [ "$(cat "$u/idVendor" 2>/dev/null)" = 303a ] || continue
        [ "$(cat "$u/idProduct" 2>/dev/null)" != 7003 ] || continue
        echo "/dev/$(basename "$t")"; exit 0
    done
    echo "no ESP32-S3 in download mode" >&2
    echo "try: just bootloader   (or hold BOOT, tap RST, release BOOT)" >&2
    exit 1

version:
    #!/usr/bin/env bash
    set -euo pipefail
    cat "$(just _drive)/boot_out.txt"

bootloader:
    #!/usr/bin/env bash
    set -euo pipefail
    exec python3 tools/bootloader.py

backup:
    #!/usr/bin/env bash
    set -euo pipefail
    d=$(just _drive)
    out="backup/$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$out"
    cp -a "$d"/. "$out"/
    sync
    echo "-> $out"
    sed -n 1p "$out/boot_out.txt" 2>/dev/null || echo "   (no boot_out.txt?)"

flash bin="vendor/adafruit-circuitpython-espressif_esp32s3_devkitc_1_n8r8-en_US-10.3.0.bin" erase="no":
    #!/usr/bin/env bash
    set -euo pipefail
    bin="{{bin}}"
    if [ ! -f "$bin" ]; then
        echo "no such image: $bin" >&2
        echo "have:" >&2; ls vendor/*.bin >&2
        exit 1
    fi
    python3 - "$bin" <<'PY'
    import sys
    d = open(sys.argv[1], "rb").read()
    if len(d) < 0x10000 or d[0] != 0xE9:
        sys.exit("not a merged ESP image (no 0xE9 at 0x0, or too short)")
    chip = d[12] | d[13] << 8
    if chip != 9:
        sys.exit("chip ID %d, not ESP32-S3 (9) -- another chip's build" % chip)
    print("   image ok: ESP32-S3, %d KB, merged at 0x0" % (len(d) // 1024))
    PY

    p=$(just _download_port)
    erase=()
    [ "{{erase}}" = yes ] && erase=(--erase-all)
    echo "flashing $bin -> $p"
    esptool --chip esp32s3 --port "$p" --after watchdog-reset \
        write-flash "${erase[@]}" 0x0 "$bin"

    echo "waiting for CIRCUITPY to come back..."
    for _ in $(seq 40); do
        if d=$(just _drive 2>/dev/null); then
            echo
            cat "$d/boot_out.txt"
            echo
            echo "-> flashed. Next: just libs && just push src/code.py"
            [ "{{erase}}" = yes ] && echo "   and after an erase: just safemode && just settings"
            exit 0
        fi
        sleep 1
    done
    echo "CIRCUITPY did not reappear within 40s." >&2
    echo "check: lsusb -d 303a:  -- 1001 means still in the ROM loader; press RST" >&2
    exit 1

pcb-parts:
    #!/usr/bin/env bash
    set -euo pipefail
    manifest=(
        "4311|adafruit/Adafruit-2.0-inch-240x320-TFT-PCB|master|4311-tft-2.0in-320x240-eyespi"
        "5840|adafruit/Adafruit-OV5640-Camera-Breakout-PCB|main|5840-ov5640-camera"
    )
    for row in "${manifest[@]}"; do
        IFS='|' read -r pid repo branch dir <<<"$row"
        out="vendor/parts/$dir"
        sha=$(curl -sSfL "https://api.github.com/repos/$repo/commits/$branch" \
              | sed -n 's/.*"sha": *"\([^"]*\)".*/\1/p' | head -1)
        if [ -z "$sha" ]; then echo "could not resolve $repo@$branch" >&2; exit 1; fi
        if [ -f "$out/PROVENANCE.txt" ] && grep -q "$sha" "$out/PROVENANCE.txt"; then
            echo "up to date: $out (${sha:0:8})"
            continue
        fi
        tmp=$(mktemp -d)
        curl -sSfL "https://api.github.com/repos/$repo/tarball/$sha" | tar xz -C "$tmp"
        src=$(echo "$tmp"/*/)
        mkdir -p "$out"
        find "$src" -maxdepth 1 -type f \
            \( -iname '*.brd' -o -iname '*.sch' -o -iname 'license*' -o -iname 'README*' \) \
            -exec cp {} "$out/" \;
        printf 'PID %s\nhttps://github.com/%s\ncommit %s (%s)\nfetched %s by `just pcb-parts`\n' \
            "$pid" "$repo" "$sha" "$branch" "$(date -I)" > "$out/PROVENANCE.txt"
        rm -rf "$tmp"
        echo "-> $out (${sha:0:8})"
    done
    out="vendor/parts/espressif-esp32-s3-devkitc-1"
    base=https://dl.espressif.com/dl/schematics
    files=(
        "esp_idf/DXF_ESP32-S3-DevKitC-1_V1.1_20220429.dxf"
        "esp_idf/DXF_ESP32-S3-DevKitC-1_V1.1_20220429.pdf"
        "SCH_ESP32-S3-DevKitC-1_V1.1_20221130.pdf"
    )
    mkdir -p "$out"
    fetched=0
    for f in "${files[@]}"; do
        if [ ! -f "$out/$(basename "$f")" ]; then
            curl -sSfL -o "$out/$(basename "$f")" "$base/$f"
            fetched=1
        fi
    done
    if [ "$fetched" = 1 ] || [ ! -f "$out/PROVENANCE.txt" ]; then
        {
            printf 'Espressif ESP32-S3-DevKitC-1 v1.1 (v3 fits the N8R8)\n'
            printf 'https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html\n'
            for f in "${files[@]}"; do printf '%s/%s\n' "$base" "$f"; done
            printf 'fetched %s by `just pcb-parts`\nNo board source is published -- the DXF is the mechanical drawing.\n' "$(date -I)"
        } > "$out/PROVENANCE.txt"
        echo "-> $out"
    else
        echo "up to date: $out"
    fi

tsci := justfile_directory() / "pcb/node_modules/.bin/tsci"

pcb-build board="test00":
    #!/usr/bin/env bash
    set -euo pipefail
    cd pcb && {{tsci}} build {{board}}/{{board}}.circuit.tsx --pcb-png
    echo "-> pcb/dist/{{board}}/{{board}}/pcb.png"

pcb-netlist board="test00":
    #!/usr/bin/env bash
    set -euo pipefail
    cd pcb && {{tsci}} check netlist {{board}}/{{board}}.circuit.tsx

pcb-export board="test00":
    #!/usr/bin/env bash
    set -euo pipefail
    cd pcb/{{board}}
    mkdir -p ../dist/export
    for f in kicad_pcb kicad_sch; do
        {{tsci}} export {{board}}.circuit.tsx -f "$f" -o "../dist/export/{{board}}.$f"
    done
    {{tsci}} export {{board}}.circuit.tsx -f gerbers -o "../dist/export/{{board}}-gerbers.zip"
    echo "-> pcb/dist/export/"

pcb-review board="test00": (pcb-export board)
    #!/usr/bin/env bash
    set -euo pipefail
    python3 .claude/skills/kicad/scripts/analyze_pcb.py \
        "pcb/dist/export/{{board}}.kicad_pcb" --text --stage layout

pcb-copper board="test00": (pcb-build board)
    #!/usr/bin/env bash
    set -euo pipefail
    python3 pcb/tools/check_copper.py "pcb/dist/{{board}}/{{board}}/circuit.json"

pcb-all board="test00": (pcb-build board) (pcb-netlist board) (pcb-copper board) (pcb-review board)
    @echo "-> {{board}} ok"

pcb-fab board="v3": (pcb-export board)
    #!/usr/bin/env bash
    set -euo pipefail
    unset APPDIR
    if command -v kicad-cli >/dev/null; then
        kc=(kicad-cli); kpy=(python3 -u)
    elif flatpak info org.kicad.KiCad >/dev/null 2>&1; then
        kc=(flatpak run --command=kicad-cli org.kicad.KiCad)
        kpy=(flatpak run --command=python3 org.kicad.KiCad -u)
    else
        echo "no kicad-cli: 'sudo dnf install kicad' or 'flatpak install flathub org.kicad.KiCad'" >&2
        exit 1
    fi
    out="pcb/dist/fab/{{board}}"
    rm -rf "$out"; mkdir -p "$out/gerbers"
    cp "pcb/dist/export/{{board}}.kicad_pcb" "$out/{{board}}.kicad_pcb"

    python3 - "$out/{{board}}.kicad_pcb" <<'PY'
    import re, sys
    path = sys.argv[1]
    src = open(path).read()
    zones = len(re.findall(r"^  \(zone\b", src, re.M))
    if not zones:
        sys.exit("!! no zone in the export -- the ground pour is missing")
    src, n = re.subn(r"\(connect_pads yes\b", "(connect_pads", src)
    open(path, "w").write(src)
    print(f"pad connections: {n} of {zones} zone(s) switched Solid -> thermal relief")
    PY

    pro="$out/{{board}}.kicad_pro"
    (cd pcb/{{board}} && {{tsci}} export {{board}}.circuit.tsx -f circuit-json \
        -o "../dist/fab/{{board}}/circuit.json" >/dev/null \
        && rm -f {{board}}.circuit.circuit.json)
    python3 pcb/tools/trace_art.py "$out/circuit.json" "$out/art.json" "$out/art"
    "${kpy[@]}" pcb/tools/fab_finish.py "$out/{{board}}.kicad_pcb" "$out/circuit.json" "$out/art.json" 2>&1 \
        | { grep -v "^swig/python detected a memory leak" || true; }

    cat > "$pro" <<'JSON'
    {
      "board": {
        "design_settings": {
          "rules": {
            "min_text_height": 1.0,
            "min_text_thickness": 0.15,
            "min_silk_clearance": 0.15
          },
          "rule_severities": {
            "silk_over_copper": "error",
            "silk_overlap": "error",
            "silk_edge_clearance": "error",
            "text_height": "error",
            "text_thickness": "error",
            "nonmirrored_text_on_back_layer": "error"
          }
        }
      }
    }
    JSON

    "${kc[@]}" pcb drc --refill-zones --save-board --severity-all \
        --format json -o "$out/drc.json" "$out/{{board}}.kicad_pcb"
    drc=0
    python3 - "$out/drc.json" <<'PY' || drc=$?
    import json, sys, collections
    d = json.load(open(sys.argv[1]))
    v = d.get("violations", [])
    errs = [x for x in v if x.get("severity") == "error"]
    print(f"DRC: {len(v)} violations, {len(errs)} error-level, "
          f"{len(d.get('unconnected_items', []))} unconnected")
    for (t, s), n in collections.Counter((x["type"], x["severity"]) for x in v).most_common():
        print(f"   {n:5d}  {s:8s} {t}")
    if errs:
        for x in errs:
            print(f"   {x['type']}: " + " / ".join(i["description"] for i in x["items"]))
        sys.exit(2)
    PY
    [ "$drc" -eq 0 ] || [ "$drc" -eq 2 ] || exit "$drc"
    if [ "$drc" -eq 2 ]; then
        echo
        echo "!! NOT READY FOR FAB: error-level DRC violations above." >&2
        echo "!! No gerbers and no {{board}}-fab.zip were written. Fix them, then rerun." >&2
        exit 0
    fi

    "${kc[@]}" pcb export gerbers -o "$out/gerbers/" --check-zones "$out/{{board}}.kicad_pcb"
    "${kc[@]}" pcb export drill -o "$out/gerbers/" --excellon-separate-th \
        --generate-map "$out/{{board}}.kicad_pcb"
    (cd "$out/gerbers" && zip -q "../{{board}}-fab.zip" ./*)
    echo
    echo "-> $out/{{board}}-fab.zip   <- send THIS, not dist/export/{{board}}-gerbers.zip"
    echo "   $out/drc.json            (full report)"

pcb-render board="v3" side="top" quality="high": (pcb-fab board)
    #!/usr/bin/env bash
    set -euo pipefail
    unset APPDIR  # see pcb-fab
    if command -v kicad-cli >/dev/null; then
        kc=(kicad-cli)
    else
        kc=(flatpak run --command=kicad-cli org.kicad.KiCad)
    fi
    out="pcb/dist/fab/{{board}}/preview"
    mkdir -p "$out"
    "${kc[@]}" pcb render --side {{side}} --quality {{quality}} \
        --width 1600 --height 1600 --background opaque \
        -o "$out/render-{{side}}.png" "pcb/dist/fab/{{board}}/{{board}}.kicad_pcb"
    echo "-> $out/render-{{side}}.png"
    [ -f "pcb/dist/fab/{{board}}/{{board}}-fab.zip" ] \
        || echo "!! this board has DRC errors and is NOT READY FOR FAB -- see above" >&2

skills-sync:
    #!/usr/bin/env bash
    set -euo pipefail
    for d in . pcb; do
        [ -d "$d/.claude/skills" ] || continue
        mkdir -p "$d/.agents/skills"
        rsync -a --delete "$d/.claude/skills/" "$d/.agents/skills/"
        echo "-> $d/.agents/skills (mirrored from $d/.claude/skills)"
    done

skills-update:
    #!/usr/bin/env bash
    set -euo pipefail
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    git clone --depth 1 https://github.com/aklofas/kicad-happy.git "$tmp/kh"
    echo "kicad-happy $(python3 -c "import json;print(json.load(open('$tmp/kh/.claude-plugin/plugin.json'))['version'])")"
    rsync -a --delete "$tmp/kh/skills/" .claude/skills/
    just skills-sync

stubs := "10.3.0"

dev:
    #!/usr/bin/env bash
    set -euo pipefail
    command -v uv >/dev/null || { echo "needs uv: https://docs.astral.sh/uv/" >&2; exit 1; }
    uv venv --allow-existing .venv
    uv pip install --quiet --python .venv/bin/python circuitpython-stubs=={{stubs}} ruff bleak pillow
    uv pip install --quiet --python .venv/bin/python --no-deps \
        adafruit-circuitpython-st7789 \
        adafruit-circuitpython-busdevice
    .venv/bin/circuitpython_setboard {{board_id}}
    .venv/bin/python tools/dev/patch_stubs.py
    echo "-> .venv (CircuitPython {{stubs}} stubs, {{board_id}})"
    echo "   VS Code: reload, then pick .venv as the interpreter if it doesn't"

check:
    #!/usr/bin/env bash
    set -euo pipefail
    [ -x .venv/bin/ruff ] || { echo "run 'just dev' first" >&2; exit 1; }
    .venv/bin/ruff check .
    uvx pyright

fmt:
    #!/usr/bin/env bash
    set -euo pipefail
    .venv/bin/ruff format src tools pcb/tools
