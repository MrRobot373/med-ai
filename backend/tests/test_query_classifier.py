from __future__ import annotations

from app.chat.query_classifier import classify_query


def test_greeting_does_not_need_retrieval():
    for text in ["hi", "Hello!", "thanks", "Thank you", "ok", "Good morning"]:
        result = classify_query(text)
        assert result.task == "general_conversation"
        assert result.needs_retrieval is False


def test_clinical_question_needs_retrieval():
    result = classify_query("What is the patient's current IOP trend?")
    assert result.task == "clinical_question"
    assert result.needs_retrieval is True


def test_empty_text_does_not_need_retrieval():
    result = classify_query("   ")
    assert result.needs_retrieval is False
