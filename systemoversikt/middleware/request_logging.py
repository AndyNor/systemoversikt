
import time
from django.utils.deprecation import MiddlewareMixin
from django.db import connections
from systemoversikt.models import RequestLogs

def get_client_ip(request):
	"""
	Returns best-effort client IP.
	If your app is behind a reverse proxy/load balancer, ensure it sets X-Forwarded-For.
	The first IP in X-Forwarded-For is typically the original client.
	"""
	xff = request.META.get("HTTP_X_FORWARDED_FOR")
	if xff:
		parts = [p.strip() for p in xff.split(",") if p.strip()]
		if parts:
			return parts[0]
	return request.META.get("REMOTE_ADDR")


class RequestLoggingMiddleware(MiddlewareMixin):
	def process_request(self, request):
		request._start_time = time.time()
		request._query_count = 0
		request._query_time_ms = 0.0

		# ✅ Attach execute_wrapper to all DB connections for this request
		def timing_wrapper(execute, sql, params, many, context):
			start = time.time()
			try:
				return execute(sql, params, many, context)
			finally:
				duration_ms = (time.time() - start) * 1000
				request._query_count += 1
				request._query_time_ms += duration_ms

		for conn in connections.all():
			conn.execute_wrappers.append(timing_wrapper)

	def process_response(self, request, response):
		try:
			# ✅ Skip static files and optionally admin
			if request.path.startswith("/static"):  # or request.path.startswith("/admin"):
				return response

			duration = round((time.time() - request._start_time) * 1000, 2)  # ms
			user = request.user.username if request.user.is_authenticated else "Anonymous"
			source_ip = get_client_ip(request)

			# ✅ Use counters collected by timing_wrapper
			query_count = getattr(request, "_query_count", 0)
			total_db_time = round(getattr(request, "_query_time_ms", 0.0), 2)

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
			response["X-Source-IP"] = source_ip or ""
		except Exception:
			pass

		return response
