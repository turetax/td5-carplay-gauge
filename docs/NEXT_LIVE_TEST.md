# Nästa live-test med K+DCAN

> **Prioritet 1 — injektorkoder:** Läs det läsande TD5-konfigurationsblocket
> (`21 3D`) och jämför råsvaret med de fem fysiska spridarkoderna. Implementera
> visning av `Injector 1–5: ABCDE · n` först när avkodningen har verifierats
> mot den aktuella ECU:n och motorkartan. Visa aldrig gissade koder.

## Förberedelser

* Bilen står stilla, växellådan i neutralläge/parkeringsläge och handbromsen är
  åtdragen.
* Anslut bara K+DCAN-kabeln till Pi:n. Kör inte parallellt Nanocom, Hawkeye,
  ELM327 eller annan diagnosutrustning på samma K-line.
* Börja med tändningen i läge II. Starta motorn endast för värden som kräver
  laddning eller varvtal.
* Spara eller fotografera de fem fysiska koderna från spridarna, i cylinderordning
  1–5. Notera även vilken mapp/ECU-typ bilen använder om det är känt.

## Testordning

1. **Adapter och session:** kontrollera att gatewayen hittar adaptern via
   `/dev/serial/by-id` och att status blir `Ansluten` med tändningen i läge II.
   Spara det användarvänliga felmeddelandet om den inte ansluter.
2. **Injektorkonfiguration — läsande test:** hämta ett enda `21 3D`-svar,
   spara råsvaret lokalt och kontrollera längd, svarstyp och kontrollsumma.
   Inga inställningar får skrivas och inga koder får rensas.
3. **Verifiera avkodning:** jämför blocket med de kända spridarkoderna. Först
   efter en entydig matchning läggs kod och idle-nummer in på injektorsidan.
4. **Livevärden med motor igång:** jämför RPM, kylvätska, laddspänning, MAP,
   MAF och bränsletemperatur mot rimliga värden. Kontrollera att kabeln klarar
   minst några minuter utan återanslutningar.
5. **K-line timing endast vid problem:** behåll `break-condition` om allt
   fungerar. Testa det alternativa `send-break`-läget endast om anslutningen
   återkommande misslyckas och dokumentera vilket kabelchip som används.
6. **Felkoder:** gör en manuell, läsande DTC-avläsning och kontrollera att
   dashboarden visar tydlig status. Rensa inga felkoder under detta test.

## Utanför scope tills vidare

* ABS-luftning, ABS-pump/ventiler och andra aktuatorprov.
* Skrivning av injektorkoder, ECU-inställningar eller immobiliserdata.
* Felkodsrensning.

De funktionerna kräver Defender-specifik protokollvalidering och separat,
tydlig användarbekräftelse.
