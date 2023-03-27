from typing import List, Union

from .base import TimeStep, Environment
from ..message import Message, MessagePool
from ..agent import Moderator


class Conversation(Environment):
    """
    Turn-based fully observable conversation environment.
    Next speaker order is either parallel or round-robin.
    """

    def __init__(self, player_names: List[str], env_desc: str, parallel: bool = False):
        super().__init__(player_names, env_desc)
        self.message_pool = MessagePool()
        self.parallel = parallel  # if True, all players speak at the same time

        self._current_turn = 0
        self._next_player_idx = 0

    @classmethod
    def from_config(cls, config: dict):
        assert config["env_type"] == "conversation"
        return cls(
            player_names=config["player_names"],
            env_desc=config["env_desc"],
            parallel=config["parallel"],
        )

    def to_config(self) -> dict:
        return {
            "env_type": "conversation",
            "player_names": self.player_names,
            "env_desc": self.env_desc,
            "parallel": self.parallel,
        }

    def reset(self):
        self._current_turn = 0
        self._next_player_idx = 0
        self.message_pool.reset()

        init_timestep = TimeStep(observation=[],
                                 reward=self.get_zero_rewards(),
                                 terminal=False)
        return init_timestep

    def print(self):
        self.message_pool.print()

    def get_next_player(self) -> str:
        """
        get the next player
        """
        return self.player_names[self._next_player_idx]

    def get_observation(self, player_name=None) -> List[Message]:
        """
        get observation for the player
        """
        if player_name is None:
            return self.message_pool.get_all_messages()
        else:
            return self.message_pool.get_visible_messages(player_name, turn=self._current_turn)

    def step(self, player_name: str, action: str) -> TimeStep:
        """
        step function that is called by the arena
        Args:
            player_name: the name of the player that takes the action
            action: the action that the agents wants to take
        """
        message = Message(agent_name=player_name, content=action, turn=self._current_turn)
        self.message_pool.append_message(message)

        # Update the counters
        if not self.parallel or self._next_player_idx == 0:
            self._current_turn += 1
        self._next_player_idx = (self._next_player_idx + 1) % len(self.player_names)

        timestep = TimeStep(observation=self.get_observation(),
                            reward=self.get_zero_rewards(),
                            terminal=False)  # Return all the messages
        return timestep


class ModeratedConversation(Conversation):
    """
    Turn-based fully observable conversation environment.
    Next speaker order is either parallel or round-robin.
    Moderator is a special agent that can see all messages and can decide whether the conversation is over.
    """

    def __init__(self, player_names: List[str], env_desc: str, parallel: bool = False,
                 moderator: Moderator = None, moderator_visibility: Union[str, List[str]] = "all"):
        super().__init__(player_names, env_desc, parallel)
        self.moderator = moderator
        self.moderator_visibility = moderator_visibility  # by default, all players can see the moderator's messages

    @classmethod
    def from_config(cls, config: dict):
        assert config["env_type"] == "moderated_conversation"
        # Add env_desc to the config of the moderator if it is not there
        if "env_desc" not in config["moderator"]:
            config["moderator"]["env_desc"] = config["env_desc"]

        return cls(
            player_names=config["player_names"],
            env_desc=config["env_desc"],
            parallel=config["parallel"],
            moderator=Moderator.from_config(config["moderator"]),
            moderator_visibility=config.get("moderator_visibility", "all")
        )

    def to_config(self) -> dict:
        return {
            "env_type": "moderated_conversation",
            "player_names": self.player_names,
            "env_desc": self.env_desc,
            "parallel": self.parallel,
            "moderator": self.moderator.to_config(),
            "moderator_visibility": self.moderator_visibility,
        }

    def step(self, player_name: str, action: str) -> TimeStep:
        """
        step function that is called by the arena
        Args:
            player_name: the name of the player that takes the action
            action: the action that the agents wants to take
        """
        message = Message(agent_name=player_name, content=action, turn=self._current_turn)
        self.message_pool.append_message(message)

        # Moderator's turn
        moderator_history = self.message_pool.get_all_messages()
        moderator_response = self.moderator(moderator_history)
        moderator_message = Message(agent_name=self.moderator.name,
                                    content=moderator_response,
                                    turn=self._current_turn,
                                    visible_to=self.moderator_visibility)
        self.message_pool.append_message(moderator_message)

        terminal = self.moderator.is_terminal(moderator_history)

        # Update the counters
        if not self.parallel or self._next_player_idx == 0:
            self._current_turn += 1
        self._next_player_idx = (self._next_player_idx + 1) % len(self.player_names)

        timestep = TimeStep(observation=self.get_observation(), reward=0, terminal=terminal)  # Return all the messages
        return timestep