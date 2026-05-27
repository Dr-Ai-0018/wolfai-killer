#!/usr/bin/env python3
"""
Run one official preset live game with a single human seat and only use god-mode after the game ends.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import backend.scripts.run_batch_reviews as batch


DEFAULT_PRESET_ID = os.getenv("WEREWOLF_LIVE_PRESET_ID", "lovers_7p")
GOD_PASSWORD = os.getenv("WEREWOLF_GOD_PASSWORD", "gm-official-preset-review")
REPORT_ROOT = ROOT / "data" / "reports" / f"official_preset_live_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def fetch_json(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, f"{batch.BASE_URL}{path}", **kwargs)
    response.raise_for_status()
    return response.json()


def build_live_report(
    preset: dict[str, Any],
    game_id: str,
    human_seat: int,
    result: dict[str, Any],
    public_logs: list[dict[str, Any]],
    phantom_payload: dict[str, Any],
    report_dir: Path,
) -> Path:
    human_role = result["human_role"]
    human_camp = result["human_camp"]
    winner = result["winner"]
    timeline = batch.extract_timeline(public_logs)
    phantom_total = int(phantom_payload.get("total") or 0)

    lines = [
        "# 官方板子实战报告",
        "",
        f"- 时间：{datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"- 预设板子：{preset['name']} (`{preset['id']}`)",
        f"- 板子说明：{preset['description']}",
        f"- 对局 ID：`{game_id}`",
        f"- 真人席位：{human_seat}号",
        f"- 真人身份：{human_role} / {human_camp}",
        f"- 对局结果：{winner}",
        f"- 冥界复盘条目：{phantom_total}",
        "",
        "## 权限边界",
        "",
        "- 对局进行中仅调用普通玩家相关接口：`/api/game/create`、`/api/game/{id}/start`、`/api/game/{id}/status`、`/api/game/{id}/player/{seat}`、`/api/game/{id}/log`、`/api/game/{id}/action`、`/api/stats/game/{id}`。",
        "- 上帝接口 `god-mode/logs` 与赛后 `phantom-actions` 只在确认 `phase=ended` 后调用。",
        "- 对局中未读取 `god-mode/players`，未在游戏结束前读取隐藏日志。",
        "",
        "## 对局时间线",
        "",
        *[f"- {item}" for item in timeline],
        "",
        "## 赛后观察",
        "",
        f"- 这局实战样本来自预设板子 `{preset['id']}`，说明预设加载、开局、主循环、结算和统计链路已在真实 API 调用下贯通。",
        f"- 我在普通玩家席位打到自然结束后才进入复盘，赛后可见的冥界行动共有 {phantom_total} 条。",
        "- 是否平衡仍要看这局具体过程和后续样本，但这一轮 goal 的重点是验证板子机制和完整对局闭环，而不是继续外扩玩法。",
        "",
    ]

    report_path = report_dir / f"{preset['id']}_{game_id}.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def run_live_game(client: httpx.Client, preset_id: str, report_dir: Path) -> dict[str, Any]:
    catalog = fetch_json(client, "GET", "/api/config/presets")
    preset = next((item for item in catalog if item.get("id") == preset_id), None)
    if not preset:
        raise RuntimeError(f"预设板子不存在：{preset_id}")

    human_seat = 1
    memory: dict[str, Any] = {}
    payload = {
        "preset_id": preset_id,
        "human_seats": [human_seat],
        "random_models": False,
        "seat_model_map": batch.build_seat_model_map(int(preset["total_players"]), 0),
        "god_mode": {"enabled": True, "password": GOD_PASSWORD},
    }

    created = fetch_json(client, "POST", "/api/game/create", json=payload)
    game_id = created["game_id"]
    fetch_json(client, "POST", f"/api/game/{game_id}/start")

    started_at = time.time()
    public_logs: list[dict[str, Any]] = []
    while True:
      if time.time() - started_at > batch.SCENARIO_TIMEOUT_SECONDS:
          raise TimeoutError(f"官方板子实战超时：{preset_id} / {game_id}")

      status = fetch_json(client, "GET", f"/api/game/{game_id}/status")
      if status.get("phase") == "ended":
          break

      if int(status.get("waiting_for_human") or 0) == human_seat:
          private_view = fetch_json(client, "GET", f"/api/game/{game_id}/player/{human_seat}")
          public_payload = fetch_json(client, "GET", f"/api/game/{game_id}/log?limit=500")
          public_logs = list(public_payload.get("logs") or [])
          action = batch.infer_human_action(
              str(status.get("human_action_type")),
              private_view,
              public_logs,
              status,
              memory,
          )
          fetch_json(
              client,
              "POST",
              f"/api/game/{game_id}/action",
              json={"action_type": status.get("human_action_type"), "data": action},
          )
          time.sleep(0.2)
          continue

      time.sleep(1.0)

    game_detail = fetch_json(client, "GET", f"/api/stats/game/{game_id}")
    public_logs = list(game_detail.get("public_logs") or game_detail.get("logs") or [])
    god_logs = fetch_json(client, "GET", f"/api/game/{game_id}/god-mode/logs?password={GOD_PASSWORD}&limit=2000")
    phantom_payload = fetch_json(client, "GET", f"/api/game/{game_id}/phantom-actions")

    result = batch.review_game(
        scenario={
            "name": preset_id,
            "total_players": int(preset["total_players"]),
            "num_wolves": int(preset["num_wolves"]),
            "role_config": dict(preset.get("role_config") or {}),
        },
        game_id=game_id,
        players=game_detail["players"],
        public_logs=public_logs,
        private_logs=god_logs.get("logs") or [],
        human_seat=human_seat,
        report_dir=report_dir,
    )
    report_path = build_live_report(preset, game_id, human_seat, result, public_logs, phantom_payload, report_dir)
    result.update(
        {
            "preset_id": preset_id,
            "report_path": str(report_path),
            "phantom_total": int(phantom_payload.get("total") or 0),
        }
    )
    return result


def main() -> int:
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    process = None
    client = None
    try:
        process, client = batch.ensure_server()
        result = run_live_game(client, DEFAULT_PRESET_ID, REPORT_ROOT)
        print(json.dumps(result, ensure_ascii=False))
        print(f"报告已写入：{result['report_path']}")
        return 0
    finally:
        if client is not None:
            client.close()
        batch.stop_server(process)


if __name__ == "__main__":
    raise SystemExit(main())
