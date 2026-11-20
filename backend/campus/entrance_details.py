from django.db import transaction
from .models import Entrance, Block

LEGACY_DESCRIPTION = "Наличие входа сообщено командой проекта; координаты ещё не собраны."
ENTRANCES = {
 "MAIN": ("Главный вход", "Main entrance", "Entrance reported by the project team; exact coordinates have not been collected."),
 "G": ("Вход со стороны блока G", "Entrance G", "Located between Blocks G and H."),
 "I": ("Вход со стороны блока I", "Entrance I", "Entrance reported by the project team; its position on the schematic is provisional."),
}
NOTES = {
 "Для блоков D–F команда указала главный вход.": "The team recommends the main entrance for Blocks D–F.",
 "Команда уточнила: для H удобнее вход со стороны G.": "The team recommends Entrance G for Block H.",
 "Предварительно: вход своего блока. Кратчайший путь не измерен.": "Provisional: use the entrance for this block. The shortest route has not been measured.",
 "Для H сравнить входы G и I после сбора плана и расстояний.": "Compare Entrances G and I after collecting plans and distances for Block H.",
}

@transaction.atomic
def update_entrances(stdout, stderr):
    changed = 0
    for code, (legacy, name, description) in ENTRANCES.items():
        obj = Entrance.objects.select_for_update().filter(code=code).first()
        if not obj:
            continue
        fields = []
        for field, old, new in [("name", legacy, name), ("description", LEGACY_DESCRIPTION, description)]:
            value = getattr(obj, field)
            if value in ("", old):
                setattr(obj, field, new); fields.append(field)
            elif value != new:
                stderr.write(f"Conflict: entrance {code}.{field}; manual value preserved.")
        if fields:
            obj.save(update_fields=fields); changed += 1
    for block in Block.objects.select_for_update():
        fields = []
        if block.name == f"Блок {block.code}":
            block.name = f"Block {block.code}"; fields.append("name")
        if block.recommendation_note in NOTES:
            block.recommendation_note = NOTES[block.recommendation_note]; fields.append("recommendation_note")
        elif block.recommendation_note and block.recommendation_note not in NOTES.values():
            stderr.write(f"Conflict: Block {block.code}.recommendation_note; manual value preserved.")
        if fields:
            block.save(update_fields=fields); changed += 1
    stdout.write(f"Entrance details: {changed} records updated.")
