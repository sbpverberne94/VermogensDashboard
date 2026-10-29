import io
import json
import os
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st
import fitz  # PyMuPDF

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


st.set_page_config(page_title="Vermogensdashboard", page_icon="📊", layout="wide")

st.title("Intern vermogensdashboard")
st.caption("Prototype voor het consolideren van vermogensoverzichten. Controleer alle geëxtraheerde gegevens voordat je ze gebruikt.")

with st.sidebar:
    st.header("Instellingen")
    st.write("De app draait lokaal. Bestanden en gegevens worden niet door deze app permanent opgeslagen.")
    api_key = st.text_input(
        "OpenAI API-sleutel (optioneel)",
        type="password",
        help="Alleen nodig voor automatische AI-extractie. De API wordt apart gefactureerd van ChatGPT."
    )
    model = st.text_input("Model", value="gpt-4o-mini")
    st.divider()
    st.warning(
        "Gebruik voor deze prototypeversie alleen fictieve of openbare documenten. "
        "Gebruik geen cliëntgegevens voordat IT, privacy en compliance de oplossing hebben beoordeeld."
    )


CATEGORIES = [
    "Spaargeld en cash",
    "Beleggingen",
    "Eigen woning",
    "Overig vastgoed",
    "Pensioenvermogen",
    "Ondernemingsbelang",
    "Overige bezittingen",
    "Hypotheek",
    "Overige schulden",
]

COLUMNS = [
    "Bestanddeel",
    "Categorie",
    "Bedrag",
    "Valuta",
    "Schuld",
    "Eigendom (%)",
    "Peildatum",
    "Bronbestand",
    "Bronpagina",
    "Vertrouwen",
    "Opmerking",
]


def extract_pdf_pages(uploaded_file):
    """Extract text page-by-page, preserving page numbers."""
    raw = uploaded_file.getvalue()
    doc = fitz.open(stream=raw, filetype="pdf")
    pages = []
    for idx, page in enumerate(doc):
        pages.append({"page": idx + 1, "text": page.get_text("text").strip()})
    doc.close()
    return pages


