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
    """Manages user permissions in memory"""
    
    def __init__(self):
        # {user_id: {"name": str, "added_date": datetime}}
        self.admins: Dict[int, dict] = {}
        self.users: Dict[int, dict] = {}
    
    def get_role(self, user_id: int) -> Role:
        """Get the role of a user"""
        if user_id == OWNER_ID:
            return Role.OWNER
        if user_id in self.admins:
            return Role.ADMIN
        if user_id in self.users:
            return Role.USER
        return Role.NONE
    
    def is_owner(self, user_id: int) -> bool:
        return user_id == OWNER_ID
    
    def is_admin_or_higher(self, user_id: int) -> bool:
        return self.is_owner(user_id) or user_id in self.admins
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user has any level of access"""
        return (
            self.is_owner(user_id)
            or user_id in self.admins
            or user_id in self.users
        )
    
    def add_admin(self, user_id: int, name: str = "Unknown") -> bool:
        """Add a new admin"""
        if user_id == OWNER_ID:
            return False
        self.admins[user_id] = {
            "name": name,
            "added_date": datetime.now(),
        }
        # Remove from users if present
        self.users.pop(user_id, None)
        return True
    
    def add_user(self, user_id: int, name: str = "Unknown") -> bool:
        """Add a new monitor user"""
        if user_id == OWNER_ID or user_id in self.admins:
            return False
        self.users[user_id] = {
            "name": name,
            "added_date": datetime.now(),
        }
        return True
    
    def remove_admin(self, user_id: int) -> bool:
        return self.admins.pop(user_id, None) is not None
    
    def remove_user(self, user_id: int) -> bool:
        return self.users.pop(user_id, None) is not None
    
    def get_all_authorized_ids(self) -> Set[int]:
        """Get all user IDs including owner"""
        return {OWNER_ID} | set(self.admins.keys()) | set(self.users.keys())


# Global instance
permissions = PermissionManager()


# Decorators
def owner_only(func):
    """Decorator: only owner can use this command"""
    async def wrapper(client, message, *args, **kwargs):
        if not permissions.is_owner(message.from_user.id):
            await message.reply_text(
                "🚫 **Access Denied!**\n\n"
                "This command is restricted to the bot owner only."
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def admin_or_owner(func):
    """Decorator: owner or admin can use this command"""
    async def wrapper(client, message, *args, **kwargs):
        user_id = message.from_user.id
        if not permissions.is_admin_or_higher(user_id):
            if permissions.is_authorized(user_id):
                await message.reply_text(
                    "🔒 **Insufficient Permissions!**\n\n"
                    "This command requires admin or owner access.\n"
                    "You only have monitoring access."
                )
            else:
                await message.reply_text(
                    "🚫 **Access Denied!**\n\n"
                    "This bot is for authorized users only.\n"
                    "Contact the owner for access."
                )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def any_authorized(func):
    """Decorator: any authorized user (owner/admin/user) can use"""
    async def wrapper(client, message, *args, **kwargs):
        if not permissions.is_authorized(message.from_user.id):
            await message.reply_text(
                "🚫 **Access Denied!**\n\n"
                "This bot is for authorized users only.\n"
                "Contact the owner for access."
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper
