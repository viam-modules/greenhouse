# Module greenhouse

Provide a description of the purpose of the module and any relevant information.

## Models

This module provides the following model(s):

- [`viam:greenhouse:hackathon-greenhouse-demo`](viam_greenhouse_hackathon-greenhouse-demo.md) - Provide a brief description of the model

### Configuration

The following attribute template can be used to configure this model.

```json
{
    "lights_on_hour": <int>,
    "lights_off_hour": <int>,
    "fan_on_above_humidity": <int>,
    "fan_off_below_humidity": <int>,
    "alerts": {
        "above_humidity": <int>,
        "below_humidity": <int>,
    }
}
```

#### Attributes

| Name          | Type        | Inclusion        | Description         |
|---------------|-------------|------------------|---------------------|
| `lights_on_hour` |int         | Optional         | 24 hour local clock hour to turn on lights. Default 7 |
| `lights_off_hour` |int         | Optional         | 24 hour local clock hour to turn off lights. Default 22 |
| `fan_on_above_humidity` | int     | Optional         | Fan goes on above this humidity (default 70)             |
| `fan_off_below_humidity` | int     | Optional         | Fan goes off above this humidity (default 40)             |
| `alerts`  |   map[string, int]    | Optional  | Thresholds for above_humidity and below_humidity which send an email |

#### Example configuration


```json
{
    "lights_on_hour": 7,
    "lights_off_hour": 22,
    "fan_on_above_humidity": 65,
    "fan_off_below_humidity": 40,
    "alerts": {
        "above_humidity": 70,
        "below_humidity": 15,
    }
}
```

