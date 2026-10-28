"""The `cv-builder` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, checks, config, gate, overlay


def load_facts(cfg: config.Config) -> list[dict] | None:
    if not cfg.facts_path.exists():
        return None
    data = overlay.load_yaml(cfg.facts_path) or {}
    return [dict(f) for f in (data.get("facts") or []) if isinstance(f, dict)]


def variants_or_fail(cfg: config.Config, wanted: list[str]) -> list[Path]:
    overlays = cfg.overlays()
    if wanted:
        overlays = [o for o in overlays if o.stem in wanted]
    if not overlays:
        raise SystemExit(f"no overlay{' matching ' + str(wanted) if wanted else ''} in "
                         f"{cfg.variants}/: add one, for example variants/general.yaml")
    return overlays


def print_issues(issues: list[checks.Issue]) -> int:
    for issue in issues:
        print(f"  {issue}")
    return sum(1 for i in issues if i.level == "error")


def cmd_check(args) -> int:
    cfg = config.load(Path(args.dir))
    if not cfg.master_path.exists():
        print(f"no master at {cfg.master_path}: run `cv-builder init` first")
        return 1
    facts = load_facts(cfg)
    errors = 0
    master = overlay.load_yaml(cfg.master_path)
    print(f"{cfg.master}:")
    errors += print_issues(checks.run_all(master, banned=cfg.banned, facts=facts,
                                          market=cfg.market, skills=cfg.skills_section))
    for path in variants_or_fail(cfg, args.variant):
        v = overlay.build_variant(cfg.master_path, path, cfg.skills_section)
        print(f"{cfg.variants}/{path.name}:")
        issues = [checks.Issue("error", path.name, e) for e in v.errors]
        issues += [checks.Issue("warning", path.name, w) for w in v.warnings]
        issues += checks.run_all(v.data, banned=cfg.banned, facts=facts, market=cfg.market,
                                 skills=cfg.skills_section)
        errors += print_issues(issues)
    print("CHECK FAILED" if errors else "CHECK PASSED", f"({errors} error(s))" if errors else "")
    return 1 if errors else 0


def cmd_build(args) -> int:
    from . import render

    cfg = config.load(Path(args.dir))
    facts = load_facts(cfg)
    failed = False
    for path in variants_or_fail(cfg, args.variant):
        v = overlay.build_variant(cfg.master_path, path, cfg.skills_section)
        issues = [checks.Issue("error", path.name, e) for e in v.errors]
        issues += [checks.Issue("warning", path.name, w) for w in v.warnings]
        issues += checks.run_all(v.data, banned=cfg.banned, facts=facts, market=cfg.market,
                                 skills=cfg.skills_section)
        if print_issues(issues):
            print(f"  {v.name}: CHECK FAILED, not rendered")
            failed = True
            continue
        merged_path = cfg.build_path / f"cv-{v.name}.yaml"
        v.dump(merged_path, cfg.master, path.name)
        try:
            pdf = render.render(merged_path, cfg.build_path / v.name, cfg.send_name,
                                cfg.root / ".tmp" / "render" / v.name)
        except render.RenderError as exc:
            print(f"  {v.name}: RENDER FAILED\n{exc}")
            failed = True
            continue
        result = gate.run_gate(pdf, v.data.get("cv"), extractors=cfg.extractors or None,
                               banned=cfg.banned, min_contrast=cfg.min_contrast)
        verdict = "GATE PASSED" if result.passed else "GATE FAILED"
        print(f"  {v.name:<16} {result.pages} page(s)  {verdict}")
        if not result.passed or args.verbose:
            print("\n".join("      " + line for line in result.report().splitlines()))
        if result.pages != cfg.pages:
            print(f"      ^ expected {cfg.pages} page(s); cut bullets with _omit or tighten text")
            failed = True
        failed |= not result.passed
    if not failed:
        print(f"  send: {cfg.build_dir}/<variant>/{cfg.send_name}")
    return 1 if failed else 0


def cmd_gate(args) -> int:
    cfg = config.load(Path(args.dir))
    cv = None
    if args.source:
        cv = (overlay.load_yaml(Path(args.source)) or {}).get("cv")
    result = gate.run_gate(Path(args.pdf), cv, extractors=cfg.extractors or None,
                           banned=cfg.banned, min_contrast=cfg.min_contrast)
    print(result.report())
    return 0 if result.passed else 1


def cmd_package(args) -> int:
    from .package import package

    ok, messages = package(config.load(Path(args.dir)))
    print("\n".join(messages))
    return 0 if ok else 1


def cmd_ingest(args) -> int:
    from .ingest import ingest

    status = 0
    for name in args.files:
        path = Path(name)
        try:
            kind, content = ingest(path)
        except (OSError, ValueError, KeyError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            status = 1
            continue
        if args.out:
            out = Path(args.out) / f"{path.stem}.{'json' if kind == 'json' else 'txt'}"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(content, encoding="utf-8")
            print(f"{path} -> {out}")
        else:
            print(content)
    return status


def cmd_compare(args) -> int:
    from .compare import compare_roles
    from .ingest import linkedin_export

    cfg = config.load(Path(args.dir))
    cv = (overlay.load_yaml(cfg.master_path) or {}).get("cv") or {}
    rows = compare_roles(cv, linkedin_export(Path(args.linkedin)))
    width = max((len(r.company) for r in rows), default=10)
    for r in rows:
        print(f"  {r.status:<17} {r.company:<{width}}  {r.detail}")
    bad = sum(r.status != "match" for r in rows)
    print(f"{len(rows) - bad} of {len(rows)} role(s) match" + (f"; {bad} to fix" if bad else ""))
    return 1 if bad else 0


def cmd_init(args) -> int:
    from .scaffold import init

    return init(Path(args.target or args.dir), sample=args.sample, force=args.force)


def cmd_doctor(args) -> int:
    from .doctor import doctor

    return doctor(Path(args.dir))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cv-builder", description=(
        "Build a CV from one master YAML file and a small overlay per target role, and gate "
        "every PDF the way applicant tracking systems read it."))
    parser.add_argument("--version", action="version", version=f"cv-builder {__version__}")
    parser.add_argument("-C", "--dir", default=".", help="the CV repository (default: here)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="create a CV repository in a new folder (default: here)")
    p.add_argument("target", nargs="?", help="the folder to create")
    p.add_argument("--sample", action="store_true", help="start from the made-up sample CV")
    p.add_argument("--force", action="store_true", help="write into a folder that has files")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("check", help="dates, claims and privacy, without rendering")
    p.add_argument("variant", nargs="*", help="only these variants")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("build", help="check, render and gate every variant")
    p.add_argument("variant", nargs="*", help="only these variants")
    p.add_argument("-v", "--verbose", action="store_true", help="print the full gate report")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("gate", help="gate one PDF")
    p.add_argument("pdf")
    p.add_argument("source", nargs="?", help="the merged YAML it was rendered from")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("package", help="zip the build folder with checksums for a release")
    p.set_defaults(func=cmd_package)

    p = sub.add_parser("doctor", help="check the toolchain")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("ingest", help="text or data out of an existing CV, a LinkedIn data "
                                      "export or a JSON Resume")
    p.add_argument("files", nargs="+")
    p.add_argument("--out", help="write one file per input into this folder (default: print)")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("compare", help="the CV's roles against a LinkedIn data export")
    p.add_argument("--linkedin", required=True, help="the export ZIP, or its unpacked folder")
    p.set_defaults(func=cmd_compare)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
