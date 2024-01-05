# Userport

Contains code for Userport Appt

Command to run app: flask --app userport run --debug
Command to start Celery worker: celery -A userport.make_celery worker --loglevel INFO
Command to Purge unacked tasks in queue: celery -A userport.make_celery purge
