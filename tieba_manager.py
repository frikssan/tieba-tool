# -*- coding: utf-8 -*-
"""
百度贴吧账号管理工具
====================

功能：
  - 查看 / 解除屏蔽的吧
  - 查看 / 解除新版拉黑用户
  - 查看 / 解除旧版黑名单用户

说明：
  仅用于个人账号管理，请勿批量高频调用，遵守贴吧社区规则。
  本工具基于开源库 aiotieba 与贴吧公开接口交互，作者不对账号风险负责。
"""

import asyncio
import json
import sys
from pathlib import Path

import aiotieba as tb
from aiotieba.enums import BlacklistType

__version__ = "1.0.0"

# ========== 配置文件 ==========
CONFIG_DIR = Path.home() / ".tieba_tool"
CONFIG_FILE = CONFIG_DIR / "config.json"


def save_config(bduss: str):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        json.dumps({"bduss": bduss}, indent=2), encoding="utf-8"
    )


def load_config() -> str | None:
    if CONFIG_FILE.exists():
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data.get("bduss")
    return None


def clear_config():
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


# ========== 通用交互 ==========
def print_header(title: str):
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print(f"{'=' * 50}")


def print_menu(options: list[str]):
    print()
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    print(f"  0. 返回/退出")


def ask_choice(max_num: int) -> int:
    while True:
        try:
            choice = input("\n请输入选项编号: ").strip()
            num = int(choice)
            if 0 <= num <= max_num:
                return num
            print(f"请输入 0-{max_num} 之间的数字")
        except ValueError:
            print("请输入数字")


async def confirm_action(msg: str) -> bool:
    ans = input(f"{msg} (y/N): ").strip().lower()
    return ans in ("y", "yes")


# ========== 屏蔽的吧 ==========
async def view_disliked_forums(client: tb.Client):
    """查看所有屏蔽的吧"""
    print_header("屏蔽的吧列表")

    all_forums = []
    pn = 1
    while True:
        result = await client.get_dislike_forums(pn, rn=20)
        all_forums.extend(result.objs)
        if not result.has_more:
            break
        pn += 1
        await asyncio.sleep(0.5)

    if not all_forums:
        print("  没有屏蔽任何贴吧")
        return all_forums

    print(f"  共屏蔽了 {len(all_forums)} 个贴吧：\n")
    for i, f in enumerate(all_forums, 1):
        print(f"  [{i}] {f.fname}  (fid: {f.fid})")

    return all_forums


async def un_dislike_forums(client: tb.Client):
    """选择性解除屏蔽的吧"""
    forums = await view_disliked_forums(client)
    if not forums:
        return

    print()
    print("  操作说明：")
    print("  - 输入编号（如 1）解除单个")
    print("  - 输入范围（如 1-5）解除连续多个")
    print("  - 输入 all 解除全部")
    print("  - 输入空格分隔多个编号（如 1 3 5）")

    selection = input("\n请选择要解除屏蔽的贴吧: ").strip()

    to_unhide = []
    if selection.lower() == "all":
        if not await confirm_action(f"确定要解除全部 {len(forums)} 个贴吧的屏蔽吗？"):
            print("已取消")
            return
        to_unhide = forums
    else:
        indices = set()
        for part in selection.split():
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    start, end = int(start), int(end)
                    indices.update(range(start, end + 1))
                except ValueError:
                    print(f"  忽略无效输入: {part}")
            else:
                try:
                    indices.add(int(part))
                except ValueError:
                    print(f"  忽略无效输入: {part}")

        for idx in sorted(indices):
            if 1 <= idx <= len(forums):
                to_unhide.append(forums[idx - 1])

        if not to_unhide:
            print("没有选择有效的贴吧")
            return

        print(f"\n  将解除以下 {len(to_unhide)} 个贴吧的屏蔽：")
        for f in to_unhide:
            print(f"    - {f.fname}")
        if not await confirm_action("确认执行？"):
            print("已取消")
            return

    print("\n正在解除屏蔽...")
    success = 0
    fail = 0
    for f in to_unhide:
        try:
            result = await client.undislike_forum(f.fid)
            if result:
                print(f"  [OK] 已解除: {f.fname}")
                success += 1
            else:
                print(f"  [失败] {f.fname}")
                fail += 1
        except Exception as e:
            print(f"  [错误] {f.fname}: {e}")
            fail += 1
        await asyncio.sleep(1)  # 每次间隔 1 秒，防止风控

    print(f"\n完成！成功 {success} 个，失败 {fail} 个")


