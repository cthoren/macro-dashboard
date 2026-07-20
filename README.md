# Makrosläpp — håller rörelsen?

Interaktiv makro-reaktionsmodell för ädelmetaller. Väger 6 faktorer (2Y-ränta,
10Y realränta, DXY, arbetsmarknad, positionering, inflations-print) och läser av
om en metallrörelse efter ett CPI/PPI/jobb/PCE/FOMC-släpp håller eller fadar.

**Live:** https://cthoren.github.io/macro-dashboard/

## Hur den hålls färsk

`refresh.py` drar guld/silver/DXY (yfinance) + 2Y/realränta/CPI/NFP (FRED) och
bakar in serierna i `index.html`. En schemalagd GitHub Action (`.github/workflows/refresh.yml`)
kör det dagligen och committar — sidan är helt självgående, ingen server.

Reaktionsmodellens 6-faktor-scoring sätts manuellt per släpp (omdömes-passet är
själva poängen — modellen är ett resonemangsverktyg, inte en pris-ticker).
