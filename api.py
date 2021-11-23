from typing import Union, TypedDict

from requests import sessions
from rocketchat_API.rocketchat import RocketChat
from settings import config
from datetime import datetime


class RocketUserInfo(TypedDict):
    _id: str
    name: str
    username: str


class LastUpdateInfo(TypedDict):
    messages: list  # 这些消息，id最小的一定是最新的。
    last_message_id: str # 上次返回的消息的id。


class RocketClient:
    def __init__(self):
        self.client = RocketChat(config["username"], config["password"], server_url='https://chat.neboer.site',
                                 session=sessions.Session())
        self.last_update_list: dict[str, LastUpdateInfo] = {}  # 存储对应roomid上次更新以来获得的新消息，以及上次更新的时间。
        self.user_rooms: dict[str, str] = {}  # 用户名对应room_id
        self.start_time = datetime.now().isoformat()

    def get_next_message(self, room_id: str, room_type="channels") -> Union[None, tuple[RocketUserInfo, str]]:
        if room_id not in self.last_update_list:
            self.last_update_list[room_id] = {"messages": [], "last_message_id": None}
        if len(self.last_update_list[room_id]["messages"]) == 0:
            # 如果缓冲消息列表是空的，则更新一下消息列表。
            if room_type == 'channels':
                message_list = self.client.channels_history(room_id, oldest=self.start_time).json()['messages']  # 重新获取消息
            elif room_type == 'im':
                message_list = self.client.im_history(room_id, oldest=self.start_time).json()['messages']  # 重新获取消息
            elif room_type == 'groups':
                message_list = self.client.groups_history(room_id, oldest=self.start_time).json()['messages']  # 重新获取消息
            else:
                raise ValueError("error!")
            pending_messages = list(filter(lambda message:message['u']['username']!=config['username'], message_list))
            if self.last_update_list[room_id]['last_message_id']:
                # 在pending messages里面查找相同id的消息，如果找到，就把“更新的消息”设置成为此条消息之后发送的所有消息（来自非机器人）。
                last_message_index = list(message['_id'] for message in pending_messages).index(self.last_update_list[room_id]['last_message_id'])
                self.last_update_list[room_id]['messages'] = pending_messages[0:last_message_index]
            else: # 大概是首次运行，还没有设置最后一次更新的消息的id。
                # 如果是首次运行，并且获得了来自非机器人用户的消息，那么就把它设置成机器人收到的上一个消息。
                self.last_update_list[room_id]['messages'] = pending_messages
        if len(self.last_update_list[room_id]["messages"]) == 0:  # 经过一次更新，还是空的！
            return None
        else:
            last_message = self.last_update_list[room_id]["messages"].pop(-1)  # 移出最旧的消息
            self.last_update_list[room_id]['last_message_id'] = last_message['_id'] # 设置一个id
            return last_message['u'], last_message['msg']

    def send_message(self, room_id: str, message: str):
        self.client.chat_post_message(message, room_id)

    # 创建或者获取一个和指定用户沟通的房间。
    def get_room(self, user_name: str):
        if user_name not in self.user_rooms:
            self.user_rooms[user_name] = self.client.im_create(user_name).json()['room']['rid']
        return self.user_rooms[user_name]

    # 创建一个群组，返回群组的id
    def create_room(self, group_name, init_user_name: Union[None, str] = None) -> str:
        members = [init_user_name] if init_user_name else None
        return self.client.groups_create(group_name, members=members).json()['group']['_id']

    # 向一个群组添加用户。
    def add_user_to_room(self, group_id, user_id):
        self.client.groups_invite(group_id, user_id)

    def remove_user_from_room(self, group_id, user_id):
        self.client.groups_kick(group_id, user_id)

    # 解散一个群组。
    def dismiss_group(self, group_id: str):
        self.client.groups_delete(group_id)


if __name__ == "__main__":
    rocket = RocketChat(config["username"], config["password"], server_url='https://chat.neboer.site')
    print(rocket.im_list().json())