def get_ai_records(client, model_name, filename, pages):
    """Ask the model for candidate records, with page-level source references."""
    page_texts = [
        {"page": p["page"], "text": p["text"][:12000]}
        for p in pages if p["text"].strip()
    ]
    if not page_texts:
        return [], "Geen selecteerbare tekst gevonden. Dit kan een gescande PDF zijn; OCR is niet inbegrepen."

    # Bound request size for a prototype. Prefer pages containing financial data where documents are large.
    page_texts = page_texts[:100]
    prompt_data = json.dumps(page_texts, ensure_ascii=False)

    system_prompt = """
Je extraheert kandidaat-gegevens uit een financieel vermogensdocument voor een menselijke reviewer.
Gebruik uitsluitend informatie die letterlijk of duidelijk uit de aangeleverde tekst blijkt.
Geef uitsluitend een JSON-object terug met sleutel "records", met een array van objecten.
Elk object heeft:
- name: korte naam van de rekening, belegging, woning, pensioenrecht of schuld
- category: één van ["Spaargeld en cash","Beleggingen","Eigen woning","Overig vastgoed","Pensioenvermogen","Ondernemingsbelang","Overige bezittingen","Hypotheek","Overige schulden"]
- amount: numerieke waarde, zonder duizendtalscheiding
- currency: ISO-code zoals EUR, USD, GBP; als onbekend "ONBEKEND"
- is_liability: true voor schulden, anders false
- ownership_percent: percentage als getal, gebruik 100 als niet anders vermeld
- valuation_date: datum in YYYY-MM-DD indien duidelijk, anders lege string
- source_page: paginanummer uit de input
- confidence: "hoog", "middel" of "laag"
- note: korte toelichting of onzekerheid

Regels:
- Neem de marktwaarde/saldi op, geen transacties of periodieke inkomsten.
- Vermijd dubbeltellingen binnen hetzelfde document. Als een totaal een uitsplitsing bevat, neem dan het totaal of de componenten, niet beide.
- Maak geen aannames om ontbrekende gegevens aan te vullen.
- Neem pensioenuitkeringen niet op als kapitaal tenzij het document expliciet een kapitaalwaarde noemt.
- Neem hypotheekschuld op als schuld, niet als negatieve woningwaarde.
- Neem alleen relevante vermogensbestanddelen op. Als iets niet duidelijk een afzonderlijk bezit of een schuld is, laat het weg.
- Bronpagina moet een van de opgegeven paginanummers zijn.
"""
    response = client.chat.completions.create(
        model=model_name,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Bestand: {filename}\nPagina's met tekst:\n{prompt_data}"},
        ],
        temperature=0,
    )
    content = response.choices[0].message.content
    parsed = json.loads(content)
    records = parsed.get("records", [])
    cleaned = []
    for r in records:
        try:
            amount = float(r.get("amount", 0))
            if amount < 0:
                amount = abs(amount)
            category = r.get("category", "Overige bezittingen")
            if category not in CATEGORIES:
                category = "Overige bezittingen"
            page_no = int(r.get("source_page", 1))
            valid_pages = {p["page"] for p in pages}
            if page_no not in valid_pages:
                page_no = None
            cleaned.append({
                "Bestanddeel": str(r.get("name", "Onbekend bestanddeel"))[:150],
                "Categorie": category,
                "Bedrag": amount,
                "Valuta": str(r.get("currency", "ONBEKEND")).upper()[:10],
                "Schuld": bool(r.get("is_liability", False)),
                "Eigendom (%)": min(100.0, max(0.0, float(r.get("ownership_percent", 100) or 100))),
                "Peildatum": str(r.get("valuation_date", ""))[:10],
                "Bronbestand": filename,
                "Bronpagina": page_no,
                "Vertrouwen": str(r.get("confidence", "laag")).lower(),
                "Opmerking": str(r.get("note", ""))[:500],
            })
        except (ValueError, TypeError):
            continue
    return cleaned, None


def blank_record():
    return {
        "Bestanddeel": "Nieuw bestanddeel",
        "Categorie": "Overige bezittingen",
        "Bedrag": 0.0,
        "Valuta": "EUR",
        "Schuld": False,
        "Eigendom (%)": 100.0,
        "Peildatum": date.today().isoformat(),
        "Bronbestand": "Handmatige invoer",
        "Bronpagina": None,
        "Vertrouwen": "handmatig",
        "Opmerking": "",
    }


if "records" not in st.session_state:
    st.session_state.records = []
if "extracted_docs" not in st.session_state:
    st.session_state.extracted_docs = {}
if "last_upload_names" not in st.session_state:
    st.session_state.last_upload_names = []

st.subheader("1. Documenten uploaden")
uploads = st.file_uploader(
    "Selecteer één of meerdere PDF's",
    type=["pdf"],
    accept_multiple_files=True,
    help="Gebruik bij voorkeur tekstgebaseerde PDF's. OCR voor scans is niet inbegrepen in deze prototypeversie."
)

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("PDF's uitlezen", type="primary", disabled=not uploads):
        docs = {}
        errors = []
        for f in uploads:
            try:
                pages = extract_pdf_pages(f)
                docs[f.name] = pages
            except Exception as e:
                errors.append(f"{f.name}: {e}")
        st.session_state.extracted_docs = docs
        st.session_state.last_upload_names = list(docs.keys())
        if errors:
            for err in errors:
                st.error(err)
        if docs:
            st.success(f"{len(docs)} PDF('s) uitgelezen.")
