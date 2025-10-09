from app.main import ChatContinueRequest, ChatMessage, validate_first_aid_intent
from app.agents import conversational_agent


def test_validate_allows_follow_up_context():
    payload = ChatContinueRequest(
        messages=[
            ChatMessage(role="user", content="i have blisters in my finger"),
            ChatMessage(role="assistant", content="Here are some steps"),
            ChatMessage(role="user", content="not painful anymore"),
        ]
    )

    validated = validate_first_aid_intent(payload)
    assert validated is payload


def test_pipeline_keeps_follow_up_in_scope():
    history = [
        {"role": "user", "content": "i have blisters in my finger"},
        {"role": "assistant", "content": "Here are some steps"},
        {"role": "user", "content": "not painful anymore"},
    ]

    result = conversational_agent.handle_message("not painful anymore", history)

    assert not result.get("rejected"), result
    assert result["conversation"]["in_scope"] is True
    assert result["triage"]["category"] != "out_of_scope"
