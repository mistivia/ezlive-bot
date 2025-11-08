# airc.py
import asyncio
import logging
import ssl
from collections import defaultdict
from typing import (Awaitable, Callable, Dict, List, NamedTuple, Optional,
                    Union)

# --- Basic Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Message Parsing ---

class Prefix(NamedTuple):
    """Represents the prefix of an IRC message (nick!user@host)."""
    nick: str
    user: Optional[str] = None
    host: Optional[str] = None

class Message(NamedTuple):
    """Represents a parsed IRC message."""
    prefix: Optional[Prefix]
    command: str
    params: List[str]

    @classmethod
    def parse(cls, line: str) -> 'Message':
        """Parses a raw IRC line into a Message object."""
        line = line.strip()
        prefix, command, params = None, '', []

        if line.startswith(':'):
            prefix_str, line = line.split(' ', 1)
            nick, _, user_host = prefix_str[1:].partition('!')
            user, _, host = user_host.partition('@')
            prefix = Prefix(nick, user or None, host or None)

        if ' :' in line:
            parts, trailing = line.split(' :', 1)
            params = parts.split()
            params.append(trailing)
        else:
            params = line.split()

        command = params.pop(0)
        return cls(prefix, command.upper(), params)

class Client:
    def __init__(
        self,
        host: str,
        port: int,
        nickname: str,
        username: str = None,
        realname: str = None,
        password: Optional[str] = None,
        use_ssl: bool = True,
    ):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl

        self.nickname = nickname
        self.username = username or nickname
        self.realname = realname or nickname
        self.password = password

        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._is_connected = False
        self._handlers: Dict[str, List[Callable[..., Awaitable[None]]]] = defaultdict(list)

        # Register essential internal handlers
        self.on('PING')(self._handle_ping)

    async def connect(self, reconnect_delay: int = 10):
        """
        Connects to the IRC server and enters the main processing loop.
        Will attempt to reconnect if the connection is lost.
        """
        while True:
            try:
                logging.info(f"Connecting to {self.host}:{self.port}...")
                
                ssl_context = ssl.create_default_context() if self.use_ssl else None
                
                self._reader, self._writer = await asyncio.open_connection(
                    self.host, self.port, ssl=ssl_context
                )
                self._is_connected = True
                logging.info("Connection successful.")

                await self._register()
                await self._read_loop()

            except (ConnectionRefusedError, OSError) as e:
                logging.error(f"Connection failed: {e}")
            except Exception as e:
                logging.error(f"An unexpected error occurred: {e}", exc_info=True)
            finally:
                self._is_connected = False
                if self._writer:
                    self._writer.close()
                    await self._writer.wait_closed()
                logging.info(f"Disconnected. Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)

    async def _register(self):
        """Sends initial NICK/USER/PASS commands to register with the server."""
        if self.password:
            await self.send_raw(f"PASS {self.password}")
        await self.send_raw(f"NICK {self.nickname}")
        await self.send_raw(f"USER {self.username} 0 * :{self.realname}")

    async def _read_loop(self):
        """Continuously reads from the server, parses messages, and dispatches them."""
        while self._is_connected and self._reader:
            raw_line = await self._reader.readline()
            if not raw_line:
                logging.warning("Received empty data, connection likely closed.")
                break

            line = raw_line.decode('utf-8', errors='replace').strip()
            logging.debug(f"<- {line}")
            
            try:
                message = Message.parse(line)
                await self._dispatch(message)
            except Exception as e:
                logging.error(f"Failed to parse or dispatch line '{line}': {e}")

    async def _dispatch(self, message: Message):
        """Calls registered handlers for a given message command."""
        # Handlers for specific commands (e.g., 'PRIVMSG', '001')
        for handler in self._handlers.get(message.command, []):
            asyncio.create_task(handler(message))
        
        # Wildcard handlers that receive all messages
        for handler in self._handlers.get('*', []):
            asyncio.create_task(handler(message))

    async def _handle_ping(self, message: Message):
        """Internal PING handler to keep the connection alive."""
        pong_data = message.params[0]
        await self.send_raw(f"PONG :{pong_data}")
        logging.info(f"Responded to PING with PONG {pong_data}")

    def on(self, command: str) -> Callable:
        """
        A decorator to register a handler for a specific IRC command.
        
        Example:
            @client.on('PRIVMSG')
            async def on_message(message: Message):
                print(f"Received: {message}")
        """
        def decorator(func: Callable[[Message], Awaitable[None]]):
            self._handlers[command.upper()].append(func)
            return func
        return decorator

    # --- Public API Methods ---

    async def send_raw(self, data: str):
        if self._writer and self._is_connected:
            encoded_data = data.encode('utf-8')
            if len(encoded_data) > 500:
                encoded_data = encoded_data[:500]
            encoded_data = encoded_data + b'\r\n'
            self._writer.write(encoded_data)
            await self._writer.drain()
            logging.debug(f"-> {data}")
        else:
            logging.error("Cannot send data: not connected.")

    async def send_privmsg(self, target: str, text: str):
        lines = text.split('\n')
        for line in text.split('\n'):
            await self.send_raw(f"PRIVMSG {target} :{line}")

    async def join(self, channel: str):
        await self.send_raw(f"JOIN {channel}")

    async def part(self, channel: str, reason: str = "Leaving"):
        await self.send_raw(f"PART {channel} :{reason}")

    async def quit(self, reason: str = "Client shutting down"):
        await self.send_raw(f"QUIT :{reason}")
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()