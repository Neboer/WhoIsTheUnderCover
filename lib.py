from enum import Enum
from time import sleep
from typing import Union
from settings import config

from api import RocketClient, RocketUserInfo


class Identity(Enum):
    spy = 1
    innocent = 0


class GamePlayerInfo:
    def __init__(self, identity, keyword):
        self.identity = identity
        self.keyword = keyword
        self.vote_count = 0


class Player:
    def __init__(self, user_info: RocketUserInfo, room_id: str):
        self.api_player_info = user_info
        self.game_player_info: Union[GamePlayerInfo, None] = None
        self.room = room_id
        self.id = 0

    def __eq__(self, other):
        return self.id == other.id

    def __str__(self):
        if self.id > 0:
            return self.api_player_info['username'] + f' ({self.id}号)'
        else:
            return self.api_player_info['username']


class GameStatus(Enum):
    preparing = "准备中"
    started = "已开始"
    finished = "已结束"

    def __str__(self):
        return self.value


# 将RocketClient包装成一个可以被game使用的object
class GameControl:
    def __init__(self, client: RocketClient, group_id: str):
        self.client = client
        self.group_id = group_id

    def send_private_message(self, target_player: Player, message: str):
        self.client.send_message(target_player.room, message)

    def send_public_message(self, message: str):
        self.client.send_message(self.group_id, message)

    # 等待指定用户发言，返回用户的发言内容（特定群组）。这里阻塞是没有关系的。注意GameControl一定要用在群组里。
    def wait_for_player(self, target_player: Player) -> str:
        user_message = None
        while not user_message or user_message[0]['_id'] != target_player.api_player_info['_id']:
            user_message = self.client.get_next_message(self.group_id, "groups")
            sleep(config['interval_sec'])
        return user_message[1]
