import logging
import requests
from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import pre_save
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
            user_roles = member_data.get('roles', [])

            user = sociallogin.user
            
            # Clear existing mapped groups to handle role removals in Discord
            for group_name in settings.DISCORD_ROLE_TO_GROUP_MAPPING.values():
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.remove(group)
                except Group.DoesNotExist:
                    # Group might not exist, so we can ignore it
                    pass

            # Assign groups based on the mapping
            for role_id in user_roles:
                logger.info(f"Processing Discord role ID: {role_id}")
                group_name = settings.DISCORD_ROLE_TO_GROUP_MAPPING.get(role_id)
                if group_name:
                    try:
                        group = Group.objects.get(name=group_name)
                        user.groups.add(group)
                    except Group.DoesNotExist:
                        # You might want to log this for debugging
                        logger.warning(f"Django group '{group_name}' does not exist.")
        else:
            logger.error(f"Error fetching guild member data: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exception during Discord API call: {e}")
        # Don't raise the exception to avoid breaking login