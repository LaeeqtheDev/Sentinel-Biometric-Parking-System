import re

from django.db import migrations, models


def _canonical(plate: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (plate or "").upper())


def backfill_canonical(apps, schema_editor):
    Vehicle = apps.get_model("vehicles", "Vehicle")
    seen = set()
    for v in Vehicle.objects.order_by("id").only("id", "plate_number"):
        canon = _canonical(v.plate_number) or f"EMPTY{v.id}"
        if canon in seen:
            # Two existing rows describe the same physical plate (e.g. "AAP-1478"
            # and "AAP1478"). Keep the oldest; tag the newer one so the unique
            # constraint can be added. An admin should merge them afterwards.
            canon = f"{canon[:12]}DUP{v.id}"[:20]
        seen.add(canon)
        Vehicle.objects.filter(pk=v.pk).update(plate_canonical=canon)


class Migration(migrations.Migration):

    dependencies = [
        ("vehicles", "0004_vehicle_registration_doc"),
    ]

    operations = [
        migrations.AddField(
            model_name="vehicle",
            name="plate_canonical",
            field=models.CharField(max_length=20, null=True, editable=False),
        ),
        migrations.RunPython(backfill_canonical, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="vehicle",
            name="plate_canonical",
            field=models.CharField(max_length=20, unique=True, editable=False),
        ),
        migrations.AddField(
            model_name="uservehicle",
            name="approved",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddIndex(
            model_name="vehicle",
            index=models.Index(fields=["status"], name="vehicle_status_idx"),
        ),
    ]
