import logging
import pickle
from collections import defaultdict
from copy import deepcopy
from typing import Dict, Optional, Tuple, Any, cast

import aioredis
from telegram.ext import BasePersistence, PersistenceInput
from telegram.ext._contexttypes import ContextTypes
from telegram.ext._utils.types import (
    BD, CD, UD,
    CDCData,
    ConversationDict,
    ConversationKey
)

logger = logging.getLogger(__file__)


class RedisPersistence(BasePersistence[UD, CD, BD]):

    def __init__(
            self,
            url: str,
            redis_key: str,
            initial_data: Dict[str, Dict] = None,
            store_data: PersistenceInput = None,
            on_flush: bool = False,
            update_interval: float = 60,
            context_types: ContextTypes[Any, UD, CD, BD] = None,
    ):
        super().__init__(store_data=store_data,
                         update_interval=update_interval)
        self.url = url
        self.redis_key = redis_key
        self._initial_data = initial_data
        self.on_flush = on_flush
        self.user_data: Optional[Dict[int, UD]] = None
        self.chat_data: Optional[Dict[int, CD]] = None
        self.bot_data: Optional[BD] = None
        self.callback_data: Optional[CDCData] = None
        self.conversations: Optional[Dict[str, Dict[Tuple, object]]] = None
        self.context_types = cast(ContextTypes[Any, UD, CD, BD],
                                  context_types or ContextTypes())

    def _format_redis_url(self) -> str:
        prefix = 'redis://'
        if self.url.startswith(prefix):
            return self.url
        return f'{prefix}{self.url}'

    async def _redis_pool_set(self, key: str, data: bytes) -> None:
        connection = aioredis.from_url(self._format_redis_url())
        await connection.set(key, data)

    async def _redis_pool_get(self, key: str) -> bytes:
        connection = aioredis.from_url(self._format_redis_url())
        data = await connection.get(key)
        return data

    async def _perform_initialization(self) -> None:
        valid_keys = ('bot_data', 'user_data', 'chat_data')
        data = {}
        for key, value in self._initial_data.items():
            if key not in valid_keys or not isinstance(value, dict):
                continue
            data[key] = value
        data_bytes = await self._redis_pool_get(self.redis_key)
        if data_bytes is None:
            self.conversations = {}
            self.user_data = data.get('user_data', defaultdict(dict))
            self.chat_data = data.get('chat_data', defaultdict(dict))
            self.bot_data = data.get('bot_data', {})
        else:
            db_data = pickle.loads(data_bytes)
            self.user_data = defaultdict(
                dict, db_data.get('_user_data', {})
            )
            self.user_data.update(data.get('user_data', {}))

            self.chat_data = defaultdict(
                dict, db_data.get('_chat_data', {})
            )
            self.chat_data.update(data.get('chat_data', {}))

            self.bot_data = db_data.get('_bot_data', {})
            self.bot_data.update(data.get('bot_data', {}))

            self.conversations = data.get('_conversations', {})

        await self._dump_redis()
        logger.info('БД успешно проинициализирована')

    async def _load_redis(self) -> None:
        if self._initial_data:
            await self._perform_initialization()
            self._initial_data = {}
        try:
            data_bytes = await self._redis_pool_get(self.redis_key)
            if data_bytes is None:
                self.conversations = {}
                self.user_data = defaultdict(dict)
                self.chat_data = defaultdict(dict)
                self.bot_data = {}
                return
            data = pickle.loads(data_bytes)
            self.user_data = defaultdict(dict, data.get('_user_data', {}))
            self.chat_data = defaultdict(dict, data.get('_chat_data', {}))
            self.bot_data = data.get('_bot_data', {})
            self.conversations = data.get('_conversations', {})
        except Exception as exc:
            raise TypeError(
                f"Something went wrong unpickling from Redis"
            ) from exc

    async def _dump_redis(self) -> None:
        data = {
            '_bot_data': self.bot_data,
            '_user_data': self.user_data,
            '_chat_data': self.chat_data,
            '_callback_data': self.callback_data,
            '_conversations': self.conversations
        }
        data_bytes = pickle.dumps(data)
        await self._redis_pool_set(self.redis_key, data_bytes)

    async def get_bot_data(self) -> BD:
        """Returns the bot_data from the Redis if it exists or
        an empty :obj:`dict`."""
        if not self.bot_data:
            await self._load_redis()
        return deepcopy(self.bot_data)

    async def update_bot_data(self, data: BD) -> None:
        """Will update the bot_data and depending on :attr:`on_flush` save
        in Redis."""
        if self.bot_data == data:
            return
        self.bot_data = data
        if not self.on_flush:
            await self._dump_redis()

    async def refresh_bot_data(self, bot_data: BD) -> None:
        pass

    async def get_chat_data(self) -> Dict[int, CD]:
        """Returns the chat_data from the Redis if it exists or
        an empty :obj:`dict`."""
        if not self.chat_data:
            await self._load_redis()
        return deepcopy(self.chat_data)

    async def update_chat_data(self, chat_id: int, data: CD) -> None:
        """Will update the chat_data and depending on :attr:`on_flush` save
        in Redis."""
        if self.chat_data is None:
            self.chat_data = {}
        if self.chat_data.get(chat_id) == data:
            return
        self.chat_data[chat_id] = data
        if not self.on_flush:
            await self._dump_redis()

    async def refresh_chat_data(self, chat_id: int, chat_data: CD) -> None:
        pass

    async def drop_chat_data(self, chat_id: int) -> None:
        """Will delete the specified key from the ``chat_data`` and depending
        on :attr:`on_flush` save in Redis."""
        if self.chat_data is None:
            return
        self.chat_data.pop(chat_id, None)

        if not self.on_flush:
            await self._dump_redis()

    async def get_user_data(self) -> Dict[int, UD]:
        """Returns the user_data from the Redis if it exists or an empty
        :obj:`dict`."""
        if not self.user_data:
            await self._load_redis()
        return deepcopy(self.user_data)

    async def update_user_data(self, user_id: int, data: UD) -> None:
        """Will update the user_data and depending on :attr:`on_flush` save
        in Redis."""
        if self.user_data is None:
            self.user_data = {}
        if self.user_data.get(user_id) == data:
            return
        self.user_data[user_id] = data
        if not self.on_flush:
            await self._dump_redis()

    async def refresh_user_data(self, user_id: int, user_data: UD) -> None:
        pass

    async def drop_user_data(self, user_id: int) -> None:
        """Will delete the specified key from the ``user_data`` and depending
        on :attr:`on_flush` save in Redis"""
        if self.user_data is None:
            return
        self.user_data.pop(user_id, None)

        if not self.on_flush:
            await self._dump_redis()

    async def get_callback_data(self) -> Optional[CDCData]:
        """Returns the callback_data from the Redis if it exists or an empty
        :obj:`dict`."""
        if not self.callback_data:
            await self._load_redis()
        if self.callback_data is None:
            return None
        return deepcopy(self.callback_data)

    async def update_callback_data(self, data: CDCData) -> None:
        """Will update the callback_data and depending on :attr:`on_flush` save
        in Redis."""
        if self.callback_data == data:
            return
        self.callback_data = data
        if not self.on_flush:
            await self._dump_redis()

    async def get_conversations(self, name: str) -> ConversationDict:
        """Returns the conversations from the Redis if it exists or an empty
        :obj:`dict`."""
        if not self.conversations:
            await self._load_redis()
        return self.conversations.get(name, {}).copy()

    async def update_conversation(
            self, name: str, key: ConversationKey, new_state: Optional[object]
    ) -> None:
        """Will update the conversations for the given handler and depending
        on :attr:`on_flush` save in Redis."""
        if not self.conversations:
            self.conversations = {}
        if self.conversations.setdefault(name, {}).get(key) == new_state:
            return
        self.conversations[name][key] = new_state
        if not self.on_flush:
            await self._dump_redis()

    async def flush(self) -> None:
        """Will save all data in memory in Redis."""
        if (
                self.user_data
                or self.chat_data
                or self.bot_data
                or self.callback_data
                or self.conversations
        ):
            await self._dump_redis()
