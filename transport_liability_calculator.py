"""
Calculateur de Sous-Assurance Transport
Application Streamlit - Lead Generation pour courtiers en assurance transport

Calcule les limites légales d'indemnisation et met en évidence la sous-assurance.
"""

import streamlit as st
import re
from datetime import datetime

# ─── Configuration de la page ───────────────────────────────────────────────
st.set_page_config(
    page_title="Calculateur de Couverture Transport",
    page_icon="🚚",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ─── Constantes ─────────────────────────────────────────────────────────────
DTS_RATE_CMR = 1.237      # 1 DTS ≈ 1.237 € (8.33 DTS × 1.237 ≈ 10.30 €/kg)
DTS_RATE_AIR = 1.25       # 22 DTS × 1.25 = 27.50 €/kg
DTS_RATE_MAR = 1.25       # 2 DTS × 1.25 = 2.50 €/kg ; 666.67 DTS × 1.25 ≈ 833 €/colis

MODES = [
    "Route — National (France)",
    "Route — International (CMR)",
    "Aérien (Convention Montréal / Varsovie)",
    "Maritime (Règles de La Haye-Visby)",
]

# ─── CSS personnalisé ────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* En-tête principal */
    .app-title {
        font-size: 2rem;
        font-weight: 800;
        color: #1a2f5a;
        line-height: 1.2;
    }
    .app-subtitle {
        font-size: 1.05rem;
        color: #5a6a7a;
        margin-top: 0.25rem;
        margin-bottom: 1.5rem;
    }

    /* Étapes de progression */
    .step-active  { color: #1a2f5a; font-weight: 700; }
    .step-done    { color: #28a745; }
    .step-pending { color: #aaa; }

    /* Boîtes de résultat */
    .box-danger {
        background: #fff0f0;
        border-left: 5px solid #dc3545;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
    }
    .box-warning {
        background: #fffbf0;
        border-left: 5px solid #e8a000;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
    }
    .box-success {
        background: #f0fff4;
        border-left: 5px solid #28a745;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
    }
    .box-info {
        background: #f0f6ff;
        border-left: 5px solid #1a6fc4;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
    }

    /* Masquer le menu hamburger Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Logique métier ──────────────────────────────────────────────────────────

def calcule_limite(mode: str, poids_kg: float, nb_colis: int, valeur: float) -> tuple[float, str]:
    """
    Retourne (limite_legale_eur, description_regle_appliquee).

    Route France <3t : 33 €/kg, plafonné à 1 000 €/colis
    Route France ≥3t : 20 €/kg
    CMR            : 8,33 DTS/kg
    Aérien         : 22 DTS/kg
    Maritime       : MAX(2 DTS/kg total, 666,67 DTS/colis × nb_colis)
    """
    if mode == MODES[0]:  # Route national
        if poids_kg < 3_000:
            poids_par_colis = poids_kg / nb_colis
            limite_par_colis = min(poids_par_colis * 33.0, 1_000.0)
            limite = limite_par_colis * nb_colis
            regle = f"< 3 t → 33 €/kg, plafond 1 000 €/colis | {poids_par_colis:.1f} kg/colis × 33 = {poids_par_colis*33:.0f} € → retenu {limite_par_colis:.0f} €/colis"
        else:
            limite = poids_kg * 20.0
            regle = "≥ 3 t → 20 €/kg (LTR France)"
        return limite, regle

    if mode == MODES[1]:  # CMR
        limite_kg = 8.33 * DTS_RATE_CMR
        limite = poids_kg * limite_kg
        regle = f"8,33 DTS/kg × {DTS_RATE_CMR} €/DTS = {limite_kg:.2f} €/kg (Convention CMR)"
        return limite, regle

    if mode == MODES[2]:  # Aérien
        limite_kg = 22 * DTS_RATE_AIR
        limite = poids_kg * limite_kg
        regle = f"22 DTS/kg × {DTS_RATE_AIR} €/DTS = {limite_kg:.2f} €/kg (Convention de Montréal / Varsovie)"
        return limite, regle

    if mode == MODES[3]:  # Maritime
        opt_kg   = poids_kg * 2 * DTS_RATE_MAR
        opt_col  = nb_colis * 666.67 * DTS_RATE_MAR
        limite   = max(opt_kg, opt_col)
        choix    = "base poids" if opt_kg >= opt_col else "base colis"
        regle = (
            f"MAX(2 DTS/kg × {poids_kg:.0f} kg = {opt_kg:,.0f} €, "
            f"666,67 DTS/colis × {nb_colis} colis = {opt_col:,.0f} €) "
            f"→ retenu : {choix} (Règles de La Haye-Visby)"
        )
        return limite, regle

    return 0.0, "Mode inconnu"


def email_valide(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", email))


def genere_recap(data: dict, limite: float, regle: str, reste: float, taux: float) -> str:
    """Génère le texte brut du récapitulatif téléchargeable."""
    lignes = [
        "=" * 60,
        "  ANALYSE DE COUVERTURE TRANSPORT",
        "  Calculateur de Sous-Assurance",
        "=" * 60,
        f"  Date           : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        f"  Email           : {st.session_state.get('email', 'N/A')}",
        "",
        "  PARAMÈTRES DE L'EXPÉDITION",
        "-" * 60,
        f"  Mode de transport  : {data['mode']}",
        f"  Poids total        : {data['poids']:,.1f} kg",
        f"  Nombre de colis    : {data['colis']}",
        f"  Valeur déclarée    : {data['valeur']:,.2f} €",
        "",
        "  RÉSULTAT DU CALCUL",
        "-" * 60,
        f"  Règle appliquée    : {regle}",
        f"  Limite légale      : {limite:,.2f} €",
        f"  Taux de couverture : {taux:.1f} %",
        f"  Reste à charge     : {reste:,.2f} €",
        "",
        "  AVERTISSEMENT",
        "-" * 60,
        f"  En cas de sinistre total, seuls {taux:.1f} % de votre",
        f"  marchandise seraient remboursés par le transporteur.",
        f"  Un contrat d'assurance ad valorem vous garantit une",
        f"  indemnisation à la valeur réelle.",
        "",
        "  Ce document est fourni à titre indicatif.",
        "  Contactez votre courtier pour un devis personnalisé.",
        "=" * 60,
    ]
    return "\n".join(lignes)


# ─── Session state ────────────────────────────────────────────────────────────
for key, val in [("etape", 1), ("data", {}), ("email", "")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ─── En-tête ─────────────────────────────────────────────────────────────────
st.markdown('<div class="app-title">🚚 Calculateur de Couverture Transport</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Découvrez en 2 minutes si votre marchandise est bien protégée face aux limites légales.</div>',
    unsafe_allow_html=True,
)

# ─── Barre de progression ─────────────────────────────────────────────────────
etapes_labels = ["1 · Informations", "2 · Identification", "3 · Résultats"]
cols_prog = st.columns(3)
for i, (col, label) in enumerate(zip(cols_prog, etapes_labels), 1):
    with col:
        if i < st.session_state.etape:
            st.markdown(f'<span class="step-done">✅ {label}</span>', unsafe_allow_html=True)
        elif i == st.session_state.etape:
            st.markdown(f'<span class="step-active">▶ {label}</span>', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="step-pending">○ {label}</span>', unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 1 — Formulaire d'entrée
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.etape == 1:

    st.subheader("Décrivez votre expédition")

    with st.form("form_transport", clear_on_submit=False):

        mode = st.selectbox(
            "Mode de transport *",
            MODES,
            help="Choisissez le mode de transport utilisé pour cette expédition.",
        )

        col1, col2 = st.columns(2)
        with col1:
            poids = st.number_input(
                "Poids total (kg) *",
                min_value=0.1,
                value=500.0,
                step=50.0,
                format="%.1f",
                help="Poids brut total de l'expédition en kilogrammes.",
            )
        with col2:
            colis = st.number_input(
                "Nombre de colis *",
                min_value=1,
                value=10,
                step=1,
                help="Nombre total d'unités de chargement / colis.",
            )

        valeur = st.number_input(
            "Valeur totale de la marchandise (€) *",
            min_value=1.0,
            value=10_000.0,
            step=500.0,
            format="%.2f",
            help="Valeur commerciale totale (facture) de la marchandise transportée.",
        )

        soumis = st.form_submit_button(
            "Calculer ma couverture  →",
            type="primary",
            use_container_width=True,
        )

        if soumis:
            st.session_state.data = {
                "mode":   mode,
                "poids":  poids,
                "colis":  int(colis),
                "valeur": valeur,
            }
            st.session_state.etape = 2
            st.rerun()

    st.caption("Taux DTS indicatifs : CMR 1,237 €/DTS — Aérien & Maritime 1,25 €/DTS. Calcul non contractuel.")

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 2 — Mur d'email
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.etape == 2:

    st.subheader("Accédez à votre analyse personnalisée")

    d = st.session_state.data
    limite_preview, _ = calcule_limite(d["mode"], d["poids"], d["colis"], d["valeur"])
    taux_preview = min(limite_preview / d["valeur"] * 100, 100)

    # Teaser sans révéler le chiffre précis
    if taux_preview < 30:
        st.markdown(
            '<div class="box-danger">🚨 <strong>Anomalie détectée :</strong> votre couverture légale semble <em>très</em> insuffisante. Consultez l\'analyse complète.</div>',
            unsafe_allow_html=True,
        )
    elif taux_preview < 80:
        st.markdown(
            '<div class="box-warning">⚠️ <strong>Couverture partielle détectée :</strong> des lacunes significatives ont été identifiées. Découvrez les détails.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="box-success">✅ Situation globalement favorable — consultez l\'analyse pour en avoir la certitude.</div>',
            unsafe_allow_html=True,
        )

    st.write("")
    st.write("**Entrez votre email professionnel pour afficher les résultats :**")

    email_input = st.text_input(
        "Adresse email",
        placeholder="prenom.nom@entreprise.com",
        label_visibility="collapsed",
    )
    st.caption("🔒 Vos données ne sont jamais revendues. Utilisées uniquement pour vous transmettre votre analyse.")

    col_retour, col_valider = st.columns(2)
    with col_retour:
        if st.button("← Modifier mes données", use_container_width=True):
            st.session_state.etape = 1
            st.rerun()
    with col_valider:
        if st.button("Voir mes résultats  →", type="primary", use_container_width=True):
            if not email_input.strip():
                st.error("Veuillez saisir votre adresse email.")
            elif not email_valide(email_input.strip()):
                st.error("Format d'email invalide. Exemple : prenom.nom@entreprise.com")
            else:
                st.session_state.email = email_input.strip()
                st.session_state.etape = 3
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAPE 3 — Résultats
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.etape == 3:

    d = st.session_state.data
    limite, regle = calcule_limite(d["mode"], d["poids"], d["colis"], d["valeur"])
    valeur       = d["valeur"]
    reste        = max(valeur - limite, 0.0)
    taux         = min(limite / valeur * 100, 100.0)
    non_couvert  = 100.0 - taux

    st.subheader("📊 Votre analyse de couverture")

    # ── Métriques clés ──
    c1, c2, c3 = st.columns(3)
    c1.metric("Valeur de la marchandise", f"{valeur:,.0f} €")
    c2.metric("Limite légale d'indemnisation", f"{limite:,.0f} €")
    c3.metric(
        "Reste à votre charge",
        f"{reste:,.0f} €",
        delta=f"−{non_couvert:.0f} % non couvert" if reste > 0 else "Couvert à 100 %",
        delta_color="inverse",
    )

    st.divider()

    # ── Jauge visuelle ──
    st.write("**Taux de couverture légale :**")

    if taux >= 90:
        gauge_label = f"🟢  Couverture satisfaisante — {taux:.1f} % remboursé"
    elif taux >= 50:
        gauge_label = f"🟡  Couverture partielle — {taux:.1f} % remboursé"
    else:
        gauge_label = f"🔴  Couverture très insuffisante — {taux:.1f} % remboursé"

    st.progress(int(taux), text=gauge_label)

    # ── Message d'avertissement ──
    if taux >= 100:
        st.markdown(
            '<div class="box-success">✅ <strong>La limite légale couvre l\'intégralité de la valeur déclarée</strong> pour ce mode de transport.</div>',
            unsafe_allow_html=True,
        )
    elif taux >= 50:
        st.markdown(
            f'<div class="box-warning">⚠️ <strong>Attention — vous n\'êtes remboursé qu\'à {taux:.1f} % de votre valeur réelle.</strong><br>'
            f'En cas de sinistre total, votre reste à charge serait de <strong>{reste:,.0f} €</strong> '
            f'({non_couvert:.1f} % de la valeur non couverte).</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="box-danger">🚨 <strong>SOUS-ASSURANCE CRITIQUE — vous n\'êtes remboursé qu\'à {taux:.1f} % de votre valeur réelle.</strong><br>'
            f'En cas de sinistre total, vous perdriez <strong>{reste:,.0f} €</strong> '
            f'({non_couvert:.1f} % de la valeur). Un contrat ad valorem est indispensable.</div>',
            unsafe_allow_html=True,
        )

    # ── Détail du calcul ──
    with st.expander("📋 Détail du calcul", expanded=True):
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"**Mode de transport**"); st.caption(d["mode"])
            st.write(f"**Poids total**");        st.caption(f"{d['poids']:,.1f} kg")
            st.write(f"**Nombre de colis**");    st.caption(str(d["colis"]))
        with col_b:
            st.write(f"**Valeur déclarée**");    st.caption(f"{valeur:,.2f} €")
            st.write(f"**Limite légale**");       st.caption(f"{limite:,.2f} €")
            st.write(f"**Reste à charge**");      st.caption(f"{reste:,.2f} €")

        st.divider()
        st.write("**Règle appliquée :**")
        st.caption(regle)

    # ── Appel à l'action ──
    st.divider()
    st.markdown(
        '<div class="box-info">📧 <strong>Une copie de cette analyse vous sera transmise à : '
        f'{st.session_state.email}</strong></div>',
        unsafe_allow_html=True,
    )

    st.markdown("#### 💼 Protégez votre marchandise à sa juste valeur")
    st.write(
        "Les limites légales sont calculées sur le poids, pas sur la valeur commerciale. "
        "Une **assurance ad valorem** vous garantit une indemnisation à la valeur réelle de votre marchandise, "
        "quelle que soit la cause du sinistre."
    )

    # ── Boutons d'action ──
    recap = genere_recap(d, limite, regle, reste, taux)
    col_dl, col_new = st.columns(2)

    with col_dl:
        st.download_button(
            label="📥 Télécharger le récapitulatif",
            data=recap,
            file_name=f"analyse_transport_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_new:
        if st.button("🔄 Nouvelle simulation", use_container_width=True):
            st.session_state.etape = 1
            st.session_state.data  = {}
            st.session_state.email = ""
            st.rerun()
