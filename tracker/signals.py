from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Streak, UserProfile

@receiver(post_save, sender=User)
def create_user_profile_and_streak(sender, instance, created, **kwargs):
    if created:
        Streak.objects.get_or_create(user=instance)
        UserProfile.objects.get_or_create(user=instance)

