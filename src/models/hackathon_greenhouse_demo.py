from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple)
import asyncio
import threading
from datetime import datetime, timedelta

from typing_extensions import Self

from viam.components.generic import *
from viam.components.board import Board
from viam.components.sensor import Sensor
from viam.components.switch import Switch
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import Geometry, ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import ValueTypes


class HackathonGreenhouseDemo(Generic, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(
        ModelFamily("viam", "greenhouse"), "hackathon-greenhouse-demo"
    )
    dependencies: Mapping[ResourceName, ResourceBase]
    stop_event: threading.Event
    fan_thread: Optional[threading.Thread]
    watering_thread: Optional[threading.Thread]
    lights_thread: Optional[threading.Thread]

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        """This method creates a new instance of this Generic component.
        The default implementation sets the name from the `config` parameter.

        Args:
            config (ComponentConfig): The configuration for this resource
            dependencies (Mapping[ResourceName, ResourceBase]): The dependencies (both required and optional)

        Returns:
            Self: The resource
        """

        result = super().new(config, dependencies)
        result.reconfigure(config, dependencies)

        return result

    def reconfigure(
        self,
        config: ComponentConfig,
        dependencies: Mapping[ResourceName, ResourceBase],
    ):
        self.dependencies = dependencies
        attrs = config.attributes.fields

        self.lights_on_hour = (
            int(attrs["lights_on_hour"].number_value)
            if "lights_on_hour" in attrs
            else 7
        )
        self.lights_off_hour = (
            int(attrs["lights_off_hour"].number_value)
            if "lights_off_hour" in attrs
            else 22
        )
        self.fan_on_above_humidity = (
            int(attrs["fan_on_above_humidity"].number_value)
            if "fan_on_above_humidity" in attrs
            else 70
        )
        self.fan_off_below_humidity = (
            int(attrs["fan_off_below_humidity"].number_value)
            if "fan_off_below_humidity" in attrs
            else 40
        )
        self.maintain_soil_moisture_level = (
            int(attrs["maintain_soil_moisture_level"].number_value)
            if "maintain_soil_moisture_level" in attrs
            else 1000
        )

        self.alert_above_humidity: Optional[int] = None
        self.alert_below_humidity: Optional[int] = None
        if "alerts" in attrs:
            alert_fields = attrs["alerts"].struct_value.fields
            if "above_humidity" in alert_fields:
                self.alert_above_humidity = int(
                    alert_fields["above_humidity"].number_value
                )
            if "below_humidity" in alert_fields:
                self.alert_below_humidity = int(
                    alert_fields["below_humidity"].number_value
                )

        # Stop existing background threads if they exist
        if hasattr(self, 'stop_event'):
            old_stop_event = self.stop_event
            old_stop_event.set()

            # Give old threads a moment to notice the stop event and exit
            # They check every second in their sleep loops
            import time
            time.sleep(2)

        # Create new stop event for the new threads
        self.stop_event = threading.Event()

        # Restart control threads
        self.control_fan()
        self.water_plants()
        self.control_lights()

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """This method allows you to validate the configuration object received from the machine,
        as well as to return any required dependencies or optional dependencies based on that `config`.

        Args:
            config (ComponentConfig): The configuration for this resource

        Returns:
            Tuple[Sequence[str], Sequence[str]]: A tuple where the
                first element is a list of required dependencies and the
                second element is a list of optional dependencies
        """
        attrs = config.attributes.fields

        int_fields = [
            "lights_on_hour",
            "lights_off_hour",
            "fan_on_above_humidity",
            "fan_off_below_humidity",
        ]
        for field in int_fields:
            if field in attrs:
                val = attrs[field]
                if val.WhichOneof("kind") != "number_value" or val.number_value % 1 != 0:
                    raise ValueError(f'"{field}" must be an int')

        if "alerts" in attrs:
            if attrs["alerts"].WhichOneof("kind") != "struct_value":
                raise ValueError('"alerts" must be a map')
            alert_fields = attrs["alerts"].struct_value.fields
            for alert_field in ["above_humidity", "below_humidity"]:
                if alert_field in alert_fields:
                    val = alert_fields[alert_field]
                    if val.WhichOneof("kind") != "number_value" or val.number_value % 1 != 0:
                        raise ValueError(f'"alerts.{alert_field}" must be an int')

        req_deps = []
        fields = config.attributes.fields

        if "gas_sensor_name" not in fields:
            raise Exception("missing required gas_sensor_name attribute")
        elif not fields["gas_sensor_name"].HasField("string_value"):
            raise Exception("gas_sensor_name must be a string")
        gas_sensor_name = fields["gas_sensor_name"].string_value
        if not gas_sensor_name:
            raise ValueError("gas_sensor_name cannot be empty")
        req_deps.append(gas_sensor_name)

        return req_deps, []

    async def toggle_light(self, position: int):
        """Set the light smart plug switch to the specified position (0 or 1)."""
        if position not in (0, 1):
            raise ValueError(f"Invalid position {position}. Must be 0 or 1.")
        for resource_name, resource in self.dependencies.items():
            if resource_name.name == "light-smart-plug":
                light_switch = resource
                if isinstance(light_switch, Switch):
                    await light_switch.set_position(position)
                    return
        raise ValueError("light-smart-plug not found in dependencies")

    async def turn_light_off(self):
        """Turn off the light."""
        self.logger.info("turning light off")
        await self.toggle_light(0)

    async def turn_light_on(self):
        """Turn on the light."""
        self.logger.info("turning light on")
        await self.toggle_light(1)

    async def check_humidity(self) -> float:
        """Get the current relative humidity from the temperature/moisture sensor."""
        for resource_name, resource in self.dependencies.items():
            if resource_name.name == "temp-moisture-sensor":
                sensor = resource
                if isinstance(sensor, Sensor):
                    readings = await sensor.get_readings()
                    if "relative_humidity" in readings:
                        self.logger.info(f"returning humidity {readings["relative_humidity"]}")
                        return readings["relative_humidity"]
                    raise KeyError("relative_humidity not found in sensor readings")
        raise ValueError("temp-moisture-sensor not found in dependencies")

    async def check_moisture(self) -> float:
        """Get the average moisture level from all soil sensors."""
        moisture_readings = []

        for resource_name, resource in self.dependencies.items():
            if "soil-sensor" in resource_name.name:
                if isinstance(resource, Sensor):
                    readings = await resource.get_readings()
                    if "moisture" in readings:
                        moisture_readings.append(readings["moisture"])
                    else:
                        self.logger.warning(f"Sensor {resource_name.name} does not have 'moisture' reading")

        if not moisture_readings:
            raise ValueError("No soil sensors with moisture readings found in dependencies")

        return sum(moisture_readings) / len(moisture_readings)

    def control_fan(self):
        """Start a background thread to control the fan based on humidity."""
        # Get the main_board from dependencies
        main_board = None
        for resource_name, resource in self.dependencies.items():
            if resource_name.name == "main_board":
                if isinstance(resource, Board):
                    main_board = resource
                    break

        if main_board is None:
            raise ValueError("main_board not found in dependencies")

        def fan_control_loop():
            """Background thread loop to monitor humidity and control fan."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def monitor():
                while not self.stop_event.is_set():
                    self.logger.info("at start of fan control loop")
                    try:
                        humidity = await self.check_humidity()
                        gpio_pin = await main_board.gpio_pin_by_name("11")

                        if humidity > self.fan_on_above_humidity:
                            await gpio_pin.set(True)
                        elif humidity < self.fan_off_below_humidity:
                            await gpio_pin.set(False)

                        # Sleep in small intervals to check stop_event more frequently
                        for _ in range(60):
                            if self.stop_event.is_set():
                                break
                            await asyncio.sleep(1)
                    except Exception as e:
                        self.logger.error(f"Error in fan control loop: {e}")
                        await asyncio.sleep(60)

            loop.run_until_complete(monitor())

        thread = threading.Thread(target=fan_control_loop, daemon=True)
        thread.start()

    def water_plants(self):
        """Start a background thread to water plants based on soil moisture."""
        # Get the main_board from dependencies
        main_board = None
        for resource_name, resource in self.dependencies.items():
            if resource_name.name == "main_board":
                if isinstance(resource, Board):
                    main_board = resource
                    break

        if main_board is None:
            raise ValueError("main_board not found in dependencies")

        def watering_loop():
            """Background thread loop to monitor soil moisture and water plants."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def monitor():
                while not self.stop_event.is_set():
                    self.logger.info("in watering loop")
                    try:
                        moisture = await self.check_moisture()

                        if moisture < self.maintain_soil_moisture_level:
                            gpio_pin = await main_board.gpio_pin_by_name("13")
                            # Turn on water pump
                            await gpio_pin.set(True)
                            # Wait 1 minute
                            await asyncio.sleep(60)
                            # Turn off water pump
                            await gpio_pin.set(False)

                        # Sleep in small intervals to check stop_event more frequently
                        for _ in range(900):
                            if self.stop_event.is_set():
                                break
                            await asyncio.sleep(1)
                    except Exception as e:
                        self.logger.error(f"Error in watering loop: {e}")
                        await asyncio.sleep(900)

            loop.run_until_complete(monitor())

        thread = threading.Thread(target=watering_loop, daemon=True)
        thread.start()

    def control_lights(self):
        """Start a background thread to control lights based on schedule."""
        def light_control_loop():
            """Background thread loop to turn lights on and off at scheduled times."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def monitor():
                while not self.stop_event.is_set():
                    self.logger.info("at start of control lights loop")
                    try:
                        now = datetime.now()
                        current_hour = now.hour

                        # Determine next action
                        if current_hour < self.lights_on_hour:
                            # Before lights on time, wait until lights on hour
                            target_hour = self.lights_on_hour
                            action = "on"
                        elif current_hour < self.lights_off_hour:
                            # Between on and off time, wait until lights off hour
                            target_hour = self.lights_off_hour
                            action = "off"
                        else:
                            # After lights off time, wait until tomorrow's lights on hour
                            target_hour = self.lights_on_hour
                            action = "on"

                        # Calculate sleep time
                        if action == "on" and current_hour >= self.lights_off_hour:
                            # Need to wait until tomorrow
                            target_time = (now + timedelta(days=1)).replace(hour=target_hour, minute=0, second=0, microsecond=0)
                        else:
                            target_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)

                        sleep_seconds = (target_time - now).total_seconds()

                        # Sleep in intervals to check stop_event
                        if sleep_seconds > 0:
                            elapsed = 0
                            while elapsed < sleep_seconds and not self.stop_event.is_set():
                                sleep_chunk = min(60, sleep_seconds - elapsed)
                                await asyncio.sleep(sleep_chunk)
                                elapsed += sleep_chunk

                        if self.stop_event.is_set():
                            break

                        # Perform action
                        if action == "on":
                            await self.turn_light_on()
                        else:
                            await self.turn_light_off()

                    except Exception as e:
                        self.logger.error(f"Error in light control loop: {e}")
                        await asyncio.sleep(60)

            loop.run_until_complete(monitor())

        thread = threading.Thread(target=light_control_loop, daemon=True)
        thread.start()

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        return {"hello": "world"}
        self.logger.error("`do_command` is not implemented")
        raise NotImplementedError()

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> Sequence[Geometry]:
        self.logger.error("`get_geometries` is not implemented")
        raise NotImplementedError()