with col2:
    can_analyze = bool(st.session_state.extracted_docs) and bool(api_key.strip())
    if st.button("Gegevens met AI extraheren", disabled=not can_analyze):
        if OpenAI is None:
            st.error("OpenAI-pakket ontbreekt. Installeer de dependencies uit requirements.txt.")
        else:
            try:
                client = OpenAI(api_key=api_key.strip())
                combined = []
                progress = st.progress(0)
                names = list(st.session_state.extracted_docs.keys())
                for i, name in enumerate(names):
                    records, error = get_ai_records(client, model.strip() or "gpt-4o-mini", name, st.session_state.extracted_docs[name])
                    if error:
                        st.warning(f"{name}: {error}")
                    combined.extend(records)
                    progress.progress((i + 1) / max(1, len(names)))
                st.session_state.records = combined
                st.success(f"{len(combined)} kandidaat-bestanddelen gevonden. Controleer ze hieronder.")
            except Exception as e:
                st.error(f"AI-extractie is mislukt: {e}")

if st.session_state.extracted_docs:
    with st.expander("Ingelezen documenten en tekst controleren"):
        for name, pages in st.session_state.extracted_docs.items():
            total_chars = sum(len(p["text"]) for p in pages)
            st.write(f"**{name}** · {len(pages)} pagina's · {total_chars:,} tekens")
            with st.expander(f"Tekstvoorbeeld: {name}"):
                shown = 0
                for p in pages:
                    if p["text"].strip():
                        st.markdown(f"**Pagina {p['page']}**")
                        st.text(p["text"][:1200])
                        shown += 1
                    if shown >= 3:
                        break

st.divider()
st.subheader("2. Geëxtraheerde vermogensbestanddelen controleren")
st.caption("Pas bedragen, categorieën, valuta en bronverwijzingen aan. Alleen EUR-bedragen worden bij elkaar opgeteld. Eigendomspercentage wordt toegepast op het getoonde bedrag.")

top1, top2 = st.columns([1, 3])
with top1:
    if st.button("Rij toevoegen"):
        st.session_state.records.append(blank_record())
with top2:
    if st.button("Alle gegevens wissen"):
        st.session_state.records = []
        st.rerun()

if st.session_state.records:
    df = pd.DataFrame(st.session_state.records)
else:
    df = pd.DataFrame(columns=COLUMNS)

edited = st.data_editor(
    df,
    key="asset_editor",
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Bestanddeel": st.column_config.TextColumn(required=True),
        "Categorie": st.column_config.SelectboxColumn(options=CATEGORIES, required=True),
        "Bedrag": st.column_config.NumberColumn(min_value=0.0, format="€ %.2f", required=True),
        "Valuta": st.column_config.SelectboxColumn(options=["EUR", "USD", "GBP", "CHF", "ONBEKEND"], required=True),
        "Schuld": st.column_config.CheckboxColumn(),
        "Eigendom (%)": st.column_config.NumberColumn(min_value=0.0, max_value=100.0, format="%.1f%%"),
        "Peildatum": st.column_config.TextColumn(help="YYYY-MM-DD, leeg laten als onbekend"),
        "Bronbestand": st.column_config.TextColumn(disabled=True),
        "Bronpagina": st.column_config.NumberColumn(min_value=1, step=1),
        "Vertrouwen": st.column_config.SelectboxColumn(options=["hoog", "middel", "laag", "handmatig"]),
        "Opmerking": st.column_config.TextColumn(),
    },
)

# Persist edits back into session state, dropping fully empty rows.
if edited is not None:
    st.session_state.records = edited.fillna({
        "Bestanddeel": "",
        "Categorie": "Overige bezittingen",
        "Bedrag": 0,
        "Valuta": "ONBEKEND",
        "Schuld": False,
        "Eigendom (%)": 100,
        "Peildatum": "",
        "Bronbestand": "",
        "Vertrouwen": "laag",
        "Opmerking": "",
    }).to_dict("records")

st.divider()
st.subheader("3. Geconsolideerd dashboard")

if edited is None or edited.empty:
    st.info("Upload documenten en voer gegevens in, of gebruik AI-extractie om het dashboard te vullen.")
