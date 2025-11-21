
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
from monitoring.models import RequestLogs

class Command(BaseCommand):
	help = "Delete RequestLogs older than 1 month"

	def handle(self, *args, **options):
		cutoff_date = now() - timedelta(days=30)
		old_logs = RequestLogs.objects.filter(timestamp__lt=cutoff_date)
		count = old_logs.count()

		if count > 0:
			old_logs.delete()
			self.stdout.write(self.style.SUCCESS(f"Deleted {count} old RequestLogs older than {cutoff_date.date()}"))
		else:
			self.stdout.write(self.style.WARNING("No old RequestLogs found to delete."))
