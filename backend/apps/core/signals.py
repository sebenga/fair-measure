"""Signals other apps can listen to without importing each other."""

from django.dispatch import Signal

# Sent with `competition=` whenever counted results in a competition change.
results_changed = Signal()
