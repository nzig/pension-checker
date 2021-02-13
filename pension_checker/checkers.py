import abc
import itertools
import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, DefaultDict, Dict, List, Tuple

import xmlschema

from .schema import (
    HAFRASHA_RANGES_PENSION, SugHafrasha, fix_nil, parse_date, parse_datetime)

logger = logging.getLogger(__name__)


class Checker(abc.ABC):
    @property
    @abc.abstractmethod
    def root_path(self) -> str:
        pass

    def __init__(self, document: xmlschema.XmlDocument) -> None:
        self.document = document
        self.problems: List[str] = []
        self.headers: Dict[str, Any] = {}

    def check(self) -> List[tuple]:
        results: List[tuple] = []
        headers = self.get_path("KoteretKovetz")
        self.headers["SUG-MIMSHAK"] = headers["SUG-MIMSHAK"]
        self.headers["TAARICH-BITZUA"] = parse_datetime(headers["TAARICH-BITZUA"])

        for idx, tree in enumerate(self.get_path(self.root_path)):
            self.check_one(tree)
            results.extend((self.root_path, idx, p) for p in self.problems)
            self.problems.clear()
        return results

    @abc.abstractmethod
    def check_one(self, tree: Dict[str, Any]) -> None:
        pass

    @classmethod
    def all_checks(cls, xml_doc: Any, schema: Any) -> List[tuple]:
        document = xmlschema.XmlDocument(xml_doc, schema=schema)
        results: List[tuple] = []
        for subclass in cls.__subclasses__():
            checker = subclass(document)
            checker_results = checker.check()
            results.extend(checker_results)
        return results

    def assert_(self, check: bool, message: str) -> None:
        if not check:
            self.report(message)

    def assert_eq(self, left: Any, right: Any, message: str) -> None:
        if left != right:
            self.report(f"{message} ({left} != {right})")

    def assert_range(self, min: Any, value: Any, max: Any, message: str) -> None:
        if value < min:
            self.report(f"{message} ({value:.4} < {min}")
        elif value > max:
            self.report(f"{message} ({value:.4} > {max}")

    def assert_gte(self, left: Any, right: Any, message: str) -> None:
        if left < right:
            self.report(f"{message} ({left} < {right}")

    def assert_gt(self, left: Any, right: Any, message: str) -> None:
        if left <= right:
            self.report(f"{message} ({left} <= {right}")

    def assert_lte(self, left: Any, right: Any, message: str) -> None:
        if left > right:
            self.report(f"{message} ({left} > {right}")

    def assert_lt(self, left: Any, right: Any, message: str) -> None:
        if left >= right:
            self.report(f"{message} ({left} >= {right}")

    def report(self, message: str) -> None:
        self.problems.append(message)

    def get_path(self, path: str) -> Any:
        return self.document.decode(path=path)


class CheckLastHafkada(Checker):
    root_path = (
        "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa/PirteiTaktziv/"
        "PirteiHafkadaAchrona/PerutPirteiHafkadaAchrona"
    )

    def check_one(self, tree: Dict[str, Any]) -> None:
        last_total = tree["TOTAL-HAFKADA"]
        last_perut = tree["PerutHafkadaAchrona"]
        self.assert_eq(
            sum(x["SCHUM-HAFKADA-SHESHULAM"] for x in last_perut),
            last_total,
            "סכום פירוט הפקדות אחרונות שונה מסך הפקדה אחרונה",
        )
        salaries = {x["SACHAR-BERAMAT-HAFKADA"] for x in last_perut}
        self.assert_(
            len(salaries) == 1,
            f"שכר לא אחיד בהפקדה אחרונה: {','.join(str(s) for s in salaries)}",
        )


class CheckHafkadotYtd(Checker):
    root_path = "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa/PirteiTaktziv"

    def check_one(self, tree: Dict[str, Any]) -> None:
        key = lambda x: x["CHODESH-SACHAR"]
        for month, hafkadot in itertools.groupby(
            sorted(tree["PerutHafkadotMetchilatShana"], key=key), key=key
        ):
            salaries = {x["SACHAR-BERAMAT-HAFKADA"] for x in hafkadot}
            self.assert_(
                len(salaries) == 1,
                f"שכר לא אחיד בהפקדה מחודש שכר {month}: {','.join(str(s) for s in salaries)}",
            )


