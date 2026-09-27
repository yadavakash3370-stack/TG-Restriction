"""Access control system for owner/admin/user roles"""
from enum import Enum
from typing import Dict, Set
from datetime import datetime
from config import OWNER_ID


class Role(Enum):
    OWNER = "owner"
    ADMIN = "admin"
    USER = "user"
    NONE = "none"


class PermissionManager:
    def __init__(self):
        self.admins: Dict[int, dict] = {}
        self.users: Dict[int, dict] = {}
    
    def get_user_id(self, message) -> int:
        """Safely extract user ID from message (even in channels)"""
        if message.from_user:
            return message.from_user.id
        # In channels, if posted by chat or linked admin
        if message.sender_chat:
            return message.sender_chat.id
        return 0

    def is_owner(self, user_id: int) -> bool:
        return user_id == OWNER_ID
    
    def is_admin_or_higher(self, user_id: int) -> bool:
        # If message is from channel itself, we allow if owner added the bot
        if user_id == 0 or user_id == OWNER_ID:
            return True
        return self.is_owner(user_id) or user_id in self.admins
    
    def is_authorized(self, user_id: int) -> bool:
        if user_id == 0 or user_id == OWNER_ID:
            return True
        return (
            self.is_owner(user_id)
            or user_id in self.admins
            or user_id in self.users
        )
    
    def add_admin(self, user_id: int, name: str = "Unknown") -> bool:
        if user_id == OWNER_ID:
            return False
        self.admins[user_id] = {"name": name, "added_date": datetime.now()}
        self.users.pop(user_id, None)
        return True
    
    def add_user(self, user_id: int, name: str = "Unknown") -> bool:
        if user_id == OWNER_ID or user_id in self.admins:
            return False
        self.users[user_id] = {"name": name, "added_date": datetime.now()}
        return True
    
    def remove_admin(self, user_id: int) -> bool:
        return self.admins.pop(user_id, None) is not None
    
    def remove_user(self, user_id: int) -> bool:
        return self.users.pop(user_id, None) is not None
    
    def get_all_authorized_ids(self) -> Set[int]:
        return {OWNER_ID} | set(self.admins.keys()) | set(self.users.keys())


permissions = PermissionManager()


def admin_or_owner(func):
    async def wrapper(client, message, *args, **kwargs):
        user_id = permissions.get_user_id(message)
        if not permissions.is_admin_or_higher(user_id):
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def owner_only(func):
    async def wrapper(client, message, *args, **kwargs):
        user_id = permissions.get_user_id(message)
        if user_id != OWNER_ID:
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def any_authorized(func):
    async def wrapper(client, message, *args, **kwargs):
        user_id = permissions.get_user_id(message)
        if not permissions.is_authorized(user_id):
            return
        return await func(client, message, *args, **kwargs)
    return wrapper
