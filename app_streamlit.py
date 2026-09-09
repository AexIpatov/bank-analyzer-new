import json
from datetime import datetime

class Task:
    """
    Класс, описывающий отдельную задачу.
    """
    def __init__(self, description: str):
        self.description = description
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.completed = False

    def to_dict(self):
        """Преобразует объект задачи в словарь для сохранения в JSON."""
        return {
            "description": self.description,
            "created_at": self.created_at,
            "completed": self.completed
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Создает объект задачи из словаря (при загрузке из файла)."""
        task = cls(data["description"])
        task.created_at = data["created_at"]
        task.completed = data["completed"]
        return task


def main():
    # Основной список задач, хранящийся в оперативной памяти во время работы программы
    tasks = []
    
    print("Менеджер задач запущен.")
    print("Введите 'help', чтобы увидеть список команд.")

if __name__ == "__main__":
    main()
