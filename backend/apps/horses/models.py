"""The horse registry, and entrants that are a combination of horse and people.

A combination entrant is still an ordinary competition Participant; this module
only records who and what it is made of, so results can be credited to the horse,
the rider (or jockey) and the trainer separately.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class Horse(BaseModel):
    class Sex(models.TextChoices):
        MARE = "mare", _("Mare")
        GELDING = "gelding", _("Gelding")
        STALLION = "stallion", _("Stallion")
        FILLY = "filly", _("Filly")
        COLT = "colt", _("Colt")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        RETIRED = "retired", _("Retired")

    name = models.CharField(max_length=120)
    registration_number = models.CharField(
        max_length=60, blank=True, help_text=_("Passport or studbook registration number.")
    )
    fei_id = models.CharField(max_length=30, blank=True, help_text=_("Optional international ID."))
    breed = models.CharField(max_length=80, blank=True)
    sex = models.CharField(max_length=10, choices=Sex.choices, blank=True)
    colour = models.CharField(max_length=40, blank=True)
    foaled_on = models.DateField(null=True, blank=True)
    owners = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="owned_horses"
    )
    owner_names = models.CharField(
        max_length=240, blank=True, help_text=_("Owners who are not on Fair Measure.")
    )
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trained_horses",
    )
    trainer_name = models.CharField(max_length=120, blank=True)
    photo_url = models.URLField(blank=True, max_length=600)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="horses_registered",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["registration_number"],
                condition=~models.Q(registration_number=""),
                name="uniq_horse_registration_number",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def can_edit(self, user) -> bool:
        if not user or not user.is_authenticated:
            return False
        return (
            user.is_staff
            or self.created_by_id == user.id
            or self.trainer_id == user.id
            or self.owners.filter(pk=user.pk).exists()
        )


class Combination(BaseModel):
    """What a combination entrant is made of: a horse, its rider, and its trainer."""

    participant = models.OneToOneField(
        "competitions.Participant", on_delete=models.CASCADE, related_name="combination"
    )
    horse = models.ForeignKey(Horse, on_delete=models.PROTECT, related_name="combinations")
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rides",
    )
    rider_name = models.CharField(max_length=120, blank=True)
    trainer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trained_entries",
    )
    trainer_name = models.CharField(max_length=120, blank=True)

    def __str__(self) -> str:
        return f"{self.horse.name} / {self.rider_label}"

    @property
    def rider_label(self) -> str:
        if self.rider_id:
            return self.rider.get_full_name() or self.rider.display_name
        return self.rider_name

    @property
    def trainer_label(self) -> str:
        if self.trainer_id:
            return self.trainer.get_full_name() or self.trainer.display_name
        return self.trainer_name or self.horse.trainer_name
