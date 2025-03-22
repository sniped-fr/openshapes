import docker
import os
import shutil
import datetime
from typing import Dict, Tuple, Any, Optional, Union
from docker.models.containers import Container

class DockerClientFactory:
    @staticmethod
    def create_client():
        return docker.from_env()

class ContainerRegistry:
    def __init__(self):
        self.active_bots: Dict[str, Dict[str, Dict[str, Any]]] = {}
    
    def register_bot(self, user_id: str, bot_name: str, container_data: Dict[str, Any]) -> None:
        if user_id not in self.active_bots:
            self.active_bots[user_id] = {}
        
        self.active_bots[user_id][bot_name] = container_data
    
    def clear(self) -> None:
        self.active_bots = {}
    
    def get_user_bots(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        return self.active_bots.get(user_id, {})
    
    def get_user_bot_count(self, user_id: str) -> int:
        return len(self.get_user_bots(user_id))
    
    def get_bot(self, user_id: str, bot_name: str) -> Optional[Dict[str, Any]]:
        user_bots = self.get_user_bots(user_id)
        return user_bots.get(bot_name)

class ScriptBuilder:
    @staticmethod
    def create_parser_runner_script() -> str:
        return """
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
    
    @staticmethod
    def create_bot_startup_script() -> str:
        startup_script = "#!/bin/bash\n"
        startup_script += "# Create necessary directory structure\n"
        startup_script += "mkdir -p /app/bot/character_data\n\n"
        
        startup_script += "# Copy configuration files to the proper locations\n"
        startup_script += "cp -v /app/config/character_config.json /app/bot/\n"
        
        startup_script += "if [ -d /app/config/character_data ]; then\n"
        startup_script += "    cp -rv /app/config/character_data/* /app/bot/character_data/\n"
        startup_script += "fi\n\n"
        
        startup_script += "# Set debug flag if needed\n"
        startup_script += "DEBUG_FLAG=\"\"\n"
        startup_script += "if [ \"$DEBUG\" = \"true\" ]; then\n"
        startup_script += "    DEBUG_FLAG=\"--debug\"\n"
        startup_script += "fi\n\n"
        
        startup_script += "# Change to bot directory and run the bot using run.sh\n"
        startup_script += "cd /app/bot\n"
        startup_script += "bash run.sh --config character_config.json $DEBUG_FLAG\n"
        
        return startup_script

class ContainerOperationResult:
    def __init__(self, success: bool, message: str, data: Any = None):
        self.success = success
        self.message = message
        self.data = data
    
    def to_tuple(self) -> Tuple[bool, Union[str, Any]]:
        return self.success, self.data if self.data is not None else self.message

class ContainerOperationExecutor:
    def __init__(self, logger, docker_client, config: Dict[str, Any]):
        self.logger = logger
        self.docker_client = docker_client
        self.config = config
    
    def handle_exception(self, operation: str, e: Exception) -> ContainerOperationResult:
        error_message = f"Error during {operation}: {str(e)}"
        self.logger.error(error_message)
        return ContainerOperationResult(False, error_message)
    
    def get_container(self, container_id: str) -> Optional[Container]:
        try:
            return self.docker_client.containers.get(container_id)
        except docker.errors.NotFound:
            return None
        except Exception as e:
            self.logger.error(f"Error getting container {container_id}: {str(e)}")
            return None

class ParserOperations(ContainerOperationExecutor):
    def __init__(self, logger, docker_client, config: Dict[str, Any]):
        super().__init__(logger, docker_client, config)
        self.script_builder = ScriptBuilder()
    
    async def run_parser_container(self, bot_dir: str, parser_src: str) -> Tuple[bool, str]:
        try:
            if not self._validate_config_exists(bot_dir):
                return False, "config.json not found"
            
            parser_dest = os.path.join(bot_dir, "parser.py")
            if not self._copy_parser_file(parser_src, parser_dest):
                return False, "Failed to copy parser.py"
            
            parser_script_path = self._create_parser_script(bot_dir)
            
            self.logger.info(f"Running parser in directory: {os.path.abspath(bot_dir)}")
            
            container = self._launch_parser_container(bot_dir)
            if not container:
                return False, "Failed to create parser container"
            
            self.logger.info(f"Created parser container with ID: {container.id}")
            
            result, logs = self._wait_for_container_completion(container)
            self._cleanup_temp_files(parser_script_path)
            
            if not result["StatusCode"] == 0:
                return False, f"Parser failed with exit code {result['StatusCode']}:\n{logs}"
            
            if not os.path.exists(os.path.join(bot_dir, "character_config.json")):
                return False, f"Parser did not generate character_config.json. Logs:\n{logs}"
            
            return True, "Parser ran successfully"
            
        except Exception as e:
            return self.handle_exception("parser container operation", e).to_tuple()
    
    def _validate_config_exists(self, bot_dir: str) -> bool:
        config_path = os.path.join(bot_dir, "config.json")
        return os.path.exists(config_path)
    
    def _copy_parser_file(self, parser_src: str, parser_dest: str) -> bool:
        try:
            shutil.copyfile(parser_src, parser_dest)
            self.logger.info(f"Copied parser.py from {parser_src} to {parser_dest}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to copy parser.py: {e}")
            return False
    
    def _create_parser_script(self, bot_dir: str) -> str:
        parser_script = self.script_builder.create_parser_runner_script()
        parser_script_path = os.path.join(bot_dir, "run_parser.py")
        
        with open(parser_script_path, "w") as f:
            f.write(parser_script)
            
        return parser_script_path
    
    def _launch_parser_container(self, bot_dir: str) -> Optional[Container]:
        try:
            return self.docker_client.containers.run(
                image=self.config["docker_base_image"],
                command="python run_parser.py",
                volumes={
                    os.path.abspath(bot_dir): {"bind": "/app/bot", "mode": "rw"}
                },
                working_dir="/app/bot",
                remove=False,
                detach=True,
                environment={
                    "PYTHONPATH": "/app/bot"
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to launch parser container: {e}")
            return None
    
    def _wait_for_container_completion(self, container: Container) -> Tuple[Dict[str, Any], str]:
        try:
            result = container.wait(timeout=30)
            logs = container.logs().decode("utf-8")
            self.logger.info(f"Container exit result: {result}")
            self.logger.info(f"Container logs: {logs}")
            
            try:
                container.remove()
            except Exception as e:
                self.logger.warning(f"Failed to remove container: {e}")
                
            return result, logs
            
        except Exception as e:
            self.logger.error(f"Error waiting for container: {e}")
            try:
                logs = container.logs().decode("utf-8")
                self.logger.info(f"Container logs after wait error: {logs}")
                
                container.stop(timeout=5)
                container.remove()
            except Exception as cleanup_error:
                self.logger.warning(f"Error during container cleanup: {cleanup_error}")
                
            return {"StatusCode": 1}, "Error waiting for container"
    
    def _cleanup_temp_files(self, parser_script_path: str) -> None:
        try:
            os.remove(parser_script_path)
        except Exception as e:
            self.logger.warning(f"Failed to remove temporary script: {e}")

class BotContainerOperations(ContainerOperationExecutor):
    def __init__(self, logger, docker_client, config: Dict[str, Any], registry: ContainerRegistry):
        super().__init__(logger, docker_client, config)
        self.registry = registry
        self.script_builder = ScriptBuilder()
    
    async def start_bot_container(
        self, user_id: str, bot_name: str, bot_dir: str
    ) -> Tuple[bool, str]:
        try:
            container_name = f"openshape_{user_id}_{bot_name}"

            existing = self._check_existing_container(container_name)
            if existing and existing.status == "running":
                return False, f"Container {container_name} is already running"

            self._setup_directories(bot_dir)
            volumes = {os.path.abspath(bot_dir): {"bind": "/app/config", "mode": "rw"}}
            environment = self._create_environment(bot_name, user_id)

            self._create_startup_script(bot_dir)

            container = self._launch_bot_container(container_name, volumes, environment, bot_name, user_id)
            if not container:
                return False, f"Failed to start container {container_name}"
            
            self.logger.info(f"Started container {container_name} with ID {container.id}")

            self.registry.register_bot(user_id, bot_name, {
                "container_id": container.id,
                "status": container.status,
                "name": container.name,
            })
            
            return True, f"Container {container_name} started"
            
        except Exception as e:
            return self.handle_exception("starting bot container", e).to_tuple()
    
    def _check_existing_container(self, container_name: str) -> Optional[Container]:
        try:
            existing = self.docker_client.containers.get(container_name)
            if existing.status != "running":
                existing.remove()
            return existing
        except docker.errors.NotFound:
            return None
        except Exception as e:
            self.logger.warning(f"Error checking existing container: {e}")
            return None
    
    def _setup_directories(self, bot_dir: str) -> None:
        character_data_dir = os.path.join(bot_dir, "character_data")
        os.makedirs(character_data_dir, exist_ok=True)
    
    def _create_environment(self, bot_name: str, user_id: str) -> Dict[str, str]:
        return {
            "OPENSHAPE_BOT_NAME": bot_name,
            "OPENSHAPE_USER_ID": user_id,
            "OPENSHAPE_CONFIG_DIR": "/app/config",
            "DEBUG": "false"
        }
    
    def _create_startup_script(self, bot_dir: str) -> str:
        startup_script = self.script_builder.create_bot_startup_script()
        script_path = os.path.join(bot_dir, "start_bot.sh")
        
        with open(script_path, "w", newline='\n') as f:
            f.write(startup_script)
        
        os.chmod(script_path, 0o755)
        return script_path
    
    def _launch_bot_container(
        self, 
        container_name: str, 
        volumes: Dict[str, Dict[str, str]], 
        environment: Dict[str, str],
        bot_name: str,
        user_id: str
    ) -> Optional[Container]:
        try:
            return self.docker_client.containers.run(
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
        except Exception as e:
            self.logger.error(f"Failed to launch bot container: {e}")
            return None

class BotManagementOperations(ContainerOperationExecutor):
    def __init__(self, logger, docker_client, config: Dict[str, Any], registry: ContainerRegistry):
        super().__init__(logger, docker_client, config)
        self.registry = registry
    
    async def start_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        try:
            bot_info = self._get_bot_info(user_id, bot_name)
            if not bot_info:
                return False, f"Bot {bot_name} not found"
            
            container = self.get_container(bot_info["container_id"])
            if not container:
                return False, f"Container for bot {bot_name} not found"
            
            if container.status == "running":
                return False, f"Bot {bot_name} is already running"
            
            container.start()
            
            return True, f"Bot {bot_name} started"
            
        except Exception as e:
            return self.handle_exception("starting bot", e).to_tuple()
    
    async def stop_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        try:
            bot_info = self._get_bot_info(user_id, bot_name)
            if not bot_info:
                return False, f"Bot {bot_name} not found"
            
            container = self.get_container(bot_info["container_id"])
            if not container:
                return False, f"Container for bot {bot_name} not found"
            
            if container.status != "running":
                return False, f"Bot {bot_name} is not running"
            
            container.stop(timeout=10)
            
            return True, f"Bot {bot_name} stopped"
            
        except Exception as e:
            return self.handle_exception("stopping bot", e).to_tuple()
    
    async def restart_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        try:
            bot_info = self._get_bot_info(user_id, bot_name)
            if not bot_info:
                return False, f"Bot {bot_name} not found"
            
            container = self.get_container(bot_info["container_id"])
            if not container:
                return False, f"Container for bot {bot_name} not found"
            
            container.restart(timeout=10)
            
            return True, f"Bot {bot_name} restarted"
            
        except Exception as e:
            return self.handle_exception("restarting bot", e).to_tuple()
    
    async def delete_bot(
        self, user_id: str, bot_name: str, is_admin: bool, bot_dir: str
    ) -> Tuple[bool, str]:
        try:
            if not is_admin:
                bot_info = self._get_bot_info(user_id, bot_name)
                if not bot_info:
                    return False, f"Bot {bot_name} not found"
            
            bot_info = self.registry.get_bot(user_id, bot_name)
            if not bot_info:
                return False, f"Bot {bot_name} not found for user {user_id}"
            
            self._stop_and_remove_container(bot_info["container_id"], bot_name)
            self._remove_bot_directory(bot_dir, bot_name)
            
            return True, f"Bot {bot_name} deleted successfully"
            
        except Exception as e:
            return self.handle_exception("deleting bot", e).to_tuple()
    
    async def get_bot_logs(
        self, user_id: str, bot_name: str, lines: int = 20, is_admin: bool = False
    ) -> Tuple[bool, str]:
        try:
            bot_info = self._get_bot_info_with_admin_check(user_id, bot_name, is_admin)
            if not bot_info:
                return False, f"Bot {bot_name} not found for user {user_id}"
            
            container = self.get_container(bot_info["container_id"])
            if not container:
                return False, f"Container for bot {bot_name} not found"
            
            logs = container.logs(tail=lines).decode("utf-8")
            
            if not logs:
                logs = "No logs available"
            
            return True, logs
            
        except Exception as e:
            return self.handle_exception("getting bot logs", e).to_tuple()
    
    async def get_bot_stats(self, user_id: str, bot_name: str) -> Tuple[bool, Dict[str, Any]]:
        try:
            bot_info = self._get_bot_info(user_id, bot_name)
            if not bot_info:
                return False, None
            
            container = self.get_container(bot_info["container_id"])
            if not container:
                return False, None
            
            stats = container.stats(stream=False)
            stats_data = self._process_container_stats(container, stats, bot_info["container_id"])
            
            return True, stats_data
            
        except Exception as e:
            return self.handle_exception("getting bot stats", e).to_tuple()
    
    def _get_bot_info(self, user_id: str, bot_name: str) -> Optional[Dict[str, Any]]:
        return self.registry.get_bot(user_id, bot_name)
    
    def _get_bot_info_with_admin_check(
        self, user_id: str, bot_name: str, is_admin: bool
    ) -> Optional[Dict[str, Any]]:
        if not is_admin:
            user_bots = self.registry.get_user_bots(user_id)
            if bot_name not in user_bots:
                return None
        
        return self.registry.get_bot(user_id, bot_name)
    
    def _stop_and_remove_container(self, container_id: str, bot_name: str) -> None:
        try:
            container = self.get_container(container_id)
            if container:
                if container.status == "running":
                    container.stop(timeout=5)
                
                container.remove()
                self.logger.info(f"Removed container for bot {bot_name}")
        except Exception as e:
            self.logger.warning(f"Error removing container: {e}")
    
    def _remove_bot_directory(self, bot_dir: str, bot_name: str) -> None:
        try:
            shutil.rmtree(bot_dir)
            self.logger.info(f"Removed directory for bot {bot_name}: {bot_dir}")
        except Exception as e:
            self.logger.error(f"Error removing bot directory: {e}")
            raise
    
    def _process_container_stats(
        self, container: Container, stats: Dict[str, Any], container_id: str
    ) -> Dict[str, Any]:
        cpu_stats = self._calculate_cpu_stats(stats)
        memory_stats = self._calculate_memory_stats(stats)
        uptime_stats = self._calculate_uptime(container)
        
        return {
            "status": container.status,
            "uptime": uptime_stats,
            "container_id": container_id[:12],
            "cpu_percent": f"{cpu_stats:.2f}%",
            "memory_usage": memory_stats["usage_str"],
            "memory_percent": f"{memory_stats['percent']:.2f}%",
        }
    
    def _calculate_cpu_stats(self, stats: Dict[str, Any]) -> float:
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
            
        return cpu_percent
    
    def _calculate_memory_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        memory_usage = stats["memory_stats"].get("usage", 0)
        memory_limit = stats["memory_stats"].get("limit", 1)
        memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0
        
        if memory_usage < 1024 * 1024:
            memory_usage_str = f"{memory_usage / 1024:.2f} KB"
        else:
            memory_usage_str = f"{memory_usage / (1024 * 1024):.2f} MB"
            
        return {
            "usage": memory_usage,
            "limit": memory_limit,
            "percent": memory_percent,
            "usage_str": memory_usage_str
        }
    
    def _calculate_uptime(self, container: Container) -> str:
        started_at = container.attrs.get("State", {}).get("StartedAt", "")
        if started_at:
            start_time = datetime.datetime.fromisoformat(
                started_at.replace("Z", "+00:00")
            )
            uptime = datetime.datetime.now(datetime.timezone.utc) - start_time
            return str(uptime).split(".")[0]
        
        return "Unknown"

class ContainerManager:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.docker_client = DockerClientFactory.create_client()
        self.registry = ContainerRegistry()

        self.parser_ops = ParserOperations(logger, self.docker_client, config)
        self.bot_container_ops = BotContainerOperations(logger, self.docker_client, config, self.registry)
        self.bot_mgmt_ops = BotManagementOperations(logger, self.docker_client, config, self.registry)
    
    async def refresh_bot_list(self) -> None:
        try:
            containers = self.docker_client.containers.list(all=True)
            self.registry.clear()
            
            for container in containers:
                if container.labels.get("managed_by") == "openshapes_manager":
                    user_id = container.labels.get("user_id")
                    bot_name = container.labels.get("bot_name")
                    
                    if user_id and bot_name:
                        self.registry.register_bot(user_id, bot_name, {
                            "container_id": container.id,
                            "status": container.status,
                            "created": container.attrs.get("Created"),
                            "name": container.name,
                        })
            
            self.logger.info(
                f"Refreshed bot list: {len(self.registry.active_bots)} users with active bots"
            )
        except Exception as e:
            self.logger.error(f"Error refreshing bot list: {e}")
    
    def get_user_bots(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        return self.registry.get_user_bots(user_id)
    
    def get_user_bot_count(self, user_id: str) -> int:
        return self.registry.get_user_bot_count(user_id)
    
    async def run_parser_container(self, bot_dir: str, parser_src: str) -> Tuple[bool, str]:
        result = await self.parser_ops.run_parser_container(bot_dir, parser_src)
        await self.refresh_bot_list()
        return result
    
    async def start_bot_container(
        self, user_id: str, bot_name: str, bot_dir: str
    ) -> Tuple[bool, str]:
        result = await self.bot_container_ops.start_bot_container(user_id, bot_name, bot_dir)
        await self.refresh_bot_list()
        return result
    
    async def start_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        result = await self.bot_mgmt_ops.start_bot(user_id, bot_name)
        await self.refresh_bot_list()
        return result
    
    async def stop_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        result = await self.bot_mgmt_ops.stop_bot(user_id, bot_name)
        await self.refresh_bot_list()
        return result
    
    async def restart_bot(self, user_id: str, bot_name: str) -> Tuple[bool, str]:
        result = await self.bot_mgmt_ops.restart_bot(user_id, bot_name)
        await self.refresh_bot_list()
        return result
    
    async def delete_bot(
        self, user_id: str, bot_name: str, is_admin: bool, bot_dir: str
    ) -> Tuple[bool, str]:
        result = await self.bot_mgmt_ops.delete_bot(user_id, bot_name, is_admin, bot_dir)
        await self.refresh_bot_list()
        return result
    
    async def get_bot_logs(
        self, user_id: str, bot_name: str, lines: int = 20, is_admin: bool = False
    ) -> Tuple[bool, str]:
        return await self.bot_mgmt_ops.get_bot_logs(user_id, bot_name, lines, is_admin)
    
    async def get_bot_stats(self, user_id: str, bot_name: str) -> Tuple[bool, Dict[str, Any]]:
        return await self.bot_mgmt_ops.get_bot_stats(user_id, bot_name)
    
    def pull_base_image(self) -> Tuple[bool, str]:
        try:
            image = self.docker_client.images.pull(self.config["docker_base_image"])
            self.logger.info(f"Updated base image: {image.id}")
            return True, f"Base image updated to: {image.id}"
        except Exception as e:
            self.logger.error(f"Error updating base image: {e}")
            return False, f"Error updating base image: {str(e)}"