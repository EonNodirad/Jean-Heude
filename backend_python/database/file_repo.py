import os
from pathlib import Path

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

    @staticmethod
    def _safe_resolve(user_id: str, rel_path: str) -> Path:
        """Résout un chemin relatif et vérifie qu'il reste dans le dossier de l'utilisateur."""
        base = Path(f"memory/users/{user_id}").resolve()
        target = (base / rel_path).resolve()
        if not str(target).startswith(str(base)):
            raise PermissionError("Accès refusé : chemin hors de la zone utilisateur")
        return target

    @staticmethod
    def list_user_files(user_id: str) -> list[dict]:
        """Retourne la liste récursive des fichiers/dossiers de l'utilisateur."""
        base = Path(f"memory/users/{user_id}")
        if not base.exists():
            return []
        result = []
        for item in sorted(base.rglob("*")):
            rel = item.relative_to(base)
            result.append({
                "path": str(rel),
                "type": "file" if item.is_file() else "dir",
            })
        return result

    @staticmethod
    def read_user_file(user_id: str, rel_path: str) -> str:
        target = FileRepo._safe_resolve(user_id, rel_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {rel_path}")
        return target.read_text(encoding="utf-8")

    @staticmethod
    def write_user_file(user_id: str, rel_path: str, content: str):
        target = FileRepo._safe_resolve(user_id, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    @staticmethod
    def create_user_file(user_id: str, rel_path: str):
        target = FileRepo._safe_resolve(user_id, rel_path)
        if target.exists():
            raise FileExistsError(f"Le fichier existe déjà : {rel_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    @staticmethod
    def delete_user_file(user_id: str, rel_path: str):
        target = FileRepo._safe_resolve(user_id, rel_path)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Fichier introuvable : {rel_path}")
        target.unlink()

