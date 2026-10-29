import asyncio

from viam.module.module import Module

# Imported to register the model with Viam's resource registry.
from models.hackathon_greenhouse_demo import HackathonGreenhouseDemo  # noqa: F401

if __name__ == "__main__":
    asyncio.run(Module.run_from_registry())
