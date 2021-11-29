# "谁是卧底"房主机器人。
from math import floor
from random import choices, choice, shuffle, randint, sample
from typing import List, Union, Tuple
from lib import Player, GamePlayerInfo, Identity, GameControl, GameStatus


class Game:
    def __init__(self, init_player: Player, word_list: List[List[str]], game_id, control: GameControl):
        self.player_list: List[Player] = [init_player]
        self.minimal_players = 3
        self.spies_per_player = 3  # 卧底的数量和玩家人数有关系。数量为[1, floor(n/3)]
        self.word_list: List[List[str]] = word_list  # 词汇表。游戏的卧底词汇和平民词汇从这个列表中选择。
        self.game_id: int = game_id  # 对局id，这个应该提前给出
        self.game_round = 0
        self.control = control
        self.status = GameStatus.preparing
        self.creator: Player = init_player  # 游戏的创建者。

    def add_player(self, new_player: Player):
        self.player_list.append(new_player)

    def prepare_players(self) -> Tuple[List[Player], Tuple[str, str]]:
        # 给游戏里的用户发身份，以及分配用户的游戏内id。返回卧底玩家和(卧底词,平民词)
        spies_count = randint(1, floor(float(len(self.player_list)) / float(self.spies_per_player)))
        chosen_spies: List[Player] = sample(self.player_list, spies_count)  # 选出卧底。
        chosen_word: List[str] = sample(choice(self.word_list), 2)  # 重新排序一下，选择第一个作为卧底词汇，第二个作为平民词汇
        for index, player in enumerate(self.player_list):
            player.id = index + 1
            if player in chosen_spies:
                player.game_player_info = GamePlayerInfo(Identity.spy, chosen_word[0])
            else:
                player.game_player_info = GamePlayerInfo(Identity.innocent, chosen_word[1])
        return chosen_spies, (chosen_word[0], chosen_word[1])

    def get_winner(self) -> Union[Identity, None]:
        # 找到胜利者。当参与人数超过四人时，规则：
        # 平民获胜条件：场上不存在卧底。
        # 卧底获胜条件：场上卧底数不少于(平民数-1)。2平民1卧底时，卧底已经获胜。
        # 当参与人数等于三人时，规则：
        # 投出平民：卧底获胜；投出卧底：平民获胜。
        innocent_count = len(list(player for player in self.player_list if player.game_player_info.identity == Identity.innocent))
        spy_count = len(list(player for player in self.player_list if player.game_player_info.identity == Identity.spy))
        if spy_count == 0:
            return Identity.innocent  # 没有卧底，平民胜利。
        else:
            if len(self.player_list) == 3:  # 游戏仅有三人参与。
                if spy_count == 1 and innocent_count == 1:
                    return Identity.spy
                else:
                    return None
            else:
                if spy_count >= innocent_count - 1:
                    return Identity.spy
                else:
                    return None

    @staticmethod
    def print_players_list(players_list: List[Player], inline: bool = True) -> str:
        delimiter = '、' if inline else '\n'
        return delimiter.join(p.__str__() for p in players_list)

    def start(self):
        self.status = GameStatus.started
        assert len(self.player_list) >= self.minimal_players
        # 人数多于最小人数，可以开始了。
        spies_players, keywords = self.prepare_players()
        # 排序players_list
        shuffle(self.player_list)
        # 给对应的用户分发身份。
        for player in self.player_list:
            self.control.send_private_message(player, f"你的词是：{player.game_player_info.keyword}，你的id：{player.id}")
        self.control.send_public_message(f"玩家列表：\n{Game.print_players_list(self.player_list, False)}\n请大家牢记自己的编号。")
        self.control.send_public_message(f"身份分发完毕。共有{len(spies_players)}个卧底、{len(self.player_list) - len(spies_players)}个平民。")
        self.control.send_public_message(f"平民游戏目标：投出所有卧底；卧底游戏目标：尽可能不被投出。现在游戏开始。")
        while self.get_winner() is None:  # 一轮游戏。
            self.game_round += 1
            self.control.send_public_message(f"第{self.game_round}轮")
            # 需要发言的玩家可能来自于之前的平票玩家。
            players_need_speak = self.player_list.copy()
            while len(players_need_speak) != 1:
                # 只要未找到唯一的票数最高的玩家，就要让票数相等的玩家们一直陈述，其他玩家一直投票，直到决出一位票数最高的玩家被投出。
                shuffle(players_need_speak)
                # 决定发言顺序。
                for player in players_need_speak:
                    self.control.send_public_message(f"请{player}发言。")
                    self.control.wait_for_player(player)
                # 发言结束，开始投票。先发言的人拥有后投票的权力。
                # 投票总是全体玩家参与，投票顺序在未决出被投出玩家时不会改变
                for voting_player in reversed(self.player_list):
                    self.control.send_public_message(f"请{voting_player}投票。请发送一条消息内容只有要票选的玩家的id，输入0弃权。")
                    while True:
                        vote_str = self.control.wait_for_player(voting_player)
                        if vote_str == "0":
                            break  # 弃权。
                        else:
                            try:
                                vote_id = int(vote_str)
                            except ValueError:
                                self.control.send_public_message(f"输入内容不是id，请重新输入。")
                                continue
                            else:
                                target_voted_player = next(
                                    (player for player in self.player_list if player.id == vote_id), None)
                                if target_voted_player:
                                    target_voted_player.game_player_info.vote_count += 1
                                    break
                                else:
                                    self.control.send_public_message("输入的id不存在，请重新输入。")
                                    continue
                max_vote_count = max(player.game_player_info.vote_count for player in self.player_list)
                players_need_speak = list(filter(lambda player: player.game_player_info.vote_count == max_vote_count,
                                                 self.player_list))  # 找出票数最高的玩家们。
                if len(players_need_speak) > 1:
                    self.control.send_public_message(f"玩家{Game.print_players_list(players_need_speak)}平票。")
                # 还原玩家投票数
                for player in self.player_list:
                    player.game_player_info.vote_count = 0
            # 已经找到了一个唯一的票数最高的玩家。
            target_voted_player = players_need_speak[0]
            self.player_list.remove(target_voted_player)  # 被投出的玩家立刻被移出玩家列表。
            self.control.send_public_message(f"玩家{target_voted_player}被投出。")
        if self.get_winner() == Identity.spy:
            self.control.send_public_message(
                f"游戏结束，卧底胜利。卧底玩家：{self.print_players_list(spies_players)}，卧底词：{keywords[0]}，平民词：{keywords[1]}")
        else:
            self.control.send_public_message(
                f"游戏结束，平民胜利。卧底玩家：{self.print_players_list(spies_players)}，卧底词：{keywords[0]}，平民词：{keywords[1]}")
        self.status = GameStatus.finished
