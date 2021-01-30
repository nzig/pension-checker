import sys
from collections import defaultdict
from decimal import Decimal
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List

import xmlschema


class SugHafrasha(IntEnum):
    pitzuim = 1
    tagmulim_oved = 2
    tagmulim_maavid = 3


class PensionChecker:
    def __init__(self, pensia: Dict[str, Any]) -> None:
        self.pensia = pensia
        self.messages: List[str] = []

    def check(self) -> List[str]:
        polisot = self.pensia["YeshutYatzran"][0]["Mutzarim"]["Mutzar"][0][
            "HeshbonotOPolisot"
        ]["HeshbonOPolisa"]
        for polisa in polisot:
            takzivim = polisa["PirteiTaktziv"]
            for takziv in takzivim:
                self.check_hafkadot_ytd(takziv)
                self.check_last_hafkada(takziv)
                self.check_hafrashot_percentage(takziv)

        return self.messages

    def check_last_hafkada(self, takziv: Dict[str, Any]) -> None:
        """בודק שפרטי ההפקדה האחרונה תואמים לאותה הפקדה בפירוט הפקדות מתחילת השנה"""
        last_hafkada = takziv["PirteiHafkadaAchrona"]["PerutPirteiHafkadaAchrona"][
            0
        ]  # TODO what if there's more than one?
        last_total = last_hafkada["TOTAL-HAFKADA"]
        last_perut = last_hafkada["PerutHafkadaAchrona"]
        self._assert(
            sum(x["SCHUM-HAFKADA-SHESHULAM"] for x in last_perut) == last_total,
            "סכום פירוט הפקדות אחרונות שונה מסך הפקדה אחרונה",
        )
        self._assert(
            len({x["SACHAR-BERAMAT-HAFKADA"] for x in last_perut}) == 1,
            "שכר לא אחיד בהפקדה אחרונה",
        )

    def check_hafkadot_ytd(self, takziv: Dict[str, Any]) -> None:
        """בודק שסכום ההפקדות בשנה האחרונה בכל חודש שווה לסכום בשדה הפקדות שנתיות"""
        sums = defaultdict(int)
        hafkadot_ytd = takziv["PerutHafkadotMetchilatShana"]
        for hafkada in hafkadot_ytd:
            sums[hafkada["SUG-HAFRASHA"]] += hafkada["SCHUM-HAFKADA-SHESHULAM"]

        hafkadot_ytd_total = takziv["HafkadotShnatiyot"]
        self._assert(
            sums[SugHafrasha.pitzuim]
            == hafkadot_ytd_total["TOTAL-HAFKADOT-PITZUIM-SHANA-NOCHECHIT"],
            "סכום הפקדות פיצויים מתחילת השנה שונה מהפקדות שנתיות",
        )
        self._assert(
            sums[SugHafrasha.tagmulim_oved]
            == hafkadot_ytd_total["TOTAL-HAFKADOT-OVED-TAGMULIM-SHANA-NOCHECHIT"],
            "סכום הפקדות תגמולי עובד מתחילת השנה שונה מהפקדות שנתיות",
        )
        self._assert(
            sums[SugHafrasha.tagmulim_maavid]
            == hafkadot_ytd_total["TOTAL-HAFKADOT-MAAVID-TAGMULIM-SHANA-NOCHECHIT"],
            "סכום הפקדות תגמולי מעביד מתחילת השנה שונה מהפקדות שנתיות",
        )

    def check_hafrashot_percentage(self, takziv: Dict[str, Any]) -> None:
        """בודק שההפרשות בכל חודש מתאימות לאחוזי ההפרשה מהשכר"""
        hafrashot_percentages: Dict[SugHafrasha, Decimal] = {}
        perut_hafrashot = takziv["PerutHafrashotLePolisa"]
        for p in perut_hafrashot:
            sug = p["SUG-HAFRASHA"]
            self._assert(
                sug not in hafrashot_percentages, "סוג הפרשה מופיע יותר מפעם אחת"
            )
            hafrashot_percentages[sug] = p["ACHUZ-HAFRASHA"]
        self._assert(
            all(s in hafrashot_percentages for s in SugHafrasha), "חסר אחוז הפרשה"
        )

        hafkadot = takziv["PerutHafkadotMetchilatShana"]
        for hafkada in hafkadot:
            sug = hafkada["SUG-HAFRASHA"]
            sachar = hafkada["SACHAR-BERAMAT-HAFKADA"]
            hafkada_schum = hafkada["SCHUM-HAFKADA-SHESHULAM"]

            hafkada_from_percentage = (
                hafrashot_percentages[sug] * sachar / Decimal("100")
            )
            self._assert(
                hafkada_schum == hafkada_from_percentage,
                "סכום הפקדה לא מתאים לאחוז משכר",
            )

    def _assert(self, check: bool, message: str) -> None:
        if not check:
            self.messages.append(message)


def main():
    schema = xmlschema.XMLSchema(
        str(
            Path(__file__).parent
            / "MivneAchid_Holdings_KarnotPensiaHadashot_XSD_Schema_008.xsd"
        )
    )
    pensia_xml = sys.argv[1]
    pensia = schema.to_dict(pensia_xml)
    checker = PensionChecker(pensia)
    with open("out.txt", "w", encoding="utf-8") as f:
        for m in checker.check():
            print(m, file=f)


if __name__ == "__main__":
    main()
