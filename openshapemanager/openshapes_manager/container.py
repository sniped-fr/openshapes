import docker
import os
import shutil
import datetime
from typing import Dict, Tuple

class ContainerManager:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.docker_client = docker.from_env()
        self.active_bots = {}

    async def refresh_bot_list(self) -> None:
        try:
            containers = self.docker_client.containers.list(all=True)
            self.active_bots = {}

            for container in containers:
                if container.labels.get("managed_by") == "openshapes_manager":
                    user_id = container.labels.get("user_id")
                    bot_name = container.labels.get("bot_name")

                    if user_id and bot_name:
                        if user_id not in self.active_bots:
                            self.active_bots[user_id] = {}

                        self.active_bots[user_id][bot_name] = {
                            "container_id": container.id,
                            "status": container.status,
                            "created": container.attrs.get("Created"),
                            "name": container.name,
                        }

            self.logger.info(
                f"Refreshed bot list: {len(self.active_bots)} users with active bots"
            )
        except Exception as e:
            self.logger.error(f"Error refreshing bot list: {e}")

    def get_user_bots(self, user_id: str) -> Dict[str, dict]:
        return self.active_bots.get(user_id, {})

    def get_user_bot_count(self, user_id: str) -> int:
        return len(self.get_user_bots(user_id))

    async def run_parser_container(self, bot_dir: str, parser_src: str) -> Tuple[bool, str]:
        try:
            config_path = os.path.join(bot_dir, "config.json")
            if not os.path.exists(config_path):
                return False, "config.json not found"

            parser_dest = os.path.join(bot_dir, "parser.py")

            try:
                shutil.copyfile(parser_src, parser_dest)
                self.logger.info(f"Copied parser.py from {parser_src} to {parser_dest}")
            except Exception as e:
                self.logger.error(f"Failed to copy parser.py: {e}")
                return False, f"Failed to copy parser.py: {str(e)}"

            parser_script = """
import os
import sys
import traceback

try:
    print(f"Working directory: {os.getcwd()}")
    print(f"Files in current directory: {os.listdir('.')}")
    
    import parser
    
    parser.main()
    
except Exception as e:
    print(f"ERROR IN PARSER: {str(e)}")
    traceback.print_exc()
    sys.exit(1)
    """

            parser_script_path = os.path.join(bot_dir, "run_parser.py")
            with open(parser_script_path, "w") as f:
                f.write(parser_script)

            self.logger.info(f"Running parser in directory: {os.path.abspath(bot_dir)}")

            container = self.docker_client.containers.run(
                image=self.config["docker_base_image"],
                command="python run_parser.py",
                volumes={
                    os.path.abspath(bot_dir): {"bind": "/app/selfhost", "mode": "rw"}
                },
                working_dir="/app/selfhost",
                remove=False,
                detach=True,
                environment={
                    "PYTHONPATH": "/app/selfhost"
                },
            )

            self.logger.info(f"Created parser container with ID: {container.id}")

            try:
                result = container.wait(timeout=30)
                self.logger.info(f"Container exit result: {result}")

                logs = container.logs().decode("utf-8")
                self.logger.info(f"Container logs: {logs}")

                try:
                    container.remove()
                except Exception as e:
                    self.logger.warning(f"Failed to remove container: {e}")

            except Exception as e:
                self.logger.error(f"Error waiting for container: {e}")
                try:
                    logs = container.logs().decode("utf-8")
                    self.logger.info(f"Container logs after wait error: {logs}")

                    container.stop(timeout=5)
                    container.remove()
                except Exception as cleanup_error:
                    self.logger.warning(f"Error during container cleanup: {cleanup_error}")
                return False, f"Error waiting for parser container: {str(e)}"

            try:
                os.remove(parser_script_path)
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary script: {e}")

            if result["StatusCode"] != 0:
                return (
                    False,
                    f"Parser failed with exit code {result['StatusCode']}:\n{logs}",
                )

            if not os.path.exists(os.path.join(bot_dir, "character_config.json")):
                return (
                    False,
                    f"Parser did not generate character_config.json. Logs:\n{logs}",
                )

            return True, "Parser ran successfully"

        except Exception as e:
            self.logger.error(f"Error running parser: {e}")
            return False, f"Error running parser: {str(e)}"

    async def start_bot_container(
        self, user_id: str, bot_name: str, bot_dir: str
    ) -> Tuple[bool, str]:
        try:
            container_name = f"openshape_{user_id}_{bot_name}"

            try:
                existing = self.docker_client.containers.get(container_name)
                if existing.status != "running":
                    existing.remove()
                else:
                    return False, f"Container {container_name} is already running"
            except docker.errors.NotFound:
                pass

            volumes = {os.path.abspath(bot_dir): {"bind": "/app/config", "mode": "rw"}}

            character_data_dir = os.path.join(bot_dir, "character_data")
            os.makedirs(character_data_dir, exist_ok=True)

            environment = {
                "OPENSHAPE_BOT_NAME": bot_name,
                "OPENSHAPE_USER_ID": user_id,
                "OPENSHAPE_CONFIG_DIR": "/app/config",
            }

            startup_script = "#!/bin/bash\n"
            startup_script += "cp -v /app/config/character_config.json /app/selfhost/\n"
            startup_script += "cp -v /app/config/config.json /app/selfhost/\n"
            startup_script += "if [ -f /app/config/brain.json ]; then\n"
            startup_script += "    cp -v /app/config/brain.json /app/selfhost/\n"
            startup_script += "fi\n"
            startup_script += "\n"
            startup_script += "mkdir -p /app/selfhost/character_data\n"
            startup_script += "\n"
            startup_script += "if [ -d /app/config/character_data ]; then\n"
            startup_script += "    cp -rv /app/config/character_data/* /app/selfhost/character_data/\n"
            startup_script += "fi\n"
            startup_script += "\n"
            startup_script += "cd /app/selfhost\n"
            startup_script += "python bot.py\n"

            script_path = os.path.join(bot_dir, "start_bot.sh")
            with open(script_path, "w", newline='\n') as f:
                f.write(startup_script)

            os.chmod(script_path, 0o755)

            container = self.docker_client.containers.run(
                image=self.config["docker_base_image"],
                name=container_name,
                volumes=volumes,
                environment=environment,
                command=["/bin/bash", "/app/config/start_bot.sh"],
                detach=True,
                restart_policy={"Name": "unless-stopped"},
                labels={
                    "managed_by": "openshapes_manager",
                    "user_id": user_id,
                    "bot_name": bot_name,
                },
            )

            self.logger.info(f"Started container {container_name} with ID {container.id}")

            return True, f"Container {container_name} started"

        except Exception as e:
            self.logger.error(f"Error starting container: {e}")
            return False, f"Error starting container: {str(e)}"

    async def start_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        try:
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, f"Bot {bot_name} not found"

            container_id = user_bots[bot_name]["container_id"]
            container = self.docker_client.containers.get(container_id)

            if container.status == "running":
                return False, f"Bot {bot_name} is already running"

            container.start()
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} started"

        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            return False, f"Error starting bot: {str(e)}"

    async def stop_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        try:
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, f"Bot {bot_name} not found"

            container_id = user_bots[bot_name]["container_id"]
            container = self.docker_client.containers.get(container_id)

            if container.status != "running":
                return False, f"Bot {bot_name} is not running"

            container.stop(timeout=10)
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} stopped"

        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")
            return False, f"Error stopping bot: {str(e)}"

    async def restart_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        try:
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, f"Bot {bot_name} not found"

            container_id = user_bots[bot_name]["container_id"]
            container = self.docker_client.containers.get(container_id)
            container.restart(timeout=10)
            await self.refresh_bot_list()

            return True, f"Bot {bot_name} restarted"

        except Exception as e:
            self.logger.error(f"Error restarting bot: {e}")
            return False, f"Error restarting bot: {str(e)}"

    async def delete_bot(self, user_id: str, bot_name: str, is_admin: bool, bot_dir: str) -> Tuple[bool, str]:
        try:
            if not is_admin:
                user_bots = self.get_user_bots(user_id)
                if bot_name not in user_bots:
                    return False, f"Bot {bot_name} not found"

            all_bots = self.active_bots.get(user_id, {})
            if bot_name not in all_bots:
                return False, f"Bot {bot_name} not found for user {user_id}"

            container_id = all_bots[bot_name]["container_id"]

            try:
                container = self.docker_client.containers.get(container_id)

                if container.status == "running":
                    container.stop(timeout=5)

                container.remove()
                self.logger.info(f"Removed container for bot {bot_name}")
            except Exception as e:
                self.logger.warning(f"Error removing container: {e}")

            try:
                shutil.rmtree(bot_dir)
                self.logger.info(f"Removed directory for bot {bot_name}: {bot_dir}")
            except Exception as e:
                self.logger.error(f"Error removing bot directory: {e}")
                return False, f"Error removing bot directory: {str(e)}"

            await self.refresh_bot_list()

            return True, f"Bot {bot_name} deleted successfully"

        except Exception as e:
            self.logger.error(f"Error deleting bot: {e}")
            return False, f"Error deleting bot: {str(e)}"

    async def get_bot_logs(
        self, user_id: str, bot_name: str, lines: int = 20, is_admin: bool = False
    ) -> Tuple[bool, str]:
        try:
            if not is_admin:
                user_bots = self.get_user_bots(user_id)
                if bot_name not in user_bots:
                    return False, f"Bot {bot_name} not found"

            all_bots = self.active_bots.get(user_id, {})
            if bot_name not in all_bots:
                return False, f"Bot {bot_name} not found for user {user_id}"

            container_id = all_bots[bot_name]["container_id"]
            container = self.docker_client.containers.get(container_id)
            logs = container.logs(tail=lines).decode("utf-8")

            if not logs:
                logs = "No logs available"

            return True, logs

        except Exception as e:
            self.logger.error(f"Error getting bot logs: {e}")
            return False, f"Error getting bot logs: {str(e)}"

    async def get_bot_stats(self, user_id: str, bot_name: str) -> Tuple[bool, dict]:
        try:
            user_bots = self.get_user_bots(user_id)
            if bot_name not in user_bots:
                return False, None

            container_id = user_bots[bot_name]["container_id"]
            container = self.docker_client.containers.get(container_id)
            stats = container.stats(stream=False)

            cpu_delta = (
                stats["cpu_stats"]["cpu_usage"]["total_usage"]
                - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            )
            system_delta = (
                stats["cpu_stats"]["system_cpu_usage"]
                - stats["precpu_stats"]["system_cpu_usage"]
            )
            cpu_count = (
                len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])
                if "percpu_usage" in stats["cpu_stats"]["cpu_usage"]
                else 1
            )

            cpu_percent = 0
            if system_delta > 0 and cpu_delta > 0:
                cpu_percent = (cpu_delta / system_delta) * cpu_count * 100

            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 1)
            memory_percent = (
                (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
            )

            started_at = container.attrs.get("State", {}).get("StartedAt", "")
            if started_at:
                start_time = datetime.datetime.fromisoformat(
                    started_at.replace("Z", "+00:00")
                )
                uptime = datetime.datetime.now(datetime.timezone.utc) - start_time
                uptime_str = str(uptime).split(".")[0]
            else:
                uptime_str = "Unknown"

            if memory_usage < 1024 * 1024:
                memory_usage_str = f"{memory_usage / 1024:.2f} KB"
            else:
                memory_usage_str = f"{memory_usage / (1024 * 1024):.2f} MB"

            return True, {
                "status": container.status,
                "uptime": uptime_str,
                "container_id": container_id[:12],
                "cpu_percent": f"{cpu_percent:.2f}%",
                "memory_usage": memory_usage_str,
                "memory_percent": f"{memory_percent:.2f}%",
            }

        except Exception as e:
            self.logger.error(f"Error getting bot stats: {e}")
            return False, None

    def pull_base_image(self) -> Tuple[bool, str]:
        try:
            image = self.docker_client.images.pull(self.config["docker_base_image"])
            self.logger.info(f"Updated base image: {image.id}")
            return True, f"Base image updated to: {image.id}"
        except Exception as e:
            self.logger.error(f"Error updating base image: {e}")
            return False, f"Error updating base image: {str(e)}"
