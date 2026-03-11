import os

class FileRepo:
    @staticmethod
    def get_user_dir(user_id: str) -> str:
        base_path = f"memory/users/{user_id}"
        os.makedirs(f"{base_path}/system", exist_ok=True)
        return base_path

    @staticmethod
    def load_os_context(user_id: str) -> str:
        contexte = ""
        user_dir = FileRepo.get_user_dir(user_id)
        
        path_agents = f"{user_dir}/system/AGENTS.md"
        if os.path.exists(path_agents):
            with open(path_agents, "r", encoding="utf-8") as f:
                contexte += f.read() + "\n\n"
                
        path_user = f"{user_dir}/system/USER.md"
        if os.path.exists(path_user):
            with open(path_user, "r", encoding="utf-8") as f:
                contexte += f"--- PROFIL DE L'UTILISATEUR ACTUEL ({user_id}) ---\n"
                contexte += f.read() + "\n\n"
        
        if not contexte.strip():
            contexte = "Tu es J.E.A.N-H.E.U.D.E, un assistant local souverain."
            
        return contexte

    @staticmethod
    def init_memory_md(user_id: str) -> bool:
        """Returns True if it was just created/empty, False if it already existed and has content."""
        user_dir = FileRepo.get_user_dir(user_id)
        file_path = f"{user_dir}/system/MEMORY.md"
        
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(f"# Mémoire Long Terme de {user_id}\n\n")
                f.write("- Je viens de me réveiller. Ma mémoire est encore vierge.\n")
            return True
        return False

    @staticmethod
    def read_memory_md(user_id: str) -> list[str]:
        user_dir = FileRepo.get_user_dir(user_id)
        file_path = f"{user_dir}/system/MEMORY.md"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.readlines()
        return []

    @staticmethod
    def append_fact_to_memory(user_id: str, fact: str):
        user_dir = FileRepo.get_user_dir(user_id)
        with open(f"{user_dir}/system/MEMORY.md", "a", encoding="utf-8") as f:
            f.write(f"\n{fact}\n")

