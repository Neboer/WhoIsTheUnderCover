from api import RocketClient, RocketUserInfo
from game import Game
from lib import GameControl, Player, GameStatus
from settings import config
from re import match
from csv import reader
from threading import Thread
from json import JSONDecodeError
from logging import info, error, exception

recruit_str = r"/创建游戏 (.*)"
apply_str = r"/加入游戏 (.*)"
cancel_str = r"/取消游戏 (.*)"
quit_str = r"/退出游戏 (.*)"
fire_str = r"/开始游戏 (.*)"
list_str = r"/所有游戏"


def check_valid_game_name(name: str):
    # noinspection PyNoneFunctionAssignment
    return len(name) < 10 and match(r'^[\u4e00-\u9fffA-Za-z0-9]+$', name)


games: dict[str, Game] = {}  # 游戏id对应玩家id。
rocket_client = RocketClient()


def send_public_message(message):
    return rocket_client.send_message(config['channel_id'], message)


next_game_id = 0


# 表示玩家是否已经加入了一场没有结束的游戏？
def check_user_in_unfinished_games(user_id: str) -> bool:
    for game in (unfinished_game_name for unfinished_game_name in games if
                 games[unfinished_game_name].status != GameStatus.finished):
        if user_id in (player.api_player_info['_id'] for player in games[game].player_list):
            return True
    else:
        return False


def handle_create_game(init_user: RocketUserInfo, game_name: str):
    global next_game_id
    if check_valid_game_name(game_name):
        # 游戏名是否已经创建？
        if game_name in games:
            send_public_message("此游戏名已被使用。")
            return
        # 玩家是否已经在游戏中了？
        if check_user_in_unfinished_games(init_user['_id']):
            send_public_message("你已经加入一局游戏了。")
            return
        else:
            # 玩家没有加入任何游戏，准备创建一个新游戏。
            # 创建游戏之前，需要创建一个新的私有群。
            group_id = rocket_client.create_room(game_name, init_user['username'])
            if not group_id:
                send_public_message("创建游戏失败。")
                return
            else:
                with open("words.csv", "r", encoding='utf8') as word_list_file:  # 每次创建新游戏的时候，都更新一下word_list。
                    word_list = list(reader(word_list_file))
                current_game = Game(Player(init_user, rocket_client.get_room(init_user['username']))
                                    , word_list, next_game_id, GameControl(rocket_client, group_id))
                next_game_id += 1
                games[game_name] = current_game
    else:
        send_public_message("游戏名只能包含中英文和数字。")


def handle_apply_game(user: RocketUserInfo, game_name: str):
    # 玩家想要加入游戏
    if game_name in games:
        if games[game_name].status != GameStatus.preparing:
            send_public_message("游戏已经开始或结束。")
            return
        elif check_user_in_unfinished_games(user['_id']):
            send_public_message("你已经加入一局游戏了。")
            return
        else:
            games[game_name].add_player(Player(user, rocket_client.get_room(user['username'])))
            rocket_client.add_user_to_room(games[game_name].control.group_id, user['_id'])
    else:
        send_public_message("游戏名不存在。")


# 玩家删除一个游戏。
def handle_delete_game(user: RocketUserInfo, game_name: str):
    if game_name in games:
        if user['_id'] == games[game_name].creator.api_player_info['_id']:
            if games[game_name].status != GameStatus.started:  # 只要不是已经开始的游戏，都可以删除。
                game = games.pop(game_name)
                rocket_client.dismiss_group(game.control.group_id)
            else:
                send_public_message("游戏已经开始，不能取消。")
        else:
            send_public_message("你不是游戏的创建者，不能取消。")
    else:
        send_public_message("游戏名不存在。")


def handle_game_start(user: RocketUserInfo, game_name: str):
    if game_name in games:
        if user['_id'] == games[game_name].creator.api_player_info['_id']:
            if games[game_name].status == GameStatus.preparing:
                if len(games[game_name].player_list) >= games[game_name].minimal_players:
                    def start_game():
                        games[game_name].start()
                        # 游戏结束之后，不立即解散房间，需要房主手动取消房间。
                        # rocket_client.dismiss_group(games[game_name].control.group_id)
                        # games.pop(game_name)
                        send_public_message(f"游戏“{game_name}”已结束。")

                    Thread(target=start_game).start()
                else:
                    send_public_message("游戏人数不足，无法开始。")
            else:
                send_public_message("游戏已经开始或结束。")
        else:
            send_public_message("你不是游戏的创建者，不能开始。")
    else:
        send_public_message("游戏名不存在。")


# 普通玩家想要退出一场准备中的游戏。
def handle_quite_game(user: RocketUserInfo):
    # 搜索玩家。
    for game_name in (name for name in games if games[name].status == GameStatus.preparing):
        if user['_id'] in (player.api_player_info['_id'] for player in games[game_name].player_list):  # 如果用户就在此游戏中
            if user['_id'] != games[game_name].creator.api_player_info['_id']:
                rocket_client.remove_user_from_room(games[game_name].control.group_id, user['_id'])
                games[game_name].player_list.pop([player.api_player_info['_id'] for player in games[game_name].player_list].index(user['_id']))
                send_public_message(f"玩家已经退出游戏{game_name}")
                return
            else:
                send_public_message("你是游戏的创建者，不能退出游戏。")
                return
    # 找不到玩家。
    send_public_message("你没有加入任何准备中的游戏。")


# 玩家想要取消一个还没有开始的游戏。已经开始的游戏不能够被取消。只有游戏的创建者才能够取消对应的游戏！


while True:
    main_group_message = None
    while not main_group_message:
        try:
            main_group_message = rocket_client.get_next_message(config['channel_id'])
        except JSONDecodeError as e:
            exception(e)
    if main_group_message[1].startswith("/"):
        # 可能是命令，谨慎对待！
        rec = match(recruit_str, main_group_message[1])
        user_info = main_group_message[0]
        if rec:  # 玩家想要创建游戏。
            handle_create_game(user_info, rec.group(1))
        app = match(apply_str, main_group_message[1])
        if app:  # 玩家想要加入游戏。
            handle_apply_game(user_info, app.group(1))
        can = match(cancel_str, main_group_message[1])
        if can:  # 玩家试图取消游戏
            handle_delete_game(user_info, can.group(1))
        fir = match(fire_str, main_group_message[1])
        if fir:  # 玩家要开始游戏！
            handle_game_start(user_info, fir.group(1))
        lst = match(list_str, main_group_message[1])
        if lst:
            if len(games) > 0:
                send_public_message(
                    '\n'.join(k + f' 创建者：{games[k].creator.api_player_info["username"]} 状态：{games[k].status}' for k in games.keys()))
            else:
                send_public_message('还没有游戏。')
