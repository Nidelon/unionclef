# UnionClef — порт на Minecraft 26.2

Ветка `26.2`. Порт мода с Java 21 / Minecraft 1.21.x на **Java 25 / Minecraft 26.2 / Fabric**.

## Что здесь есть

| путь | что это |
|---|---|
| `src/` | altoclef (adris) — правленые под 26.2 исходники |
| `tungsten/src/` | tungsten (kaptainwutax) — без изменений |
| `port26/` | проект сборки 26.2: свой `build.gradle.kts` и `settings.gradle.kts` |
| `port26/src/` | **генерируемое** дерево (в git не попадает) |
| `scripts/port/` | пайплайн портирования |
| `PORT-STATE.md` | этот файл |

`port26/` — отдельный проект, потому что Gradle 9 убрал флаг `-b`, а трогать
`build.gradle` и `versions/*` ради одной версии не хотелось: сборка 1.21.x
работает как раньше.

## Как собрать

```bash
bash scripts/port/rebuild.sh
```

Шаги: препроцессинг веток → переименование yarn→mojmap → карта версий
mojmap→26.2 → детерминированные фиксы → итеративный автофиксер по структурной
диагностике → проверка целей миксинов → сборка.

Готовый jar: `port26/build/libs/unionclef-0.95.58-26.2-port.1.jar`

### Первый запуск на чистой машине

Пайплайну нужны таблицы маппингов; они не лежат в git:

```bash
python3 scripts/port/maps/fetch_sources.py 1.21.1
python3 scripts/port/maps/fetch_sources.py 1.21.11
# затем build_map.py / build_hierarchy.py / build_vermap.py / compose_map.py
# для каждой версии; для vermap нужен client.jar 26.2 из кэша Loom
# (появляется после первой сборки port26)
```

## Почему порт — это не «бамп версии»

В 26.x Mojang убрал обфускацию: игра выходит с официальными именами, Yarn и
intermediary для неё не существуют. Поэтому переименование идёт по цепочке
`yarn → intermediary → official(obf) → mojmap`, а поверх — ручная миграция API,
которую никакая карта не выразит: удалённые классы (`TieredItem`, `ArmorItem`,
`Tiers`, `GuiGraphics`, `FastColor`, `Tuple`), переехавшие (`ARGB`,
`FuelValues`), сменившие сигнатуры (`interact` получил `EntityHitResult`,
`Entity.getYaw()` стал `getYRot(float)`), и целые подсистемы вроде рецептов.

## Состояние

Проверено вживую:

- сборка с нуля, 0 ошибок компиляции;
- клиент стартует, мод грузится, миксины применяются;
- инициализация доходит до конца: `Py4j gateway on 25333` и
  `MCP server on 0.0.0.0:25350`;
- агентский интерфейс отвечает: `tools/list` (60 инструментов),
  `getGameState` отдаёт живое состояние бота.

Открытый вопрос: **навигация не двигает бота**. Тик-хендлер tungsten
(`MixinClientPlayerEntity.start`) выходит на первой строке
`if (TungstenMod.runKeyBinding == null) return;`, то есть весь стек движения
не запускается. Дальше копать отсюда.

Осознанно отключено (с причинами) — см. коммит про миксины: `WorldBlockModifiedMixin`,
`GameOverlayMixin`, `MixinDebugRenderer`, `MixinClientCommandSource`,
`AxeItemAccessor`, `MiningToolItemAccessor`, `DrawableHelperInvoker`,
`ToolMaterialVer`; перечисление рецептов на клиенте в 26.2 недоступно.
