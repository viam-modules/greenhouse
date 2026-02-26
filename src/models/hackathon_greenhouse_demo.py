from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple)

from typing_extensions import Self

from viam.components.generic import *
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

        return [], []

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        self.logger.error("`do_command` is not implemented")
        raise NotImplementedError()

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> Sequence[Geometry]:
        self.logger.error("`get_geometries` is not implemented")
        raise NotImplementedError()

