from llama_deploy import (
    deploy_core,
    ControlPlaneConfig,
    SimpleMessageQueueConfig,
)


async def main():
    await deploy_core(
        control_plane_config=ControlPlaneConfig(host='0.0.0.0', port=8000),
        message_queue_config=SimpleMessageQueueConfig(host='0.0.0.0', port=8001),
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())