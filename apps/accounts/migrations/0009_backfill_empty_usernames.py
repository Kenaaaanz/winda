from django.db import migrations


def backfill_empty_usernames(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    database = schema_editor.connection.alias

    for user in User.objects.using(database).filter(username='').iterator():
        username = (user.email or '').strip()
        if not username:
            raise RuntimeError(
                f'Cannot repair user {user.pk}: the account has no email address.'
            )
        if (
            User.objects.using(database)
            .filter(username=username)
            .exclude(pk=user.pk)
            .exists()
        ):
            raise RuntimeError(
                f'Cannot repair user {user.pk}: username {username!r} is already in use.'
            )

        User.objects.using(database).filter(pk=user.pk).update(username=username)


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0008_scoutprofile_payout_paystack_recipient_code'),
    ]

    operations = [
        migrations.RunPython(backfill_empty_usernames, migrations.RunPython.noop),
    ]
