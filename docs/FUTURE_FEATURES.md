# Framtida funktioner och återstående arbete

Den här listan sammanför projektets roadmap, nästa live-test, LIVI:s
telemetriplan och återstående arbete på den fysiska installationen. Punkter som
redan är delvis implementerade är markerade så att listan inte blandar ihop
färdig funktionalitet med återstående verifiering.

## Prioriterad arbetsordning

1. Stabil strömförsörjning utan underspänning eller strypning.
2. Komplett fordonstest med K+DCAN och TD5 ECU.
3. Verifiering och avkodning av injektorkoder.
4. CarPlay-test med riktig Carlinkit CPC200-CCPA.
5. Färdig kapsling och fordonsmontering.
6. Säkerhetskritiska ECU- och ABS-funktioner.

## TD5-diagnostik

### Nästa live-test

- Verifiera att gatewayen hittar K+DCAN via `/dev/serial/by-id`.
- Kontrollera RPM, kylvätska, laddspänning, MAP, MAF och bränsletemperatur mot
  rimliga värden med motorn igång.
- Långtidstesta anslutningen utan återanslutningar.
- Behåll `break-condition`; prova `send-break` bara vid återkommande problem och
  dokumentera kabelns USB-krets.
- Verifiera manuell, skrivskyddad DTC-avläsning i bilen.

### Injektorkoder — högsta diagnostikprioritet

- Läs ett enda skrivskyddat `21 3D`-konfigurationsblock.
- Kontrollera svarslängd, svarstyp och kontrollsumma.
- Jämför råsvaret med de fem fysiska spridarkoderna och aktuell ECU/motorkarta.
- Visa injektor 1–5 med kod och idle-nummer först efter entydig verifiering.
- Visa aldrig gissade injektorkoder.

### Säkerhetskritiska senare funktioner

- Radera TD5-felkoder.
- Skriva injektorkoder och andra ECU-inställningar.
- Eventuell immobiliseringshantering.
- ABS-luftning.
- ABS-pump-, ventil- och andra aktuatorprov.
- Kräv validerat protokoll, stillastående fordon, tydlig bekräftelse,
  säkerhetsspärrar och test på kompatibel Defender innan aktivering.

## CarPlay, Android Auto och telemetri

### CarPlay-test på riktig hårdvara

Status 2026-09-13: CPC200-CCPA är inkopplad och identifierad som `1314:1521
Magic Communication Tec. Auto Box`. LIVI har etablerat länken och visar
1174 × 440 H.264-video med Raspberry Pi:s hårdvaruavkodare och DMA-buffert.
Punkterna nedan som kräver handpåläggning återstår.

- USB-detektering och första videolänk är verifierade; långtidstesta stabiliteten.
- Testa trådbunden och trådlös CarPlay.
- Testa videostart, touch, ljud, mikrofon, Siri och ratt-/mediaknappar.
- Testa återanslutning efter urkoppling, telefonbyte, vila och omstart.
- Kontrollera att TD5-vyn återkommer direkt när CarPlay-video avslutas.

### Native CarPlay-telemetri som återstår

- Hastighet, RPM, växel, backsignal och rattvinkel.
- Blinkers, ljus, helljus, varningsblinkers och parkeringsbroms.
- Bränslenivå, förbrukning och EV-batteridata.
- Kylvätske-, olje-, insugs- och växellådstemperatur.
- Batterispänning, barometertryck, MAP, laddtryck, lambda och AFR.
- Vägmätare och trippmätare.

Nattläge, räckvidd, utomhustemperatur och GPS/GNSS är redan kopplade till
native CarPlay.

### Android Auto

- Migrera återstående AV/media-meddelanden från äldre `oaa` till
  `aap_protobuf` (`Setup`, `Config`, `Start` och `Ack`) i fas 2.

## Fordonsström och installation

- Välj fordonsklassad DC/DC-omvandlare dimensionerad för paj, skärm och USB.
- Lägg till säkring nära matningspunkten och skydd mot transienter/startfall.
- Detektera tändningsläge.
- Behåll reservkraft för en kontrollerad avstängning.
- Bryt matningen först när Raspberry Pi verkligen har stängt av.
- Testa uppstart och avstängning vid verklig motorstart.
- Eliminera rapporterad underspänning och aktiv strypning.
- Skapa en färdig, testad SD-kortsavbild för enkel installation.
- Dokumentera montering, kabeldragning och samtliga fordonsanslutningar.

Den manuella avstängningsknappen och visuell avstängningsbekräftelse är
implementerade. Automatisk avstängning från tändningssignal återstår.

## Kapsling och fysisk montering

- Verifiera skärmdjup, hörnradie, passning och skruvcentrum i bilen.
- Lägg till verifierade Defender-skruvhål.
- Lägg till Raspberry Pi-distanser och fästpunkter.
- Lägg till kontakthål, kabelgenomföringar och ventilation.
- Lägg till relä- och säkringsfästen.
- Lägg till bakre servicelucka och slutligt fäste/rem.
- Genomför temperatur-, vibrations- och slutlig passningstest.

## Teknisk skuld

- Flytta navigeringsstatus till Reacts `AppContext`.
- Ersätt direkt DOM-sökning med React-refs.
- Samordna reglerna för dold navigation.
- Ta bort äldre `label`-fält när översättningsnycklar täcker all text.
- Rätta typworkaround i FFT-worker.
- Rätta kvarvarande typfel och föråldrade testmockar.

## Delvis eller helt implementerat

- Backkamerasida och automatisk växling vid backsignal finns; fysisk kamera ska
  fortfarande verifieras.
- Säker manuell avstängning med bekräftelse finns; tändningsstyrd strömbrytning
  saknas.
- Läsning av TD5-felkoder finns; radering saknas.
- Grundläggande ABS-felkodsläsning finns; luftning och aktuatorprov saknas.
- Injektorsida finns; verifierad avkodning av injektorkoder saknas.

## Ursprungliga källor

- `README.md`, avsnitten om hårdvara, ström och roadmap.
- `docs/NEXT_LIVE_TEST.md`.
- `cad/README-prototype.md`.
- `third_party/LIVI/src/main/shared/types/Telemetry.ts`.
- `third_party/LIVI/src/main/services/telemetry/adapters/cpAdapter.ts`.
- `third_party/LIVI/src/main/services/projection/driver/aa/stack/proto/index.ts`.
