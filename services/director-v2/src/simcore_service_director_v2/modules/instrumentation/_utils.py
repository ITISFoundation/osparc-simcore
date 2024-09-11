from ...models.dynamic_services_scheduler import SchedulerData


def get_start_stop_labels(scheduler_data: SchedulerData) -> dict[str, str]:
    return {
        "user_id": f"{scheduler_data.user_id}",
        "wallet_id": (
            f"{scheduler_data.wallet_info.wallet_id}"
            if scheduler_data.wallet_info
            else ""
        ),
        "service_key": scheduler_data.key,
        "service_version": scheduler_data.version,
    }
