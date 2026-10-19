from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import UUIDModel

from .storage import private_storage


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra):
        if not email:
            raise ValueError("Users must have an email address.")
        user = self.model(email=self.normalize_email(email), **extra)
        if password:
            user.set_password(password)
        else:
            # Social-only accounts have no usable local password.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("is_active", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superusers must have is_staff and is_superuser set.")
        return self._create_user(email, password, **extra)


class User(UUIDModel, AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(_("email address"), unique=True, db_index=True)
    display_name = models.CharField(max_length=120, blank=True)
    avatar_url = models.URLField(blank=True)
    bio = models.TextField(blank=True)

    # Optional personal details. A profile is usable with every one of these empty.
    given_name = models.CharField(_("name"), max_length=80, blank=True)
    family_name = models.CharField(_("surname"), max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    id_number = models.CharField(_("ID number"), max_length=40, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    city = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True)
    headline = models.CharField(
        max_length=160, blank=True, help_text=_("A role or one-line title, as on a CV.")
    )
    website = models.URLField(blank=True)
    experience = models.TextField(blank=True)
    education = models.TextField(blank=True)
    skills = models.TextField(blank=True)
    languages = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.display_name or self.email

    def get_full_name(self) -> str:
        legal = " ".join(part for part in (self.given_name, self.family_name) if part).strip()
        return legal or self.display_name or self.email

    def get_short_name(self) -> str:
        return self.given_name or (
            self.display_name.split(" ")[0] if self.display_name else self.email
        )


class SocialAccount(UUIDModel):
    """Links a third-party identity (currently Google) to a local user."""

    class Provider(models.TextChoices):
        GOOGLE = "google", "Google"
        FIREBASE = "firebase", "Firebase"
        AUTH0 = "auth0", "Auth0"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="social_accounts")
    provider = models.CharField(max_length=32, choices=Provider.choices)
    provider_user_id = models.CharField(max_length=255)
    raw_profile = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_user_id"], name="uniq_provider_identity"
            )
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.provider_user_id}"


SOCIAL_PROVIDER_CHOICES = SocialAccount.Provider.choices


def _document_path(instance: IdentityDocument, filename: str) -> str:
    import uuid

    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"identity/{instance.user_id}/{uuid.uuid4().hex}.{suffix[:5]}"


class IdentityDocument(UUIDModel):
    """An optional passport or ID scan. Only its owner can ever download it.

    Scouts, other players and competition admins never see these, nor that one
    exists. A new upload of the same kind replaces the old file.
    """

    class Kind(models.TextChoices):
        PASSPORT = "passport", _("Passport")
        NATIONAL_ID = "national_id", _("ID document")

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="identity_documents")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    file = models.FileField(upload_to=_document_path, storage=private_storage, max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=80)
    size_bytes = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["kind"]
        constraints = [
            models.UniqueConstraint(fields=["user", "kind"], name="uniq_document_kind_per_user")
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.kind}"


@receiver(post_delete, sender=IdentityDocument)
def _remove_document_file(sender, instance: IdentityDocument, **kwargs) -> None:
    # Deleting an account cascades here; the scan must not outlive the row.
    if instance.file:
        instance.file.delete(save=False)