else:
    calc = edited.copy()
    calc["Bedrag"] = pd.to_numeric(calc["Bedrag"], errors="coerce").fillna(0).abs()
    calc["Eigendom (%)"] = pd.to_numeric(calc["Eigendom (%)"], errors="coerce").fillna(100).clip(0, 100)
    calc["Aandeel"] = calc["Bedrag"] * calc["Eigendom (%)"] / 100
    calc["Valuta"] = calc["Valuta"].fillna("ONBEKEND").astype(str).str.upper()
    calc["Schuld"] = calc["Schuld"].fillna(False).astype(bool)

    eur = calc[calc["Valuta"] == "EUR"].copy()
    non_eur = calc[calc["Valuta"] != "EUR"].copy()
    assets = eur[~eur["Schuld"]]["Aandeel"].sum()
    liabilities = eur[eur["Schuld"]]["Aandeel"].sum()
    net_worth = assets - liabilities

    k1, k2, k3 = st.columns(3)
    k1.metric("Bezittingen (EUR)", f"€ {assets:,.0f}".replace(",", "."))
    k2.metric("Schulden (EUR)", f"€ {liabilities:,.0f}".replace(",", "."))
    k3.metric("Netto vermogen (EUR)", f"€ {net_worth:,.0f}".replace(",", "."))

    if not non_eur.empty:
        currencies = sorted(non_eur["Valuta"].unique())
        st.warning(
            "Niet-EUR-bedragen zijn uitgesloten van de totalen. Valutaomrekening is niet automatisch uitgevoerd. "
            "Valuta aangetroffen: " + ", ".join(currencies)
        )

    chart_data = eur[~eur["Schuld"]].groupby("Categorie", as_index=False)["Aandeel"].sum()
    chart_data = chart_data[chart_data["Aandeel"] > 0]
    if not chart_data.empty:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            st.markdown("#### Samenstelling van bezittingen")
            fig = px.pie(
                chart_data,
                names="Categorie",
                values="Aandeel",
                hole=0.35,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label")
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), legend_title_text="Categorie")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.markdown("#### Bezittingen en schulden")
            summary = pd.DataFrame({
                "Type": ["Bezittingen", "Schulden"],
                "Bedrag": [assets, liabilities],
            })
            fig2 = px.bar(summary, x="Type", y="Bedrag", text_auto=".2s")
            fig2.update_layout(showlegend=False, yaxis_title="EUR", xaxis_title="", margin=dict(t=10, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    st.markdown("#### Vermogensbestanddelen")
    display_cols = ["Bestanddeel", "Categorie", "Aandeel", "Valuta", "Schuld", "Peildatum", "Bronbestand", "Bronpagina", "Vertrouwen", "Opmerking"]
    st.dataframe(
        calc[display_cols].rename(columns={"Aandeel": "Bedrag na eigendom"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### Broncontrole")
    for _, row in calc.iterrows():
        label = f"{row.get('Bestanddeel', 'Bestanddeel')} · {row.get('Bronbestand', 'Onbekende bron')}"
        with st.expander(label):
            st.write(f"**Bronpagina:** {row.get('Bronpagina', '')}")
            st.write(f"**Peildatum:** {row.get('Peildatum', '')}")
            st.write(f"**Opmerking:** {row.get('Opmerking', '') or 'Geen'}")
            source_name = row.get("Bronbestand", "")
            source_page = row.get("Bronpagina", None)
            if source_name in st.session_state.extracted_docs and pd.notna(source_page):
                page_num = int(source_page)
                page_list = st.session_state.extracted_docs[source_name]
                matching = [p for p in page_list if p["page"] == page_num]
                if matching:
                    st.text(matching[0]["text"][:5000])

    csv = calc.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Download gegevens als CSV",
        data=csv,
        file_name="vermogensbestanddelen.csv",
        mime="text/csv",
    )

st.divider()
st.caption(
    "Prototypebeperkingen: geen OCR voor gescande PDF's, geen automatische wisselkoersen, geen permanente opslag, "
    "geen automatische detectie van dubbeltellingen tussen documenten en geen productiegeschikte authenticatie. "
    "Controleer alle resultaten handmatig."
)
