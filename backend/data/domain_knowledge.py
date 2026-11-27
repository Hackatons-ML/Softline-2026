"""
Structured B2B IT domain knowledge, slang/jargon/rebranding ontology,
keyboard layout & transliteration tables, and verified external vendor
compatibility ecosystems for Store.softline.ru.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Keyboard layout mapping (QWERTY <-> ЙЦУКЕН) for mistyped queries
# ---------------------------------------------------------------------------
_EN_CHARS = "`qwertyuiop[]asdfghjkl;'zxcvbnm,./~QWERTYUIOP{}ASDFGHJKL:\"ZXCVBNM<>?"
_RU_CHARS = "ёйцукенгшщзхъфывапролджэячсмитьбю.ЁЙЦУКЕНГШЩЗХЪФЫВАПРОЛДЖЭЯЧСМИТЬБЮ,"

EN_TO_RU_MAP: Dict[int, str] = str.maketrans(_EN_CHARS, _RU_CHARS)
RU_TO_EN_MAP: Dict[int, str] = str.maketrans(_RU_CHARS, _EN_CHARS)

# ---------------------------------------------------------------------------
# 2. Bidirectional phonetic transliteration & canonical brand aliases
# ---------------------------------------------------------------------------
CANONICAL_TOKEN_ALIASES: Dict[str, str] = {
    # Astra Linux
    "астралинукс": "astra linux",
    "астра линукс": "astra linux",
    "астра линух": "astra linux",
    "astralinux": "astra linux",
    # MDaemon
    "мдаемон": "mdaemon",
    "мдемон": "mdaemon",
    "мдаймон": "mdaemon",
    "эмдаемон": "mdaemon",
    # CryptoPro
    "крипто про": "криптопро",
    "крипто-про": "криптопро",
    "kripto-pro": "криптопро",
    "kriptopro": "криптопро",
    "cryptopro": "криптопро",
    "crypto pro": "криптопро",
    # Positive Technologies MaxPatrol
    "max patrol": "maxpatrol",
    "макс патрол": "maxpatrol",
    "макспатрол": "maxpatrol",
    # Echelon Scanner-VS
    "сканер вс": "сканер-вс",
    "сканервс": "сканер-вс",
    "scaner-vs": "сканер-вс",
    "scanner-vs": "сканер-вс",
    "эшелон сканер": "эшелон сканер-вс",
    # AnyDesk / Remote Desktop
    "энидеск": "anydesk",
    "анидеск": "anydesk",
    "эни деск": "anydesk",
    "ани деск": "anydesk",
    "any desk": "anydesk",
    "рудесктоп": "rudesktop",
    "тимвьювер": "teamviewer",
    "тимвивер": "teamviewer",
    # Kaspersky
    "касперский": "kaspersky",
    "каспер": "kaspersky",
    "касперского": "kaspersky",
    "ksos": "kaspersky small office security",
    "kes": "kaspersky endpoint security",
    # Dr.Web
    "дрвеб": "доктор веб",
    "др веб": "доктор веб",
    "drweb": "доктор веб",
    "dr.web": "доктор веб",
    # Cyberprotect / Cyber Backup
    "кибербэкап": "кибер бэкап",
    "кибер бекап": "кибер бэкап",
    "кибербекап": "кибер бэкап",
    "cyber backup": "кибер бэкап",
    "cyberbackup": "кибер бэкап",
    # Microsoft / Office / Windows
    "майкрософт": "microsoft",
    "микрософт": "microsoft",
    "виндовс": "windows",
    "виндоус": "windows",
    "ексель": "excel",
    "эксель": "excel",
    "ворд": "word",
    # Russian Office Suites & Platforms
    "р7 офис": "р7-офис",
    "р7офис": "р7-офис",
    "r7 office": "р7-офис",
    "мой офис": "мойофис",
    "myoffice": "мойофис",
    "контур толк": "контур.толк",
    "элма": "elma365",
    "элма365": "elma365",
    "элма 365": "elma365",
    "elma 365": "elma365",
    # Security & CAD & Hardware
    "юзергейт": "usergate",
    "user gate": "usergate",
    "нанокад": "nanocad",
    "нано кад": "nanocad",
    "компас 3д": "компас-3d",
    "компас 3d": "компас-3d",
    "супермикро": "supermicro",
    "депо": "depo",
    "аквариус": "aquarius",
}


# ---------------------------------------------------------------------------
# 3. Domain Jargon, Slang, Numeric Shortcuts & Vendor Rebrandings
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QueryRule:
    rule_id: str
    triggers: Tuple[str, ...]
    exact_token_only: bool
    explanation: str
    expanded_query: str
    boost_vendors: Tuple[str, ...] = ()
    boost_categories: Tuple[str, ...] = ()
    boost_group_names: Tuple[str, ...] = ()
    product_type_hint: Optional[str] = None  # 'софт' | 'электроника' | None
    disambiguation_options: Tuple[Tuple[str, str], ...] = ()
    import_substitution_category: Optional[str] = None


DOMAIN_QUERY_RULES: List[QueryRule] = [
    QueryRule(
        rule_id="rebrand_mts_link",
        triggers=("мтс", "мтс линк", "mts link", "mts", "вебинар", "вебинары", "webinar"),
        exact_token_only=True,
        explanation="Ребрендинг вендора: сервис Webinar Group теперь развивается как «МТС Линк» (в каталоге store.softline.ru/webinar/)",
        expanded_query="МТС Линк Webinar онлайн коммуникации вебинары видеоконференции",
        boost_vendors=("МТС Линк", "СКБ Контур"),
        boost_categories=("7388", "7437"),
        boost_group_names=("МТС Линк Optimum 30", "МТС Линк Стандарт", "МТС Линк Про", "Webinar"),
        product_type_hint="софт",
    ),
    QueryRule(
        rule_id="numeric_365",
        triggers=("365", "офис 365", "office 365", "office365", "m365", "microsoft 365"),
        exact_token_only=True,
        explanation="Запрос «365» интерпретирован как облачный пакет Microsoft 365 / Office и корпоративные платформы 365 (включая доступные в РФ лицензии Office и аналоги)",
        expanded_query="Microsoft 365 Microsoft Office для дома и бизнеса ELMA365 офисный пакет подписка",
        boost_vendors=("Программы и лицензии Microsoft Corporation", "ELMA", "Р7", "МойОфис"),
        boost_categories=("1145", "872", "1140"),
        boost_group_names=(
            "Microsoft 365",
            "Microsoft Office 2024 для дома и бизнеса",
            "ELMA365",
        ),
        product_type_hint="софт",
        import_substitution_category="office_suite",
    ),
    QueryRule(
        rule_id="slang_antivirus",
        triggers=("антивирь", "антивирусник", "антивир", "защита от вирусов", "антивирус"),
        exact_token_only=True,
        explanation="Жаргон «антивирь» нормализован в категорию антивирусной защиты рабочих станций и серверов (Endpoint Security)",
        expanded_query="антивирус Kaspersky Small Office Security Kaspersky Endpoint Security Dr.Web PRO32 защита ПК",
        boost_vendors=("«Лаборатория Касперского»", "Доктор Веб", "PRO32", "Positive Technologies"),
        boost_categories=("650", "652"),
        boost_group_names=(
            "Kaspersky Small Office Security",
            "Kaspersky Endpoint Security для бизнеса Стандартный",
            "PRO32 Endpoint Security",
            "MaxPatrol Endpoint Protection Platform",
        ),
        product_type_hint="софт",
    ),
    QueryRule(
        rule_id="slang_windows",
        triggers=("винда", "винду", "винды", "шиндовс", "виндовс", "windows"),
        exact_token_only=True,
        explanation="Жаргон «винда» распознан как ОС Microsoft Windows + сертифицированные российские ОС для импортозамещения",
        expanded_query="Microsoft Windows 11 Pro операционная система Astra Linux РЕД ОС Базальт Альт",
        boost_vendors=("Программы и лицензии Microsoft Corporation", "Группа Астра", "РЕД СОФТ", "Базальт СПО"),
        boost_categories=("2052", "222320"),
        boost_group_names=("Astra Linux Special Edition", "Windows 11", "Windows 10", "РЕД ОС"),
        product_type_hint="софт",
        import_substitution_category="os",
    ),
    QueryRule(
        rule_id="slang_office",
        triggers=("офис", "ворд и эксель", "офисный пакет", "таблицы и документы"),
        exact_token_only=True,
        explanation="Разговорный запрос «офис» сопоставлен с офисными пакетами (Microsoft Office, Р7-Офис, МойОфис)",
        expanded_query="Microsoft Office 2024 для дома и бизнеса Р7-Офис МойОфис Стандартный офисные программы",
        boost_vendors=("Программы и лицензии Microsoft Corporation", "Р7", "МойОфис", "Новые облачные технологии"),
        boost_categories=("872", "1145"),
        boost_group_names=(
            "Microsoft Office 2024 для дома и бизнеса",
            "Р7-Офис. Профессиональный",
            "МойОфис Стандартный",
        ),
        product_type_hint="софт",
        import_substitution_category="office_suite",
    ),
    QueryRule(
        rule_id="rebrand_acronis_backup",
        triggers=("акронис", "acronis", "резервка", "бэкап", "бекап", "резервное копирование"),
        exact_token_only=True,
        explanation="Ребрендинг и ИТ-сленг: российский преемник Acronis — линейка «Кибер Бэкап» от вендора Киберпротект",
        expanded_query="Киберпротект Кибер Бэкап Стандартная Расширенная резервное копирование данных",
        boost_vendors=("Киберпротект",),
        boost_categories=("1033",),
        boost_group_names=(
            "Кибер Бэкап Стандартная редакция",
            "Кибер Бэкап Расширенная редакция",
            "Кибер Бэкап Малый Бизнес",
            "Кибер Бэкап Облачный",
        ),
        product_type_hint="софт",
    ),
    QueryRule(
        rule_id="rebrand_abbyy_ocr",
        triggers=("файнридер", "finereader", "абби", "abbyy", "abby", "распознавание текста", "ocr"),
        exact_token_only=True,
        explanation="Ребрендинг: продукты распознавания текста ABBYY в РФ поставляются под брендом Content AI",
        expanded_query="Content AI Reader Screenshot Reader распознавание текста PDF OCR SETERE",
        boost_vendors=("Content AI", "Сontent AI", "SETERE", "Code Industry"),
        boost_categories=("6", "8", "127"),
        product_type_hint="софт",
        import_substitution_category="pdf_ocr",
    ),
    QueryRule(
        rule_id="slang_remote_access",
        triggers=("удаленка", "удалёнка", "удаленный доступ", "удаленный рабочий стол", "teamviewer", "тимвьювер"),
        exact_token_only=False,
        explanation="Сценарий удаленного подключения и администрирования ПК (AnyDesk и российские аналоги из реестра ПО)",
        expanded_query="AnyDesk RuDesktop Ассистент Контур.Доступ программы для удаленного доступа",
        boost_vendors=("AnyDesk", "RuDesktop", "САФИБ", "СКБ Контур"),
        boost_categories=("327028", "327030"),
        boost_group_names=("AnyDesk",),
        product_type_hint="софт",
        import_substitution_category="remote_access",
    ),
    QueryRule(
        rule_id="slang_crypto_eds",
        triggers=("эцп", "скзи", "гост шифрование", "электронная подпись", "криптопровайдер"),
        exact_token_only=False,
        explanation="Запрос по электронной подписи / СКЗИ → средства криптографической защиты информации КриптоПро CSP и токены",
        expanded_query="КриптоПро CSP 5.0 лицензия СКЗИ электронная подпись Рутокен JaCarta",
        boost_vendors=("КриптоПро", "Актив", "Аладдин Р.Д."),
        boost_categories=("687",),
        boost_group_names=("Программа КриптоПро CSP 5.0",),
        product_type_hint="софт",
    ),
    QueryRule(
        rule_id="slang_ngfw_firewall",
        triggers=("фаервол", "файрвол", "межсетевой экран", "нгфв", "ngfw", "utm", "шлюз безопасности"),
        exact_token_only=False,
        explanation="Запрос по сетевой безопасности периметра → межсетевые экраны нового поколения (NGFW / UTM)",
        expanded_query="UserGate NGFW ПАК межсетевой экран Континент Ideco сетевая безопасность",
        boost_vendors=("UserGate", "Код Безопасности", "Айдеко"),
        boost_categories=("687", "3656", "652"),
        product_type_hint="софт",
    ),
    QueryRule(
        rule_id="slang_cad",
        triggers=("автокад", "autocad", "чертежи", "сапр", "проектирование dwg"),
        exact_token_only=True,
        explanation="Инженерное проектирование и САПР (AutoCAD и отечественные САПР: nanoCAD, КОМПАС-3D)",
        expanded_query="nanoCAD КОМПАС-3D САПР проектирование чертежи Нанософт АСКОН",
        boost_vendors=("Нанософт Разработка", "АСКОН", "Renga Software"),
        boost_categories=("5676",),
        product_type_hint="софт",
        import_substitution_category="cad",
    ),
    QueryRule(
        rule_id="unavailable_zoom_vks",
        triggers=("zoom", "зум", "ms teams", "тимс", "скайп", "вкс"),
        exact_token_only=True,
        explanation="Зарубежный ВКС-сервис / запрос ВКС → доступные в РФ корпоративные платформы видеоконференций",
        expanded_query="МТС Линк Контур.Толк TrueConf видеоконференцсвязь вебинары онлайн встречи",
        boost_vendors=("МТС Линк", "СКБ Контур", "TrueConf"),
        boost_categories=("7388", "7437"),
        product_type_hint="софт",
        import_substitution_category="vks",
    ),
    QueryRule(
        rule_id="unavailable_adobe_pdf",
        triggers=("photoshop", "фотошоп", "adobe acrobat", "акробат", "редактор pdf"),
        exact_token_only=False,
        explanation="Продукты Adobe недоступны для прямой закупки в РФ → показаны позиции каталога и доступные аналоги для графики и PDF",
        expanded_query="Master PDF Editor Content AI CorelDRAW редактор PDF графический пакет",
        boost_vendors=("Code Industry", "Corel Corporation", "Content AI", "Adobe Systems"),
        boost_categories=("127", "188", "6"),
        product_type_hint="софт",
        import_substitution_category="pdf_ocr",
    ),
    QueryRule(
        rule_id="unavailable_jira_tracker",
        triggers=("jira", "джира", "confluence", "конфлюенс", "trello", "трелло", "notion", "ноушен"),
        exact_token_only=True,
        explanation="Зарубежные таск-трекеры Atlassian/Notion ушли с рынка РФ → подобраны российские системы управления проектами и BPM из каталога",
        expanded_query="ELMA365 Проекты Directum Битрикс24 управление проектами корпоративный портал",
        boost_vendors=("ELMA", "DIRECTUM", "1С-Битрикс"),
        boost_categories=("182", "1140"),
        product_type_hint="софт",
        import_substitution_category="bpm_crm",
    ),
    QueryRule(
        rule_id="unavailable_vmware_virt",
        triggers=("vmware", "вмварь", "vsphere", "esxi", "hyper-v", "виртуализация"),
        exact_token_only=True,
        explanation="Платформы виртуализации (замена VMware vSphere / Hyper-V на российские гипервизоры из реестра ПО)",
        expanded_query="Кибер Инфраструктура Брест zVirt РЕД Виртуализация серверная виртуализация",
        boost_vendors=("Киберпротект", "Группа Астра", "РЕД СОФТ"),
        boost_categories=("687", "2502", "2052"),
        product_type_hint="софт",
        import_substitution_category="virtualization",
    ),
]

# Software context qualifiers that override bare "сервер" hardware preference
SERVER_SOFTWARE_QUALIFIERS: Tuple[str, ...] = (
    "почтовый", "почта", "mail", "mdaemon", "exchange",
    "sql", "субд", "база данных", "postgres", "mssql",
    "терминальный", "rdp", "вкс", "вебинар", "трансляц",
    "документооборот", "сэд", "1с", "лицензия", "ос ", "операционн",
    "astra", "астра", "windows server", "линукс", "linux", "антивирус",
    "виртуализац", "прокси", "proxy", "принт",
)

SERVER_HARDWARE_TRIGGERS: Tuple[str, ...] = (
    "сервер", "сервак", "серверы", "сервера", "rack сервер", "стоечный сервер",
    "серверное оборудование", "сервер в стойку", "tower сервер", "платформа серверная",
)


# ---------------------------------------------------------------------------
# 4. Verified External Vendor Ecosystem & Cross-Sell / Alternative Rules
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VendorSourceRef:
    vendor_name: str
    program_title: str
    url: str
    summary: str


@dataclass(frozen=True)
class EcosystemRule:
    ecosystem_id: str
    match_keywords: Tuple[str, ...]
    companion_queries: Tuple[Tuple[str, str, VendorSourceRef], ...]
    # tuple of: (companion_search_query, relation_badge, verified_vendor_source)


VERIFIED_ECOSYSTEM_RULES: List[EcosystemRule] = [
    EcosystemRule(
        ecosystem_id="astra_linux_stack",
        match_keywords=("astra linux", "группа астра", "редос", "ред ос", "альт сервер", "альт рабочая", "операционные системы"),
        companion_queries=(
            (
                "КриптоПро CSP 5.0",
                "Часто покупают вместе · СКЗИ и ГОСТ ЭП",
                VendorSourceRef(
                    vendor_name="Группа Астра × КриптоПро",
                    program_title="Сертификат совместимости Ready for Astra",
                    url="https://astra.ru/about/press-center/news/sovmestimost-astra-linux-i-kriptopro/",
                    summary="Официально подтверждена работа СКЗИ КриптоПро CSP 5.0 на Astra Linux SE 1.7/1.8 (x86_64, Байкал, Эльбрус).",
                ),
            ),
            (
                "Кибер Бэкап Стандартная редакция",
                "Часто покупают вместе · Резервное копирование",
                VendorSourceRef(
                    vendor_name="Киберпротект × Группа Астра",
                    program_title="Матрица совместимости Кибер Бэкап и Astra Linux SE",
                    url="https://cyberprotect.ru/compatibility/",
                    summary="Полная поддержка резервного копирования серверов и АРМ Astra Linux SE при включенных МРД и МКЦ.",
                ),
            ),
            (
                "Kaspersky Small Office Security",
                "Часто покупают вместе · Антивирусная защита ИБ",
                VendorSourceRef(
                    vendor_name="Лаборатория Касперского",
                    program_title="Защита конечных точек и серверов на российских ОС",
                    url="https://www.kaspersky.ru/small-to-medium-business-security",
                    summary="Сертифицированная защита рабочих станций и файловых серверов от шифровальщиков и сетевых угроз.",
                ),
            ),
            (
                "Rack-сервер DEPO Storm",
                "Инфраструктурная основа · Аппаратный сервер",
                VendorSourceRef(
                    vendor_name="DEPO Computers × Astra Linux",
                    program_title="Аппаратная совместимость серверов DEPO Storm",
                    url="https://www.depo.ru/catalog/servery/",
                    summary="Серверные платформы DEPO протестированы для развертывания корпоративных контуров на базе Astra Linux.",
                ),
            ),
        ),
    ),
    EcosystemRule(
        ecosystem_id="server_hardware_stack",
        match_keywords=("rack-сервер", "серверы и опции", "superchassis", "supermicro", "depo storm", "серверные опции", "шасси"),
        companion_queries=(
            (
                "Astra Linux Special Edition",
                "Необходимое ПО · Серверная ОС",
                VendorSourceRef(
                    vendor_name="Группа Астра",
                    program_title="Оборудование, совместимое с Astra Linux Server",
                    url="https://astra.ru/products/astralinux/special-edition/",
                    summary="Защищенная серверная ОС со встроенными СЗИ для стоечных x86-64 серверов.",
                ),
            ),
            (
                "Кибер Бэкап Расширенная редакция",
                "Защита данных · Бэкап физических и виртуальных серверов",
                VendorSourceRef(
                    vendor_name="Киберпротект",
                    program_title="Резервное копирование серверной инфраструктуры",
                    url="https://cyberprotect.ru/products/cyber-backup/",
                    summary="Централизованный бэкап физических серверов, гипервизоров и корпоративных СУБД.",
                ),
            ),
            (
                "ПАК UserGate NGFW",
                "Защита периметра ЦОД · Акция −50%",
                VendorSourceRef(
                    vendor_name="UserGate",
                    program_title="Межсетевое экранирование серверного сегмента",
                    url="https://www.usergate.com/ru/products/usergate-ngfw",
                    summary="Аппаратно-программный межсетевой экран нового поколения для защиты серверной стойки и филиалов.",
                ),
            ),
            (
                "MaxPatrol Endpoint Protection Platform",
                "ИБ серверов · Контроль защищенности узлов",
                VendorSourceRef(
                    vendor_name="Positive Technologies",
                    program_title="Защита серверных ОС Windows и Linux",
                    url="https://www.ptsecurity.com/ru-ru/products/epp/",
                    summary="Предотвращение сложных атак и шифровальщиков на критически важных серверных узлах.",
                ),
            ),
        ),
    ),
    EcosystemRule(
        ecosystem_id="office_productivity_stack",
        match_keywords=("microsoft office", "microsoft 365", "р7-офис", "мойофис", "офисные программы", "текстовые редакторы"),
        companion_queries=(
            (
                "Kaspersky Small Office Security",
                "Безопасность АРМ · Защита рабочей почты и документов",
                VendorSourceRef(
                    vendor_name="Лаборатория Касперского",
                    program_title="Комплексная защита офисных ПК от фишинга и шифровальщиков",
                    url="https://www.kaspersky.ru/small-office-security",
                    summary="Мгновенное развертывание защиты офисных ноутбуков и файловых серверов без выделенного ИТ-отдела.",
                ),
            ),
            (
                "КриптоПро CSP 5.0",
                "Юридически значимый ЭДО · ЭП в документах",
                VendorSourceRef(
                    vendor_name="КриптоПро",
                    program_title="Подписание электронных документов и отчетности",
                    url="https://www.cryptopro.ru/products/csp",
                    summary="Стандарт СКЗИ для работы с ЭП в офисных пакетах, браузерах и государственных порталах.",
                ),
            ),
            (
                "Master Pdf Editor",
                "Работа с PDF · Выгодный редактор документов",
                VendorSourceRef(
                    vendor_name="Code Industry",
                    program_title="Редактирование и подписание PDF на Windows и Linux",
                    url="https://code-industry.net/ru/masterpdfeditor/",
                    summary="Полноценное редактирование текста, форм и ЭП в PDF-документах как доступная замена Adobe Acrobat.",
                ),
            ),
            (
                "МТС Линк Optimum 30",
                "Командная работа · ВКС и онлайн-встречи",
                VendorSourceRef(
                    vendor_name="МТС Линк",
                    program_title="Единое пространство деловых коммуникаций",
                    url="https://mts-link.ru/",
                    summary="Корпоративные онлайн-встречи, вебинары, чаты и ИИ-саммари совещаний для офисных команд.",
                ),
            ),
        ),
    ),
    EcosystemRule(
        ecosystem_id="cybersecurity_stack",
        match_keywords=("kaspersky", "криптопро", "maxpatrol", "сканер-вс", "эшелон", "доктор веб", "usergate", "антивирусы", "защиты информации"),
        companion_queries=(
            (
                "Эшелон СКАНЕР-ВС",
                "Контроль уязвимостей · Сертификат ФСТЭК",
                VendorSourceRef(
                    vendor_name="НПО «Эшелон»",
                    program_title="Сертифицированный анализ защищенности СКАНЕР-ВС",
                    url="https://npo-echelon.ru/solutions/scanner_vs/",
                    summary="Выявление уязвимостей и аудит конфигураций ИТ-инфраструктуры в соответствии с требованиями ФСТЭК РФ.",
                ),
            ),
            (
                "Кибер Бэкап Стандартная редакция",
                "Киберустойчивость · Резервная копия от шифровальщиков",
                VendorSourceRef(
                    vendor_name="Киберпротект",
                    program_title="Эшелонированная защита данных от программ-вымогателей",
                    url="https://cyberprotect.ru/products/cyber-backup/",
                    summary="Неизменяемые резервные копии и активная защита бэкапов дополняют антивирус и СКЗИ.",
                ),
            ),
            (
                "ПАК UserGate NGFW",
                "Сетевой контур · Акция −50% в каталоге",
                VendorSourceRef(
                    vendor_name="UserGate",
                    program_title="Экосистема сетевой безопасности UserGate SUMMA",
                    url="https://www.usergate.com/ru/",
                    summary="Инспекция трафика, предотвращение вторжений IDPS и безопасный удаленный VPN-доступ.",
                ),
            ),
            (
                "Astra Linux Special Edition",
                "Доверенная среда · Защищенная ОС",
                VendorSourceRef(
                    vendor_name="Группа Астра",
                    program_title="Построение защищенных автоматизированных систем и КИИ",
                    url="https://astra.ru/",
                    summary="Базовая доверенная ОС для работы средств криптозащиты и сертифицированных решений ИБ.",
                ),
            ),
        ),
    ),
    EcosystemRule(
        ecosystem_id="vks_remote_comms_stack",
        match_keywords=("мтс линк", "webinar", "контур.толк", "anydesk", "удаленного доступа", "mdaemon", "почтовые"),
        companion_queries=(
            (
                "Yealink",
                "Оборудование переговорных · ВКС и спикерфоны",
                VendorSourceRef(
                    vendor_name="Yealink × МТС Линк",
                    program_title="Аппаратное оснащение переговорных комнат",
                    url="https://mts-link.ru/",
                    summary="Профессиональные ВКС-терминалы, камеры и спикерфоны для гибридных встреч и вебинаров.",
                ),
            ),
            (
                "MDaemon Messaging Server",
                "Корпоративная почта · Локальный почтовый сервер",
                VendorSourceRef(
                    vendor_name="MDaemon Technologies",
                    program_title="Защищенный почтовый сервер и групповые календари",
                    url="https://www.mdaemon.com/",
                    summary="Надежный корпоративный почтовый сервер с встроенной защитой от спама и поддержкой ActiveSync.",
                ),
            ),
            (
                "Kaspersky Small Office Security",
                "Безопасность удаленки · Защита гибридных рабочих мест",
                VendorSourceRef(
                    vendor_name="Лаборатория Касперского",
                    program_title="Безопасность распределенных команд",
                    url="https://www.kaspersky.ru/small-office-security",
                    summary="Защита корпоративных ноутбуков и удаленных сессий вне офисного периметра.",
                ),
            ),
            (
                "AnyDesk",
                "Техподдержка сотрудников · Удаленный доступ",
                VendorSourceRef(
                    vendor_name="AnyDesk",
                    program_title="Быстрое удаленное администрирование рабочих станций",
                    url="https://anydesk.com/",
                    summary="Мгновенное подключение ИТ-службы к удаленным сотрудникам с минимальной задержкой.",
                ),
            ),
        ),
    ),
]

# Import-substitution lookup map when queried vendor/SKU is unavailable (available="false") or foreign
IMPORT_SUBSTITUTION_ALTERNATIVES: Dict[str, Tuple[str, str, str]] = {
    # category_key -> (search_query_for_active_analogs, badge_title, rationale)
    "office_suite": (
        "Р7-Офис МойОфис Стандартный Профессиональный",
        "Доступная альтернатива из Реестра ПО РФ",
        "Российские офисные пакеты с полной поддержкой форматов DOCX/XLSX/PPTX, доступные для коммерческих и госзаказчиков без санкционных ограничений.",
    ),
    "os": (
        "Astra Linux Special Edition РЕД ОС Альт",
        "Российские ОС (Импортозамещение · ЕРРП)",
        "Отечественные операционные системы для рабочих станций и серверов со встроенными средствами защиты и сертификатами ФСТЭК.",
    ),
    "pdf_ocr": (
        "Content AI Master PDF Editor SETERE OCR",
        "Доступные аналоги Adobe / ABBYY в наличии",
        "Актуальные решения для распознавания сканов (OCR) и редактирования PDF-документов, доступные к быстрой поставке на store.softline.ru.",
    ),
    "remote_access": (
        "RuDesktop Ассистент Контур.Доступ AnyDesk",
        "Решения удаленного доступа в наличии",
        "Лицензируемые в РФ инструменты удаленного администрирования и техподдержки с поддержкой Windows, macOS и Astra Linux.",
    ),
    "cad": (
        "nanoCAD КОМПАС-3D Renga",
        "Отечественные САПР (замена AutoCAD)",
        "Полная поддержка DWG/3D-моделирования и российских стандартов оформления проектной документации СПДС и ЕСКД.",
    ),
    "vks": (
        "МТС Линк Контур.Толк TrueConf",
        "Корпоративные ВКС в наличии (Реестр ПО РФ)",
        "Облачные и серверные платформы онлайн-встреч и вебинаров с серверами на территории РФ.",
    ),
    "bpm_crm": (
        "ELMA365 Directum Битрикс24",
        "Российские платформы совместной работы и BPM",
        "Замена зарубежных трекеров и систем документооборота с гибкой low-code настройкой бизнес-процессов.",
    ),
    "virtualization": (
        "Кибер Инфраструктура Брест zVirt",
        "Российская виртуализация (замена VMware)",
        "Отказоустойчивые платформы серверной виртуализации и программно-определяемых хранилищ из реестра Минцифры.",
    ),
}
