from django.core.management.base import BaseCommand
from django.db import transaction

from campus.models import Block, Entrance, Room
from campus.numbering import parse_room_code


BARRELS = [
    ("D117", "A1", "1-й этаж, первая от главного входа"),
    ("D218", "A2", "2-й этаж, первая от главного входа"),
    ("D116", "B1", "1-й этаж, вторая от главного входа"),
    ("D217", "B2", "2-й этаж, вторая от главного входа"),
    ("D113", "C1", "1-й этаж, третья, рядом с Advisor Desk"),
    ("D214", "C2", "2-й этаж, третья, рядом с Advisor Desk"),
    ("E117", "D1", "1-й этаж, четвёртая, рядом с Red Canteen"),
    ("E221", "D2", "2-й этаж, четвёртая, рядом с Red Canteen"),
]


def ordinary_room_codes():
    """Team-requested provisional inventory: floors 1–4, rooms 01–05."""
    return [f"{block}{floor}{number:02d}" for block in "DEFGHI"
            for floor in range(1, 5) for number in range(1, 6)]


class Command(BaseCommand):
    help = "Create campus blocks, entrances, barrels and 120 provisional rooms; preserve manual edits."

    @transaction.atomic
    def handle(self, *args, **options):
        blocks = {}
        for order, code in enumerate("DEFGHI"):
            blocks[code], _ = Block.objects.get_or_create(code=code, defaults={
                "name": f"Блок {code}", "horizontal_order": order,
            })
        entrances = {}
        for code, name, block in [("MAIN", "Главный вход", None),
                                   ("G", "Вход со стороны блока G", blocks["G"]),
                                   ("I", "Вход со стороны блока I", blocks["I"])]:
            entrances[code], _ = Entrance.objects.get_or_create(code=code, defaults={
                "name": name, "block": block,
                "description": "Наличие входа сообщено командой проекта; координаты ещё не собраны.",
            })
        for code, block in blocks.items():
            # Only initialise an untouched recommendation; never replace manual edits.
            old_h_note = "Для H сравнить входы G и I после сбора плана и расстояний."
            if code == "H" and block.recommended_entrance_id is None and (
                not block.recommendation_note or block.recommendation_note == old_h_note
            ):
                block.recommended_entrance = entrances["G"]
                block.recommendation_status = Block.RecommendationStatus.USER_REPORTED
                block.recommendation_note = "Команда уточнила: для H удобнее вход со стороны G."
                block.save(update_fields=["recommended_entrance", "recommendation_status", "recommendation_note"])
                continue
            if block.recommended_entrance_id or block.recommendation_note:
                continue
            if code in "DEF":
                block.recommended_entrance = entrances["MAIN"]
                block.recommendation_status = Block.RecommendationStatus.USER_REPORTED
                block.recommendation_note = "Для блоков D–F команда указала главный вход."
            elif code in "GI":
                block.recommended_entrance = entrances[code]
                block.recommendation_status = Block.RecommendationStatus.PROVISIONAL
                block.recommendation_note = "Предварительно: вход своего блока. Кратчайший путь не измерен."
            else:
                block.recommendation_note = "Для H сравнить входы G и I после сбора плана и расстояний."
            block.save(update_fields=["recommended_entrance", "recommendation_status", "recommendation_note"])
        created = 0
        for code in ordinary_room_codes():
            _, block_code, floor = parse_room_code(code)
            _, new = Room.objects.get_or_create(code=code, defaults={
                "block": blocks[block_code], "floor": floor,
                "kind": Room.Kind.CLASSROOM if floor < 4 else Room.Kind.UNKNOWN,
                "name": f"Кабинет {code}",
                "description": "Предварительная запись по нумерации; проверить при сборе данных кампуса.",
                "source": "Сгенерировано по указанию команды, 2026-10-07; наличие требует проверки",
            })
            created += int(new)
        for code, alias, description in BARRELS:
            _, block_code, floor = parse_room_code(code)
            _, new = Room.objects.get_or_create(code=code, defaults={
                "block": blocks[block_code], "floor": floor, "kind": Room.Kind.BARREL,
                "name": f"Бочка {alias}", "aliases": [alias, f"Бочка {alias}", f"Barrel {alias}"],
                "description": description, "source": "Список команды проекта, 2026-10-07",
            })
            created += int(new)
        self.stdout.write(self.style.SUCCESS(f"Campus seeded: {created} new rooms; existing records preserved."))
