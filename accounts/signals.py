from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.models import VendorProfile


@receiver(pre_save, sender=VendorProfile)
def track_verification_status_change(sender, instance, **kwargs):
    if not instance.pk:
        instance._verification_status_changed_to = None
        return

    previous_status = sender.objects.only("verification_status").get(pk=instance.pk).verification_status
    instance._verification_status_changed_to = (
        instance.verification_status
        if previous_status != instance.verification_status
        else None
    )


@receiver(post_save, sender=VendorProfile)
def send_verification_status_email(sender, instance, **kwargs):
    status = getattr(instance, "_verification_status_changed_to", None)
    if status not in {
        VendorProfile.VerificationStatus.APPROVED,
        VendorProfile.VerificationStatus.DECLINED,
    }:
        return

    from notifications.services import send_vendor_approved, send_vendor_declined

    send_email = (
        send_vendor_approved
        if status == VendorProfile.VerificationStatus.APPROVED
        else send_vendor_declined
    )
    transaction.on_commit(lambda: send_email(instance))