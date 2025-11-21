import time
from django.utils.deprecation import MiddlewareMixin
from django.db import connection
from systemoversikt.models import RequestLogs

def get_client_ip(request):
	"""
	Returns best-effort client IP.
	If your app is behind a reverse proxy/load balancer, ensure it sets X-Forwarded-For.
	The first IP in X-Forwarded-For is typically the original client.
	"""
	xff = request.META.get("HTTP_X_FORWARDED_FOR")
	if xff:
		# Example: "203.0.113.1, 198.51.100.5"
		# Take the first non-empty trimmed part
		parts = [p.strip() for p in xff.split(",") if p.strip()]
		if parts:
			return parts[0]
	return request.META.get("REMOTE_ADDR")





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

			source_ip = get_client_ip(request)

			# ✅ Save to DB
			RequestLogs.objects.create(
				path=request.path,
				method=request.method,
				user=user,
				status_code=response.status_code,
				duration_ms=duration,
				sql_queries=query_count,
				sql_time_ms=total_db_time,
				source_ip=source_ip,
			)

			# Optional: Add headers for debugging
			response["X-Render-Time-ms"] = str(duration)
			response["X-SQL-Queries"] = str(query_count)
			response["X-SQL-Time-ms"] = str(total_db_time)

		except Exception:
			# Avoid breaking the app if logging fails
			pass

		return response