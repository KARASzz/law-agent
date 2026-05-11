# -*- coding: utf-8 -*-
"""
兼容入口：把旧的清洗命令转发到系统内画像批处理管线。

保留这个文件是为了让手动调用 `clean_to_json.py` 的习惯仍然可用；
核心实现已迁入 law_agent.profile_pipeline，避免清洗逻辑分叉。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from law_agent.profile_pipeline import (  # noqa: E402
    clean_profile_workbook,
    load_pipeline_config,
    parse_bool,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="律师客户画像采集表清洗为 JSON")
    parser.add_argument("--input", required=True, help="输入 Excel 文件路径，例如 input\\本周采集表.xlsx")
    parser.add_argument("--output-dir", default="output", help="输出文件夹，默认 output")
    parser.add_argument("--config", default="config.json", help="配置文件，默认 config.json")
    parser.add_argument("--sheet", default="", help="可选：指定工作表名，不填则自动识别")
    parser.add_argument("--use-model", default="false", help="是否启用模型占位逻辑：true/false，默认 false")
    args = parser.parse_args()

    config = load_pipeline_config(Path(args.config) if args.config else None)
    use_model = parse_bool(args.use_model) or bool(config.get("model", {}).get("use_model", False))
    output_path = clean_profile_workbook(
        input_path=Path(args.input),
        output_dir=Path(args.output_dir),
        config=config,
        requested_sheet=args.sheet.strip() or None,
        use_model=use_model,
    )

    print(f"[OK] 已生成：{output_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        raise SystemExit(1)
