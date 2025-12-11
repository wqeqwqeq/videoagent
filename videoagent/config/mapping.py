"""Sheet-to-topic mapping and optional filter functions for VideoAgent."""

from typing import Callable

# View name (from Tableau) -> topic_id (matches YAML filename without extension)
# Update these mappings to match your actual Tableau view names
sheet_topic_map: dict[str, str] = {
    "Major Issues": "topic_01_major_issues",
    "Critical Workflows Current": "topic_02_critical_workflows_current",
    "Critical Workflows History": "topic_03_critical_workflows_history",
    "Platform Health Current": "topic_04_platform_health_current",
    "Platform Health History": "topic_05_platform_health_history",
    "CR Deployed 24h": "topic_06_cr_deployed_24h",
    "CR Upcoming": "topic_07_cr_upcoming",
    "CR Overdue": "topic_08_cr_overdue",
    "Problems Tasks": "topic_09_problems_tasks",
    "Major Incidents": "topic_10_major_incidents",
    "Manual Unplanned Activities": "topic_11_manual_unplanned_activities",
    "Upcoming Completed Events": "topic_12_upcoming_completed_events",
    "Open Items Summary": "topic_13_open_items_summary",
}


# Optional filters per topic: topic_id -> filter function
# Filter function signature: (csv_content: str) -> str
# Example filter that filters rows by today's date:
#
# def filter_by_today(csv_content: str) -> str:
#     import csv
#     import io
#     from datetime import date
#
#     today = date.today().isoformat()
#     reader = csv.DictReader(io.StringIO(csv_content))
#     output = io.StringIO()
#     writer = csv.DictWriter(output, fieldnames=reader.fieldnames)
#     writer.writeheader()
#     for row in reader:
#         if row.get("date", "").startswith(today):
#             writer.writerow(row)
#     return output.getvalue()

sheet_filters: dict[str, Callable[[str], str]] = {
    # Add your filter functions here, keyed by topic_id
    # Example:
    # "topic_01_major_issues": filter_by_today,
}
