# Intern vermogensdashboard

Een prototype voor het uitlezen en consolideren van vermogensoverzichten in PDF-formaat.

## Functionaliteit

- Meerdere PDF's uploaden
- Tekst uit PDF's uitlezen met paginanummers
- Optionele AI-extractie van kandidaat-vermogensbestanddelen
- Gegevens handmatig controleren en corrigeren
- Bezittingen, schulden en netto vermogen berekenen
- Taartdiagram van de samenstelling van bezittingen
- Bronbestand en bronpagina bewaren bij geëxtraheerde gegevens
- CSV-export

## Lokaal starten

Vereist Python 3.11 of nieuwer.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Installeer afhankelijkheden en start:

```bash
pip install -r requirements.txt
streamlit run app.py
```

De app opent normaal gesproken in je browser.

## AI-extractie

AI-extractie is optioneel. Zonder API-sleutel kun je de interface testen en gegevens handmatig invoeren.

Voor AI-extractie:
1. Vul in de zijbalk een OpenAI API-sleutel in.
2. Controleer het ingestelde model en de actuele beschikbaarheid.
3. Upload alleen documenten die je naar de gekozen API mag versturen.

Een ChatGPT-abonnement omvat niet automatisch API-gebruik. API-gebruik kan apart worden gefactureerd.

## Belangrijke beperkingen

Dit is een prototype en geen productiegeschikt cliëntsysteem.

- Geen login of gebruikersbeheer
- Geen database of permanente opslag
- Geen OCR voor PDF's die alleen uit scans bestaan
- Geen automatische wisselkoersconversie
- Niet-EUR-bedragen worden niet meegenomen in EUR-totalen
- Geen automatische detectie van dubbeltellingen tussen documenten
- Peildata worden niet automatisch geharmoniseerd
- AI-extractie kan fouten maken; controleer alle bedragen en bronpagina's
- Geen formele beveiligings-, privacy- of compliancebeoordeling

Gebruik tijdens ontwikkeling alleen fictieve of openbare documenten. Gebruik geen cliëntgegevens voordat de organisatie de architectuur, leveranciers, beveiliging en privacy heeft beoordeeld.

## GitHub

1. Maak een **private** repository aan op GitHub.
2. Upload alle bestanden uit deze map.
3. Commit nooit API-sleutels, echte cliëntdocumenten of exports met persoonsgegevens.
4. Deze applicatie is bedoeld om lokaal te draaien. GitHub Pages kan deze Python-app niet uitvoeren.

## Structuur

```text
vermogen-dashboard/
├── .streamlit/
│   └── config.toml
├── .gitignore
├── LICENSE
├── README.md
├── app.py
└── requirements.txt
```
