import time
from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from systemoversikt.models import RequestLogs

class RequestLoggingMiddleware(MiddlewareMixin):
	def process_request(self, request):
		request._start_time = time.time()

	def process_response(self, request, response):
		try:
			# ✅ Skip static files and admin
			if request.path.startswith("/static"): # or request.path.startswith("/admin"):
				return response

			duration = round((time.time() - request._start_time) * 1000, 2)  # ms
			user = request.user.username if request.user.is_authenticated else "Anonymous"

			# ✅ Collect SQL query stats
			query_count = len(connection.queries)
			total_db_time = round(sum(float(q.get("time", 0)) for q in connection.queries) * 1000, 2)  # ms

			# ✅ Save to DB
			RequestLogs.objects.create(
				path=request.path,
				method=request.method,
				user=user,
				status_code=response.status_code,
				duration_ms=duration,
				sql_queries=query_count,
				sql_time_ms=total_db_time
			)

			# Optional: Add headers for debugging
			response["X-Render-Time-ms"] = str(duration)
			response["X-SQL-Queries"] = str(query_count)
			response["X-SQL-Time-ms"] = str(total_db_time)

		except Exception:
			# Avoid breaking the app if logging fails
			pass

		return response