# ========== 新版拉黑用户 ==========
async def view_blacklist_users(client: tb.Client):
    """查看新版黑名单用户"""
    print_header("新版用户黑名单")

    result = await client.get_blacklist()
    users = result.objs

    if not users:
        print("  黑名单为空")
        return users

    print(f"  共拉黑了 {len(users)} 个用户：\n")
    for i, u in enumerate(users, 1):
        name = u.show_name or u.user_name or f"uid:{u.user_id}"
        print(f"  [{i}] {name}  (uid: {u.user_id})")

    return users


async def unblock_blacklist_users(client: tb.Client):
    """选择性解除新版黑名单"""
    users = await view_blacklist_users(client)
    if not users:
        return

    print()
    print("  操作说明：")
    print("  - 输入编号（如 1）解除单个")
    print("  - 输入范围（如 1-5）解除连续多个")
    print("  - 输入 all 解除全部")
    print("  - 输入空格分隔多个编号（如 1 3 5）")

    selection = input("\n请选择要移出黑名单的用户: ").strip()

    to_unblock = []
    if selection.lower() == "all":
        if not await confirm_action(f"确定要解除全部 {len(users)} 个用户的拉黑吗？"):
            print("已取消")
            return
        to_unblock = users
    else:
        indices = set()
        for part in selection.split():
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    start, end = int(start), int(end)
                    indices.update(range(start, end + 1))
                except ValueError:
                    print(f"  忽略无效输入: {part}")
            else:
                try:
                    indices.add(int(part))
                except ValueError:
                    print(f"  忽略无效输入: {part}")

        for idx in sorted(indices):
            if 1 <= idx <= len(users):
                to_unblock.append(users[idx - 1])

        if not to_unblock:
            print("没有选择有效的用户")
            return

        print(f"\n  将解除以下 {len(to_unblock)} 个用户的拉黑：")
        for u in to_unblock:
            name = u.show_name or u.user_name or f"uid:{u.user_id}"
            print(f"    - {name}")
        if not await confirm_action("确认执行？"):
            print("已取消")
            return

    print("\n正在解除拉黑...")
    success = 0
    fail = 0
    for u in to_unblock:
        try:
            # 新版黑名单：set_blacklist 设为 NULL 即解除
            result = await client.set_blacklist(u.user_id, btype=BlacklistType.NULL)
            if result:
                name = u.show_name or u.user_name or f"uid:{u.user_id}"
                print(f"  [OK] 已解除: {name}")
                success += 1
            else:
                print(f"  [失败] uid:{u.user_id}")
                fail += 1
        except Exception as e:
            print(f"  [错误] uid:{u.user_id}: {e}")
            fail += 1
        await asyncio.sleep(1)

    print(f"\n完成！成功 {success} 个，失败 {fail} 个")


# ========== 旧版黑名单 ==========
async def view_old_blacklist(client: tb.Client):
    """查看旧版黑名单用户"""
    print_header("旧版用户黑名单")

    all_users = []
    pn = 1
    while True:
        result = await client.get_blacklist_old(pn, rn=100)
        all_users.extend(result.objs)
        if not result.has_more:
            break
        pn += 1
        await asyncio.sleep(0.5)

    if not all_users:
        print("  旧版黑名单为空")
        return all_users

    print(f"  共 {len(all_users)} 个用户：\n")
    for i, u in enumerate(all_users, 1):
        name = getattr(u, "show_name", "") or getattr(u, "user_name", "") or f"uid:{u.user_id}"
        print(f"  [{i}] {name}  (uid: {u.user_id})")

    return all_users


