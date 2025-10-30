class BaseConfig:
    def get_launch_commands(self) -> list[str]:
        pass

    def get_cfg(self, project_path) -> list[str]:
        pass

    def on_pre_init(self, project_path):
        pass
