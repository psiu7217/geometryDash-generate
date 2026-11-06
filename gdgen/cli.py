"""Command line interface: generate / edit / preview / import / inspect."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from . import __version__
from .gdlvl import load_gdlvl, save_gdlvl
from .generator import BASE_SPEED, generate, spec_from_preset
from .level import Level
from .preview import render_preview
from .route import annotate_sections, estimate_route
from .savefile import DEFAULT_SAVE, SaveFileError, add_level, is_game_running, list_levels
from .spec import LevelSpec, describe, parse_prompt
from .validate import validate


TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(name: str) -> str:
    lowered = "".join(TRANSLIT.get(ch, ch) for ch in name.lower())
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    return slug or "level"


def _sidecar(path: pathlib.Path) -> pathlib.Path:
    return path.with_suffix(".json")


def _write_sidecar(path: pathlib.Path, spec: LevelSpec, level: Level,
                   metadata: dict | None = None) -> None:
    data = json.loads(spec.to_json())
    data["_generator"] = {
        "version": __version__,
        "objects": len(level.objects),
        "blocks": level.length_units / 30.0,
        "duration_estimate": round(level.duration_seconds or level.length_units / BASE_SPEED, 2),
        "metadata": metadata or {},
    }
    _sidecar(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_sidecar(path: pathlib.Path) -> tuple[LevelSpec, dict]:
    side = _sidecar(path)
    if not side.exists():
        raise SystemExit(
            f"Нет файла спецификации {side.name}. Правка промптом поддерживается для "
            "уровней, созданных этим генератором (рядом должен лежать .json)."
        )
    data = json.loads(side.read_text(encoding="utf-8"))
    generator = data.pop("_generator", {})
    spec = LevelSpec.from_json(json.dumps(data))
    return spec, generator.get("metadata", {})


def _report(level: Level, result) -> None:
    stats = level.stats()
    print(f"Уровень: {level.name}")
    print(f"  объектов: {stats['objects']}  блоков: {stats['blocks']}  "
          f"шипов: {stats['hazards']}  порталов: {stats['portals']}")
    print(f"  длина: {level.length_units:.0f} units ({level.length_units / 30:.0f} блоков)")
    duration = level.duration_seconds or level.length_units / BASE_SPEED
    print(f"  оценка длительности: {duration:.1f} c")
    print(result.summary())


def cmd_generate(args) -> int:
    if args.preset:
        spec = spec_from_preset(args.preset)
        metadata = {"preset": args.preset, "edits": []}
    elif args.prompt:
        spec = parse_prompt(args.prompt)
        if spec.name == LevelSpec.name:
            spec.name = f"AI {spec.theme.title()} Run"
        metadata = {"prompt": args.prompt, "edits": []}
    else:
        print("Укажите --prompt или --preset.", file=sys.stderr)
        return 2

    if args.name:
        spec.name = args.name
    if args.duration:
        spec.duration = max(10.0, min(180.0, args.duration))
    if args.theme:
        spec.theme = args.theme
    if args.seed is not None:
        spec.seed = args.seed
    if args.bpm is not None:
        spec.bpm = max(40, min(300, args.bpm))

    level = generate(spec)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slugify(spec.name)}.gdlvl"
    if not args.preview_only:
        save_gdlvl(path, level)
        _write_sidecar(path, spec, level, metadata)

    preview_path = None
    detail_path = None
    if not args.no_preview or args.preview_only:
        preview_path = render_preview(level, out_dir / "preview" / f"{slugify(spec.name)}.png")
        detail_path = render_preview(
            level, out_dir / "preview" / f"{slugify(spec.name)}_detail.png",
            width_per_block=14, height_per_block=18, window_blocks=90,
        )

    result = validate(level)
    _report(level, result)
    print(f"  спецификация: {describe(spec)}")
    if args.preview_only:
        print("  РЕЖИМ ПРЕДПРОСМОТРА: .gdlvl и JSON не создавались.")
    else:
        print(f"  .gdlvl: {path}")
    if preview_path:
        print(f"  предпросмотр: {preview_path}")
    if detail_path:
        print(f"  детальный фрагмент: {detail_path}")
    if not result.ok:
        return 1
    print("  ВАЖНО: проходимость не проверена реальным прохождением.")
    return 0


def cmd_edit(args) -> int:
    path = pathlib.Path(args.input)
    spec, metadata = _load_sidecar(path)
    old = spec.clone()
    spec = parse_prompt(args.prompt, base=spec)
    if args.name:
        spec.name = args.name
    if args.seed is not None:
        spec.seed = args.seed

    level = generate(spec)
    target = pathlib.Path(args.out) if args.out else path
    save_gdlvl(target, level)
    # Preserve the source sidecar when --out writes an edited copy.
    metadata.setdefault("edits", []).append(args.prompt)
    _write_sidecar(target, spec, level, metadata)

    preview_path = None
    if not args.no_preview:
        preview_path = render_preview(level, target.parent / "preview" / f"{slugify(spec.name)}.png")

    result = validate(level)
    print(f"Было:  {describe(old)}")
    print(f"Стало: {describe(spec)}")
    _report(level, result)
    print(f"  .gdlvl: {target}")
    if preview_path:
        print(f"  предпросмотр: {preview_path}")
    return 0 if result.ok else 1


def cmd_preview(args) -> int:
    level = load_gdlvl(args.input)
    if not level.route:
        level.route = estimate_route(level)
        annotate_sections(level)
    out = pathlib.Path(args.out) if args.out else pathlib.Path(args.input).with_suffix(".png")
    render_preview(
        level, out, args.width_per_block, args.height_per_block,
        start_x=args.start_block * 30.0, window_blocks=args.blocks,
    )
    print(f"PNG: {out}  ({level.length_units / 30:.0f} блоков)")
    return 0


def cmd_import(args) -> int:
    level = load_gdlvl(args.input)
    save_path = pathlib.Path(args.save) if args.save else None
    if is_game_running():
        print("Geometry Dash запущена. Закройте игру и повторите импорт.", file=sys.stderr)
        return 3
    try:
        used, backup = add_level(level, save_path)
    except SaveFileError as exc:
        print(f"Импорт отменён: {exc}", file=sys.stderr)
        return 2
    print(f"Добавлено «{level.name}» в {used}")
    print(f"Резервная копия: {backup}")
    print("Запустите игру и откройте уровень в редакторе.")
    return 0


def cmd_list(args) -> int:
    path = pathlib.Path(args.save) if args.save else DEFAULT_SAVE
    try:
        names = list_levels(path)
    except SaveFileError as exc:
        print(exc, file=sys.stderr)
        return 2
    if not names:
        print("В сохранении нет локальных уровней.")
    for name in names:
        print(f"- {name}")
    return 0


def cmd_inspect(args) -> int:
    level = load_gdlvl(args.input)
    if not level.sections:
        annotate_sections(level)
    if not level.route:
        level.route = estimate_route(level)
    result = validate(level)
    _report(level, result)
    if level.sections:
        for section in level.sections:
            print(f"  {section['mode']:>6}: {section['start']:.0f} .. {section['end']:.0f}")
    return 0 if result.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gdgen",
        description="Geometry Dash AI level generator (prompt -> .gdlvl + preview).",
    )
    parser.add_argument("--version", action="version", version=f"gdgen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="сгенерировать уровень по промпту или пресету")
    gen.add_argument("--prompt", "-p", help="текстовое описание уровня")
    gen.add_argument("--preset", choices=["ai-neon-run", "neon-cyber-city"], help="готовый пресет")
    gen.add_argument("--out", default="levels", help="папка для результата")
    gen.add_argument("--name", help="переопределить имя уровня")
    gen.add_argument("--duration", type=float, help="длительность в секундах")
    gen.add_argument("--theme", help="neon/space/lava/ice/cyber/forest/sunset")
    gen.add_argument("--seed", type=int, help="seed генератора")
    gen.add_argument("--bpm", type=int, help="BPM для декоративных ритмических акцентов")
    gen.add_argument("--preview-only", action="store_true", help="PNG без записи .gdlvl или JSON")
    gen.add_argument("--no-preview", action="store_true", help="не рисовать PNG")
    gen.set_defaults(func=cmd_generate)

    edit = sub.add_parser("edit", help="изменить сгенерированный уровень промптом")
    edit.add_argument("input", help="существующий .gdlvl")
    edit.add_argument("--prompt", "-p", required=True, help="что изменить")
    edit.add_argument("--out", help="новый файл (по умолчанию перезаписать)")
    edit.add_argument("--name", help="новое имя уровня")
    edit.add_argument("--seed", type=int)
    edit.add_argument("--no-preview", action="store_true")
    edit.set_defaults(func=cmd_edit)

    prev = sub.add_parser("preview", help="нарисовать PNG из .gdlvl")
    prev.add_argument("input", help=".gdlvl")
    prev.add_argument("--out", "-o", help="куда сохранить PNG")
    prev.add_argument("--width-per-block", type=int, default=8)
    prev.add_argument("--height-per-block", type=int, default=12)
    prev.add_argument("--start-block", type=float, default=0,
                      help="начальный блок увеличенного фрагмента")
    prev.add_argument("--blocks", type=int, help="длина фрагмента в блоках")
    prev.set_defaults(func=cmd_preview)

    imp = sub.add_parser("import", help="добавить .gdlvl в CCLocalLevels.dat")
    imp.add_argument("input", help=".gdlvl")
    imp.add_argument("--save", help="путь к CCLocalLevels.dat")
    imp.set_defaults(func=cmd_import)

    lst = sub.add_parser("list", help="список локальных уровней в сохранении")
    lst.add_argument("--save", help="путь к CCLocalLevels.dat")
    lst.set_defaults(func=cmd_list)

    ins = sub.add_parser("inspect", help="статистика и проверки .gdlvl")
    ins.add_argument("input", help=".gdlvl")
    ins.set_defaults(func=cmd_inspect)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, OSError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