async def unblock_old_blacklist(client: tb.Client):
    """选择性解除旧版黑名单"""
    users = await view_old_blacklist(client)
    if not users:
        return

    print()
    selection = input("请选择要移出旧版黑名单的用户（编号/all）: ").strip()

    to_unblock = []
    if selection.lower() == "all":
        if not await confirm_action(f"确定要解除全部 {len(users)} 个用户的旧版黑名单吗？"):
            print("已取消")
            return
        to_unblock = users
    else:
        indices = set()
        for part in selection.split():
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    indices.update(range(int(start), int(end) + 1))
                except ValueError:
                    pass
            else:
                try:
                    indices.add(int(part))
                except ValueError:
                    pass

        for idx in sorted(indices):
            if 1 <= idx <= len(users):
                to_unblock.append(users[idx - 1])

        if not to_unblock:
            print("没有选择有效的用户")
            return

    if not await confirm_action(f"确认解除 {len(to_unblock)} 个用户的旧版黑名单？"):
        print("已取消")
        return

    print("\n正在解除...")
    success = 0
    fail = 0
    for u in to_unblock:
        try:
            result = await client.del_blacklist_old(u.user_id)
            if result:
                name = getattr(u, "show_name", "") or getattr(u, "user_name", "") or f"uid:{u.user_id}"
                print(f"  [OK] 已解除: {name}")
                success += 1
            else:
                fail += 1
        except Exception as e:
            print(f"  [错误] uid:{u.user_id}: {e}")
            fail += 1
        await asyncio.sleep(1)

    print(f"\n完成！成功 {success} 个，失败 {fail} 个")


# ========== 登录流程 ==========
def input_bduss() -> str:
    print_header("首次使用 - 登录")
    print("  请输入你的贴吧 BDUSS（Cookie 中的 BDUSS 值）")
    print("  获取方法：浏览器登录贴吧 → F12 → 应用程序 → Cookies → 找 BDUSS")
    print()
    bduss = input("  BDUSS: ").strip()
    if not bduss:
        print("BDUSS 不能为空")
        sys.exit(1)
    save_config(bduss)
    print("  已保存到本地配置\n")
    return bduss


async def get_client() -> tb.Client:
    """获取已登录的 Client"""
    bduss = load_config()
    if not bduss:
        bduss = input_bduss()
    return tb.Client(bduss)


# ========== 主菜单 ==========
async def main():
    print("=" * 50)
    print("  百度贴吧账号管理工具")
    print("  功能：解除屏蔽的吧 / 解除拉黑的用户")
    print(f"  版本：v{__version__}")
    print("=" * 50)

    try:
        client = await get_client()
    except Exception as e:
        print(f"登录失败：{e}")
        print("可在主菜单选择“重新登录”更换 BDUSS。")
        clear_config()
        return

    try:
        while True:
            print_header("主菜单")
            print_menu([
                "查看屏蔽的吧",
                "解除屏蔽的吧",
                "查看拉黑的用户（新版）",
                "解除拉黑的用户（新版）",
                "查看旧版黑名单用户",
                "解除旧版黑名单",
                "重新登录（清除已保存的 BDUSS）",
            ])

            choice = ask_choice(7)

            if choice == 0:
                print("\n再见！")
                break
            elif choice == 1:
                await view_disliked_forums(client)
            elif choice == 2:
                await un_dislike_forums(client)
            elif choice == 3:
                await view_blacklist_users(client)
            elif choice == 4:
                await unblock_blacklist_users(client)
            elif choice == 5:
                await view_old_blacklist(client)
            elif choice == 6:
                await unblock_old_blacklist(client)
            elif choice == 7:
                clear_config()
                print("\n已清除本地 BDUSS，下次启动将重新登录")
                client = await get_client()

            input("\n按回车键继续...")

    except KeyboardInterrupt:
        print("\n\n已退出。")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
