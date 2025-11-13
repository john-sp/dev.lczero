import logging
import requests
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import pre_save
from django.db import transaction  
from django.dispatch import receiver
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import pre_social_login

logger = logging.getLogger(__name__)

@receiver(pre_social_login)
def sync_discord_roles_to_groups(sender, request, sociallogin, **kwargs):
    """
    Signal receiver to synchronize a user's Discord roles with Django groups.
    """
    
    logger.info("Starting Discord role to Django group synchronization")
    if sociallogin.account.provider != 'discord':
        return
    # Get the user's access token
    try:
        social_token = sociallogin.token
        access_token = social_token.token
    except Exception as e:
        logger.error(f"Failed to get access token: {e}")
        return

    # Fetch the user's member information for the specific guild
    guild_id = settings.DISCORD_GUILD_ID
    if not guild_id:
        logger.error("DISCORD_GUILD_ID is not set")
        return
    url = f"https://discord.com/api/v10/users/@me/guilds/{guild_id}/member"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            member_data = response.json()
            user_roles_set = set(member_data.get('roles', []))

            user = sociallogin.user

            ensure_present = [
                group_name
                for role, group_name in settings.DISCORD_ROLE_TO_GROUP_MAPPING.items()
                if role in user_roles_set
            ]
            ensure_absent = [
                group_name
                for role, group_name in settings.DISCORD_ROLE_TO_GROUP_MAPPING.items()
                if role not in user_roles_set
            ]

            print("Ensuring groups:", Group.objects.filter(name__in=ensure_present), "Removing groups:", ensure_absent)

            with transaction.atomic():
                user.groups.add(*Group.objects.filter(name__in=ensure_present))
                user.groups.remove(*Group.objects.filter(name__in=ensure_absent))
        else:
            logger.error(f"Error fetching guild member data: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exception during Discord API call: {e}")