class CheckHafkadotYtdTotal(Checker):
    root_path = "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa/PirteiTaktziv"

    def check_one(self, tree: Dict[str, Any]) -> None:
        sums: DefaultDict[SugHafrasha, Decimal] = defaultdict(Decimal)
        hafkadot_ytd = tree["PerutHafkadotMetchilatShana"]
        for hafkada in hafkadot_ytd:
            sums[hafkada["SUG-HAFRASHA"]] += hafkada["SCHUM-HAFKADA-SHESHULAM"]

        hafkadot_ytd_total = tree["HafkadotShnatiyot"]
        self.assert_eq(
            sums[SugHafrasha.pitzuim],
            hafkadot_ytd_total["TOTAL-HAFKADOT-PITZUIM-SHANA-NOCHECHIT"],
            "סכום הפקדות פיצויים מתחילת השנה שונה מהפקדות שנתיות",
        )
        self.assert_eq(
            sums[SugHafrasha.tagmulim_oved],
            hafkadot_ytd_total["TOTAL-HAFKADOT-OVED-TAGMULIM-SHANA-NOCHECHIT"],
            "סכום הפקדות תגמולי עובד מתחילת השנה שונה מהפקדות שנתיות",
        )
        self.assert_eq(
            sums[SugHafrasha.tagmulim_maavid],
            hafkadot_ytd_total["TOTAL-HAFKADOT-MAAVID-TAGMULIM-SHANA-NOCHECHIT"],
            "סכום הפקדות תגמולי מעביד מתחילת השנה שונה מהפקדות שנתיות",
        )


class CheckHafrashotSize(Checker):
    root_path = "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa/PirteiTaktziv"

    def check_one(self, tree: Dict[str, Any]) -> None:
        hafrashot_percentages: Dict[SugHafrasha, Decimal] = {}
        hafrashot = tree["PerutHafrashotLePolisa"]
        for p in hafrashot:
            sug = p["SUG-HAFRASHA"]
            self.assert_(sug not in hafrashot_percentages, f"סוג הפרשה {sug} מופיע יותר מפעם אחת")
            hafrashot_percentages[sug] = p["ACHUZ-HAFRASHA"]
        for sug, (sug_min, sug_max) in HAFRASHA_RANGES_PENSION.items():
            if sug not in hafrashot_percentages:
                self.report(f"חסר סוג הפרשה {sug}")
                continue
            self.assert_range(
                sug_min,
                hafrashot_percentages[sug],
                sug_max,
                f"סוג ההפרשה {sug} מחוץ לטווח המותר",
            )


class CheckHafrashotSizeInHafkadotYtd(Checker):
    root_path = (
        "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa/PirteiTaktziv/"
        "PerutHafkadotMetchilatShana"
    )

    def check_one(self, tree: Dict[str, Any]) -> None:
        sug = tree["SUG-HAFRASHA"]
        if sug not in HAFRASHA_RANGES_PENSION:
            return
        sug_min, sug_max = HAFRASHA_RANGES_PENSION[sug]

        salary = tree["SACHAR-BERAMAT-HAFKADA"]
        hafkada_schum = tree["SCHUM-HAFKADA-SHESHULAM"]
        percentage = hafkada_schum / salary * Decimal(100)

        self.assert_range(
            sug_min,
            percentage,
            sug_max,
            f"סכום ההפרשה כאחוז מהשכר {sug} מחוץ לטווח המותר",
        )


class CheckTotalHafkadaParts(Checker):
    root_path = "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa/PirteiTaktziv"

    def check_one(self, tree: Dict[str, Any]) -> None:
        last_hafkada = tree["PirteiHafkadaAchrona"]["PerutPirteiHafkadaAchrona"][0]
        bruto = last_hafkada["TOTAL-HAFKADA"]
        neto = last_hafkada["TOTAL-HAFKADA-ACHRONA"]

        expenses = tree["PerutHotzaot"]["HotzaotBafoalLehodeshDivoach"]
        insurance_premium = fix_nil(expenses["SACH-DMEI-BITUAH-SHENIGBOO"], 0)
        dmei_nihul_hafkada = fix_nil(expenses["TOTAL-DMEI-NIHUL-HAFKADA"], 0)

        self.assert_(
            neto == bruto - insurance_premium - dmei_nihul_hafkada,
            " סכום הפקדה נטו לא מתאים לברוטו - הוצאות ביטוח - דמי ניהול מהפקדה"
            f"({neto} != {bruto} - {insurance_premium} - {dmei_nihul_hafkada} ",
        )


class CheckNechonutDate(Checker):
    root_path = "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa"

    def check_one(self, tree: Dict[str, Any]) -> None:
        nechonut_date = parse_date(tree["TAARICH-NECHONUT"])
        bitzua_date = self.headers["TAARICH-BITZUA"].date()
        self.assert_lte(nechonut_date, bitzua_date, "תאריך נכונות אחרי תאריך ביצוע ")


class CheckJoinDate(Checker):
    root_path = "YeshutYatzran/Mutzarim/Mutzar/HeshbonotOPolisot/HeshbonOPolisa"

    def check_one(self, tree: Dict[str, Any]) -> None:
        customer = self.get_path("YeshutYatzran/Mutzarim/Mutzar/NetuneiMutzar/YeshutLakoach")
        birthday = parse_date(customer["TAARICH-LEYDA"])

        join_day = parse_date(tree["TAARICH-HITZTARFUT-MUTZAR"])

        self.assert_gt(join_day, birthday, "תאריך הצטרפות לפני תאריך לידה")
