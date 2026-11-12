"""Vérification rapide de la clé et du modèle Gemini : python -m eval.smoke_gemini"""
from app.core.config import get_settings
from app.services import gemini

if __name__ == "__main__":
    print("Modèle :", get_settings().gemini_model)
    text, usage = gemini.generate("Réponds uniquement par le mot : OK", temperature=0.0)
    print("generate ->", repr(text), usage)
    usage = gemini.Usage()
    pieces = list(gemini.stream("Compte de 1 à 5, un nombre par ligne.", usage, system="Tu es concis."))
    print("stream ->", len(pieces), "fragment(s) :", repr("".join(pieces)), usage)
    text, _ = gemini.generate("Donne un objet avec ville='Paris'.", json_schema={
        "type": "object", "properties": {"ville": {"type": "string"}}, "required": ["ville"]})
    print("json ->", text)
