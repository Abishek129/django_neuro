from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .services.hwmon_service import (
    parse_sensors,
    get_pwm_controls,
    set_pwm_value,
    set_pwm_mode,
    check_ipmi_available,
    get_ipmi_sensors,
    get_ipmi_chassis_status,
    get_ipmi_sel,
    get_system_info,
    get_power_status,
    get_bmc_status,
    get_bmc_history,
    clear_bmc_history,
    get_sensors_data2,
)

# ------------------- Core endpoints (match cpu/memory/gpu/disk pattern) -------------------

@api_view(["GET"])
def get_status(request):
    """Get current BMC/hardware sensor status (main endpoint)."""
    return Response(get_bmc_status())


@api_view(["GET"])
def get_history(request):
    """Get BMC sensor history from Redis."""
    return Response(get_bmc_history())


@api_view(["DELETE"])
def clear_history(request):
    """Clear BMC history from Redis."""
    return Response(clear_bmc_history())


# ------------------- Live readings (DB-free) -------------------

@api_view(["GET"])
def live_sensors(request):
    # Direct pull only (no DB, no aliases)
    return Response(parse_sensors())

@api_view(["GET"])
def available_sensors(request):
    """
    DB-free version of list_available_sensors().
    Returns a flattened list of sensors from parse_sensors().
    """
    data = parse_sensors()
    sensors = []

    for fan in data.get("fans", []):
        sensors.append({
            "sensor_type": "fan",
            "chip": fan["chip"],
            "sensor_name": fan["name"],
            "default_label": fan.get("label"),
            "current_value": fan.get("rpm"),
            "unit": "RPM",
        })

    for temp in data.get("temperatures", []):
        sensors.append({
            "sensor_type": "temperature",
            "chip": temp["chip"],
            "sensor_name": temp["name"],
            "default_label": temp.get("label"),
            "current_value": temp.get("current"),
            "unit": "°C",
        })

    for volt in data.get("voltages", []):
        sensors.append({
            "sensor_type": "voltage",
            "chip": volt["chip"],
            "sensor_name": volt["name"],
            "default_label": volt.get("label"),
            "current_value": volt.get("voltage"),
            "unit": "V",
        })

    for pwm in data.get("pwm_controls", []):
        sensors.append({
            "sensor_type": "pwm",
            "chip": pwm["chip"],
            "sensor_name": pwm["name"],
            "default_label": pwm.get("label"),
            "current_value": pwm.get("percent"),
            "unit": "%",
            "enable_mode": pwm.get("enable_mode_name"),
        })

    for intr in data.get("intrusions", []):
        sensors.append({
            "sensor_type": "intrusion",
            "chip": intr["chip"],
            "sensor_name": intr["name"],
            "default_label": intr.get("name"),
            "current_value": intr.get("alarm"),
            "unit": "alarm",
        })

    return Response({
        "sensors": sensors,
        "count": len(sensors),
        "timestamp": data.get("timestamp"),
    })

@api_view(["GET"])
def pwm_controls(request):
    return Response({"controls": get_pwm_controls()})


# ------------------- Fan control (DB-free) -------------------

@api_view(["POST"])
def pwm_set_value(request):
    hwmon_path = request.data.get("hwmon_path")
    pwm_name = request.data.get("pwm_name")
    value = request.data.get("value")

    if not hwmon_path or not pwm_name or value is None:
        return Response(
            {"error": "hwmon_path, pwm_name, value are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        value = int(value)
    except ValueError:
        return Response({"error": "value must be an integer"}, status=400)

    return Response(set_pwm_value(hwmon_path, pwm_name, value))


@api_view(["POST"])
def pwm_set_mode(request):
    hwmon_path = request.data.get("hwmon_path")
    pwm_name = request.data.get("pwm_name")
    mode = request.data.get("mode")

    if not hwmon_path or not pwm_name or mode is None:
        return Response(
            {"error": "hwmon_path, pwm_name, mode are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        mode = int(mode)
    except ValueError:
        return Response({"error": "mode must be an integer"}, status=400)

    return Response(set_pwm_mode(hwmon_path, pwm_name, mode))


# ------------------- IPMI / system info (DB-free) -------------------

@api_view(["GET"])
def ipmi_status(request):
    return Response({"available": check_ipmi_available()})

@api_view(["GET"])
def ipmi_sensors(request):
    if not check_ipmi_available():
        return Response({"available": False, "sensors": []})
    return Response({"available": True, "sensors": get_ipmi_sensors()})

@api_view(["GET"])
def ipmi_chassis(request):
    return Response(get_ipmi_chassis_status())

@api_view(["GET"])
def ipmi_sel(request):
    count = int(request.query_params.get("count", "20"))
    return Response({"events": get_ipmi_sel(count)})

@api_view(["GET"])
def system_info(request):
    return Response(get_system_info())

@api_view(["GET"])
def power_status(request):
    return Response(get_power_status())


@api_view(["GET"])
def raw_sensors(request):
    """Get raw sensor data directly from lm-sensors (sensors -j output)."""
    return Response(get_sensors_data2())
