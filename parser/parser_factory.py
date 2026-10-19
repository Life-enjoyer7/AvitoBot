"""Parser factory: marketplace -> cached parser instance."""

from __future__ import annotations

from db.enums import Marketplace
from parser.avito_parser import AvitoParser
from parser.base_parser import BaseParser
from parser.stub_parsers import AutoParser, OzonParser, WildberriesParser
from parser.yandex_parser import YandexParser


class ParserFactory:
    """Returns a parser instance for a given marketplace."""

    _parsers: dict[Marketplace, BaseParser] = {
        Marketplace.AVITO: AvitoParser(),
        Marketplace.YANDEX: YandexParser(),
        Marketplace.OZON: OzonParser(),
        Marketplace.WB: WildberriesParser(),
        Marketplace.AUTO: AutoParser(),
    }

    @classmethod
    def get_parser(cls, marketplace: Marketplace) -> BaseParser:
        try:
            return cls._parsers[marketplace]
        except KeyError as exc:
            raise ValueError(f"No parser registered for {marketplace}") from exc
