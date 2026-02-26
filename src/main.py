import asyncio
from viam.module.module import Module
from models.hackathon_greenhouse_demo import HackathonGreenhouseDemo


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())

    # call readings method from sensor module
